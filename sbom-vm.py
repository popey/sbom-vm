#!/usr/bin/env python3

import subprocess
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
import time
import shutil
import tempfile

def setup_logging(image_path: Path) -> logging.Logger:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"{timestamp}_{image_path.stem}.log"
    
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

logger = None  # Will be initialized in main()

class ImageMounter:
    def __init__(self, image_path: str, mount_point: str = "/mnt/image_analysis"):
        self.image_path = Path(image_path)
        self.mount_point = Path(mount_point)
        self.nbd_device = "/dev/nbd0"
        self.mounted_partition = None
        self.temp_dir = None
        self.temp_image = None

    def parse_size(self, size_str):
        """Parse size strings with units into numeric values."""
        try:
            size_str = str(size_str).strip().upper()
            if 'GB' in size_str:
                return float(size_str.rstrip('GB')) * 1024
            elif 'MB' in size_str:
                return float(size_str.rstrip('MB'))
            elif 'KB' in size_str:
                return float(size_str.rstrip('KB')) / 1024
            else:
                return float(size_str)
        except (ValueError, AttributeError):
            return 0

    def _run_command(self, command: list, check: bool = True, **kwargs) -> subprocess.CompletedProcess:
        try:
            result = subprocess.run(command, check=check, capture_output=True, text=True, **kwargs)
            return result
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed: {' '.join(command)}")
            logger.error(f"Error output: {e.stderr}")
            raise

    def _detect_image_format(self) -> str:
        """Detect the format of the input image."""
        logger.info(f"Detecting format of {self.image_path}")
        
        try:
            result = self._run_command(["qemu-img", "info", str(self.image_path)])
            for line in result.stdout.split('\n'):
                if line.startswith('file format:'):
                    fmt = line.split(':')[1].strip()
                    logger.info(f"qemu-img detected format: {fmt}")
                    return fmt
        except subprocess.CalledProcessError as e:
            logger.warning(f"qemu-img info failed: {e}")

        # Fallback to extension-based detection
        suffix = self.image_path.suffix.lower()
        if suffix == '.vmdk':
            return 'vmdk'
        elif suffix in ['.ami', '.raw']:
            # Check if gzipped
            try:
                with open(self.image_path, 'rb') as f:
                    if f.read(2).startswith(b'\x1f\x8b'):
                        return 'gzip'
            except Exception as e:
                logger.warning(f"Failed to check if file is gzipped: {e}")
        
        return 'raw'  # Default to raw format

    def _prepare_image(self) -> Path:
        """Prepare image for mounting, converting if necessary."""
        self.temp_dir = tempfile.mkdtemp(prefix='sbomvm_')
        image_format = self._detect_image_format()
        
        if image_format == 'gzip':
            logger.info("Decompressing gzipped image")
            self.temp_image = Path(self.temp_dir) / f"{self.image_path.stem}.raw"
            self._run_command(
                ["gunzip", "-c", str(self.image_path)],
                stdout=open(self.temp_image, 'wb'),
                text=False
            )
            return self.temp_image
            
        elif image_format in ['vmdk', 'vhd', 'vpc']:
            logger.info(f"Converting {image_format} to qcow2")
            self.temp_image = Path(self.temp_dir) / f"{self.image_path.stem}.qcow2"
            self._run_command([
                "qemu-img", "convert",
                "-f", image_format,
                "-O", "qcow2",
                str(self.image_path),
                str(self.temp_image)
            ])
            return self.temp_image
        
        return self.image_path

    def setup_nbd(self):
        logger.info("Loading NBD kernel module")
        self._run_command(["modprobe", "nbd", "max_part=8"])
        time.sleep(1)

    def connect_image(self):
        prepared_image = self._prepare_image()
        logger.info(f"Connecting image {prepared_image} to NBD device")
        self._run_command(["qemu-nbd", "--connect", self.nbd_device, str(prepared_image)])
        # Increase delay to allow NBD device to stabilize
        time.sleep(2)
        # Trigger partition rescanning
        self._run_command(["partprobe", self.nbd_device])
        time.sleep(1)

    def find_filesystem_partition(self) -> str:
        logger.info("Analyzing partitions")
        
        # Add extra delay and retry logic for partition analysis
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Use parted for detailed partition info
                parted_result = self._run_command(["parted", "-s", self.nbd_device, "print"])
                break
            except subprocess.CalledProcessError as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Partition analysis failed, attempt {attempt + 1}/{max_retries}")
                    time.sleep(2)
                    continue
                raise
        
        logger.debug("parted output:\n%s", parted_result.stdout)
        
        # Parse parted output to find partitions
        partitions = []
        for line in parted_result.stdout.split('\n'):
            if not line.strip() or any(x in line for x in ['Number', 'Disk', 'Model:', 'Partition Table:']):
                continue
                
            # More robust parsing of parted output
            parts = line.strip().split()
            if len(parts) >= 4:  # Need at least number, start, end, and size
                number = parts[0]
                partition = f"{self.nbd_device}p{number}"
                
                # Find filesystem type - it's usually after the size
                fs_type = ''
                for i, part in enumerate(parts):
                    if part.lower() in ['ext4', 'ntfs', 'hfsplus', 'apfs', 'fat32', 'vfat', 'btrfs']:
                        fs_type = part.lower()
                        break
                
                size = parts[3] if len(parts) > 3 else '0'
                
                # Skip known system partitions
                if any(x in line for x in ['Microsoft reserved', 'hidden, diag']):
                    logger.info(f"Skipping system partition {partition}")
                    continue
                
                # Handle EFI system partition
                if 'esp' in line.lower() or 'EFI' in line:
                    logger.info(f"Found EFI system partition {partition}")
                    if fs_type.lower() in ['vfat', 'fat32']:
                        partitions.append((partition, fs_type.lower(), size, 0))  # Priority 0 (lowest)
                    continue
                
                # Skip swap partitions
                if 'swap' in line.lower():
                    logger.info(f"Skipping swap partition {partition}")
                    continue
                
                # Check filesystem type
                if fs_type and fs_type.lower() in ['ntfs', 'hfsplus', 'apfs', 'ext4', 'vfat', 'fat32', 'btrfs']:
                    # Assign priority based on filesystem type
                    priority = {
                        'ext4': 3,    # Highest priority for Linux root
                        'btrfs': 3,   # High priority for Linux root
                        'ntfs': 2,    # High priority for Windows
                        'hfsplus': 2, # High priority for macOS
                        'apfs': 2,    # High priority for macOS
                        'vfat': 1,    # Lower priority
                        'fat32': 1    # Lower priority
                    }.get(fs_type.lower(), 0)
                    
                    partitions.append((partition, fs_type.lower(), size, priority))
                    logger.info(f"Found usable partition {partition} of type {fs_type}")
                else:
                    # Try blkid for additional detection
                    try:
                        blkid_result = self._run_command(["blkid", partition], check=False)
                        if blkid_result.returncode == 0:
                            blkid_output = blkid_result.stdout.lower()
                            for fs in ['ntfs', 'hfsplus', 'apfs', 'ext4', 'vfat', 'zfs_member', 'btrfs']:
                                if fs in blkid_output:
                                    priority = 3 if fs in ['ext4', 'btrfs'] else 2 if fs in ['ntfs', 'hfsplus', 'apfs'] else 1
                                    partitions.append((partition, fs, size, priority))
                                    logger.info(f"Found usable partition {partition} of type {fs} (via blkid)")
                                    break
                    except Exception as e:
                        logger.debug(f"Error running blkid on {partition}: {e}")

        if not partitions:
            logger.error("Partition analysis for debugging:")
            logger.error("parted output:\n%s", parted_result.stdout)
            raise RuntimeError("No supported filesystem partitions found")
        
        logger.info(f"Found filesystem partition(s): {', '.join(f'{p[0]} ({p[1]})' for p in partitions)}")
        
        # Sort partitions by priority (highest first) and then by size (largest first)
        sorted_partitions = sorted(partitions, 
                                 key=lambda x: (x[3], self.parse_size(x[2])), 
                                 reverse=True)
        selected_partition = sorted_partitions[0][0]
        logger.info(f"Selected partition {selected_partition} (priority: {sorted_partitions[0][3]}, size: {sorted_partitions[0][2]})")
        
        return selected_partition
        
    def mount_filesystem(self):
        self.mounted_partition = self.find_filesystem_partition()
        self.mount_point.mkdir(parents=True, exist_ok=True)

        # Get filesystem type
        result = self._run_command(["blkid", "-o", "value", "-s", "TYPE", self.mounted_partition])
        fs_type = result.stdout.strip().lower()
        
        logger.info(f"Mounting {fs_type} filesystem")
        
        if fs_type == "zfs_member":
            self._handle_zfs(self.mounted_partition)
        elif fs_type == "btrfs":
            # Handle btrfs mount with specific options
            mount_opts = ["mount", "-t", "btrfs", "-o", "ro"]
            self._run_command(mount_opts + [self.mounted_partition, str(self.mount_point)])
        elif fs_type == "hfsplus":
            self._run_command(["mount", "-t", "hfsplus", "-o", "ro,force", 
                            self.mounted_partition, str(self.mount_point)])
        elif fs_type == "apfs":
            self._run_command(["modprobe", "apfs"], check=False)
            mount_opts = ["mount", "-t", "apfs", "-o", "ro"]
            self._run_command(mount_opts + [self.mounted_partition, str(self.mount_point)])
        else:
            mount_opts = ["mount", "-o", "ro"]
            if fs_type in ["ntfs", "vfat", "ufs"]:
                mount_opts.extend(["-t", fs_type])
            self._run_command(mount_opts + [self.mounted_partition, str(self.mount_point)])

    def _handle_zfs(self, zfs_partition):
        logger.info(f"Attempting to import ZFS pool from {zfs_partition}")
        
        # First, scan for available pools
        scan_result = self._run_command([
            "zpool", "import", "-d", zfs_partition
        ])
        
        # Parse output to find pool name
        pool_name = None
        for line in scan_result.stdout.split('\n'):
            if line.strip().startswith('pool:'):
                pool_name = line.split(':', 1)[1].strip()
                break
        
        if not pool_name:
            raise RuntimeError(f"No ZFS pool found in {zfs_partition}")
            
        logger.info(f"Found ZFS pool: {pool_name}")
        
        # Now import the pool
        self._run_command([
            "zpool", "import", "-f", "-d", zfs_partition,
            "-R", str(self.mount_point), "-o", "readonly=on", pool_name
        ])

    def generate_sbom(self):
        # Get filesystem type
        try:
            fs_type = self._run_command(
                ["blkid", "-o", "value", "-s", "TYPE", self.mounted_partition]
            ).stdout.strip()
        except:
            fs_type = "unknown"
        
        # Extract partition device name
        partition_name = self.mounted_partition.split('/')[-1]
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        image_name = self.image_path.stem
        output_file = f"{timestamp}_sbom_{image_name}_{partition_name}_{fs_type}.json"
        
        logger.info(f"Generating SBOM for mounted filesystem at {self.mount_point}")
        logger.info(f"Filesystem type: {fs_type}")
        
        # Debug mount contents
        self._run_command(["ls", "-la", str(self.mount_point)])
        self._run_command(["mount"])
        
        # Generate SBOM
        self._run_command([
            "syft",
            "--override-default-catalogers", "image",
            str(self.mount_point),
            "-o", f"syft-json=./{output_file}"
        ])
        
        logger.info(f"SBOM generated: {output_file}")

    def cleanup(self):
        logger.info("Starting cleanup")
        
        # Export ZFS pools
        try:
            pools = self._run_command(["zpool", "list", "-H"], check=False)
            if pools.returncode == 0 and pools.stdout.strip():
                for pool in pools.stdout.strip().split('\n'):
                    pool_name = pool.split()[0]
                    logger.info(f"Exporting ZFS pool {pool_name}")
                    self._run_command(["zpool", "export", pool_name], check=False)
        except Exception as e:
            logger.debug(f"Error during ZFS cleanup: {e}")

        if self.mount_point.is_mount():
            logger.info(f"Unmounting {self.mount_point}")
            self._run_command(["umount", str(self.mount_point)], check=False)
        
        logger.info("Disconnecting NBD device")
        self._run_command(["qemu-nbd", "--disconnect", self.nbd_device], check=False)
        
        logger.info("Removing NBD kernel module")
        self._run_command(["rmmod", "nbd"], check=False)
        
        # Clean up temporary files
        if self.temp_image and self.temp_image.exists():
            logger.info(f"Removing temporary image: {self.temp_image}")
            self.temp_image.unlink()
        
        if self.temp_dir and Path(self.temp_dir).exists():
            logger.info(f"Removing temporary directory: {self.temp_dir}")
            shutil.rmtree(self.temp_dir)

def main():
    if len(sys.argv) != 2:
        print("Usage: script.py <path_to_image>")
        sys.exit(1)

    if os.geteuid() != 0:
        print("This script must be run as root")
        sys.exit(1)

    image_path = Path(sys.argv[1])
    global logger
    logger = setup_logging(image_path)
    mounter = ImageMounter(image_path)

    try:
        mounter.setup_nbd()
        mounter.connect_image()
        mounter.mount_filesystem()
        mounter.generate_sbom()
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)
    finally:
        mounter.cleanup()

if __name__ == "__main__":
    main()