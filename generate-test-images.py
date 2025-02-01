#!/usr/bin/env python3

import subprocess
import sys
import os
from pathlib import Path
import logging
import shutil
import time
import tempfile
from typing import Optional, List, Dict

# Get the directory where the script is located
SCRIPT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))

class CommandNotFoundException(Exception):
    pass

class TestImageGenerator:
    REQUIRED_COMMANDS = {
        'fallocate': 'util-linux',
        'parted': 'parted',
        'losetup': 'util-linux',
        'mkfs.fat': 'dosfstools',
        'mkfs.ext4': 'e2fsprogs',
        'mount': 'util-linux',
        'umount': 'util-linux',
        'docker': 'docker.io',
        'tar': 'tar',
        'qemu-img': 'qemu-utils'
    }

    def __init__(self, output_dir: str = "test_images"):
        self.output_dir = SCRIPT_DIR / output_dir
        self.logger = logging.getLogger(__name__)
        self.verify_commands()
        
        # Create output directory safely
        self.logger.info(f"Creating output directory at {self.output_dir}")
        os.makedirs(self.output_dir, exist_ok=True)
        if not os.access(self.output_dir, os.W_OK):
            raise PermissionError(f"Cannot write to output directory: {self.output_dir}")

    def verify_commands(self):
        """Verify all required commands are available."""
        missing_commands = {}
        for cmd, package in self.REQUIRED_COMMANDS.items():
            if not shutil.which(cmd):
                missing_commands[cmd] = package
        
        if missing_commands:
            commands_str = '\n'.join(f"  - {cmd} (from package {pkg})" 
                                   for cmd, pkg in missing_commands.items())
            raise CommandNotFoundException(
                f"Required commands not found. Please install:\n{commands_str}"
            )

    def _run_command(self, command: List[str], check: bool = True, 
                        timeout: Optional[int] = None, binary_output: bool = False, **kwargs) -> subprocess.CompletedProcess:
        """Run a command with proper logging and error handling."""
        cmd_str = ' '.join(command)
        self.logger.debug(f"Running command: {cmd_str}")
        
        try:
            if 'stdout' in kwargs or 'stderr' in kwargs:
                # If stdout/stderr are redirected, don't use capture_output
                result = subprocess.run(
                    command,
                    check=check,
                    timeout=timeout,
                    text=not binary_output,
                    **kwargs
                )
            else:
                # Otherwise capture output for logging
                result = subprocess.run(
                    command,
                    check=check,
                    capture_output=True,
                    timeout=timeout,
                    text=not binary_output,
                    **kwargs
                )
                
                if result.stdout and not binary_output:
                    self.logger.debug(f"Command output: {result.stdout.strip()}")
                if result.stderr and not binary_output:
                    self.logger.debug(f"Command stderr: {result.stderr.strip()}")
            
            return result
                
        except subprocess.TimeoutExpired:
            self.logger.error(f"Command timed out after {timeout}s: {cmd_str}")
            raise
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Command failed with exit code {e.returncode}: {cmd_str}")
            if e.stdout and not binary_output:
                self.logger.error(f"Command output: {e.stdout.strip()}")
            if e.stderr and not binary_output:
                self.logger.error(f"Error output: {e.stderr.strip()}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error running command {cmd_str}: {str(e)}")
            raise

    def create_raw_disk(self, size_mb: int = 1024) -> Path:
        """Create an empty raw disk image using fallocate."""
        image_path = Path(tempfile.mktemp(prefix="disk_", suffix=".raw", dir=str(self.output_dir)))
        
        self.logger.info(f"Creating {size_mb}MB raw disk image at {image_path}")
        self._run_command([
            "fallocate", "-l", f"{size_mb}M", str(image_path)
        ])
        
        # Verify file was created with correct size
        if not image_path.exists():
            raise RuntimeError(f"Failed to create image file: {image_path}")
            
        actual_size = image_path.stat().st_size
        expected_size = size_mb * 1024 * 1024
        if actual_size != expected_size:
            raise RuntimeError(
                f"Created image has wrong size. Expected {expected_size}, got {actual_size}"
            )
            
        return image_path

    def partition_disk(self, image_path: Path):
        """Create a typical partition layout."""
        self.logger.info(f"Creating partition table on {image_path}")
        
        # Verify image exists
        if not image_path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")
        
        parted_commands = [
            "mklabel gpt",
            # EFI System Partition
            "mkpart ESP fat32 1MiB 501MiB",
            "set 1 esp on",
            # Root partition
            "mkpart primary ext4 501MiB 100%"
        ]
        
        for cmd in parted_commands:
            self._run_command(["parted", "-s", str(image_path)] + cmd.split())
            # Brief pause to ensure partition table changes are registered
            time.sleep(0.5)

    def setup_loop_device(self, image_path: Path) -> str:
        """Attach disk image to loop device."""
        self.logger.info(f"Setting up loop device for {image_path}")
        
        # Verify image exists
        if not image_path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")
            
        result = self._run_command(["losetup", "--show", "-f", str(image_path)])
        loop_device = result.stdout.strip()
        
        # Verify loop device was created
        if not Path(loop_device).exists():
            raise RuntimeError(f"Failed to create loop device: {loop_device}")
            
        # Wait for partition device nodes to appear
        time.sleep(1)
        
        # Trigger partition rescanning
        self._run_command(["partprobe", loop_device])
        
        # Wait for partition device nodes and verify they exist
        time.sleep(1)
        for i in range(1, 3):  # We expect 2 partitions
            part_path = f"{loop_device}p{i}"
            if not Path(part_path).exists():
                raise RuntimeError(f"Expected partition not found: {part_path}")
                
        return loop_device

    def create_filesystems(self, loop_device: str):
        """Create filesystems on partitions."""
        self.logger.info("Creating filesystems")
        
        # Verify partition devices exist
        for i in range(1, 3):
            part_path = f"{loop_device}p{i}"
            if not Path(part_path).exists():
                raise RuntimeError(f"Partition device not found: {part_path}")
        
        # Create ESP
        self._run_command(["mkfs.fat", "-F32", f"{loop_device}p1"])
        
        # Create root filesystem
        self._run_command(["mkfs.ext4", "-F", f"{loop_device}p2"])

    def mount_root_partition(self, loop_device: str, mount_point: Path):
        """Mount the root partition."""
        self.logger.info(f"Mounting root partition to {mount_point}")
        
        mount_point.mkdir(parents=True, exist_ok=True)
        if not os.access(mount_point, os.W_OK):
            raise PermissionError(f"Cannot write to mount point: {mount_point}")
            
        self._run_command(["mount", f"{loop_device}p2", str(mount_point)])
        
        # Verify mount was successful
        if not self._is_mounted(mount_point):
            raise RuntimeError(f"Failed to mount {loop_device}p2 at {mount_point}")

    def _is_mounted(self, path: Path) -> bool:
        """Check if a path is a mountpoint."""
        try:
            return path.is_mount()
        except Exception:
            return False

    def _ensure_unmounted(self, mount_point: Path, max_retries: int = 3, delay: float = 3.0):
        """Ensure a mount point is fully unmounted."""
        for attempt in range(max_retries):
            if not self._is_mounted(mount_point):
                return True
            
            if attempt > 0:
                self.logger.info(f"Mount point still busy, attempt {attempt + 1}/{max_retries}")
                time.sleep(delay)
            
            try:
                self._run_command(["umount", "-f", str(mount_point)], check=False)
            except Exception as e:
                self.logger.warning(f"Unmount attempt failed: {e}")
                
        return not self._is_mounted(mount_point)

    def _ensure_loop_detached(self, loop_device: str, max_retries: int = 3, delay: float = 3.0):
        """Ensure a loop device is fully detached."""
        device_path = Path(loop_device)
        
        # Add initial delay after unmount
        time.sleep(1)
        
        for attempt in range(max_retries):
            # Check if device is already gone
            if not device_path.exists():
                return True
                
            if attempt > 0:
                self.logger.info(f"Loop device still busy, attempt {attempt + 1}/{max_retries}")
                time.sleep(delay)
            
            try:
                # Check if device is actually in use
                result = self._run_command(["losetup", "-j", loop_device], check=False)
                if not result.stdout.strip():
                    # Device is not in use, we can consider it detached
                    return True
                    
                # Force detach the device
                self._run_command(["losetup", "-d", loop_device], check=False)
                
            except Exception as e:
                self.logger.warning(f"Detach attempt failed: {e}")
        
        # Final check - is the device actually gone?
        return not bool(self._run_command(
            ["losetup", "-j", loop_device], 
            check=False
        ).stdout.strip())

    def populate_from_container(self, mount_point: Path, container: str = "ubuntu:22.04"):
        """Extract container rootfs and add it to the image."""
        self.logger.info(f"Populating root filesystem from container {container}")
        
        # Verify docker is running
        try:
            self._run_command(["docker", "info"], timeout=10)
        except Exception as e:
            raise RuntimeError("Docker daemon is not running") from e
        
        # Pull container
        self.logger.info(f"Pulling container {container}")
        self._run_command(["docker", "pull", container])
        
        # Create temporary container
        self.logger.info("Creating temporary container")
        container_id = self._run_command(["docker", "create", container]).stdout.strip()
        
        try:
            # Export container filesystem
            self.logger.info("Exporting container filesystem")
            rootfs_tar = mount_point / "rootfs.tar"
            with open(rootfs_tar, 'wb') as f:
                self._run_command(
                    ["docker", "export", container_id],
                    stdout=f,
                    binary_output=True
                )
            
            # Verify export succeeded
            if not rootfs_tar.exists() or rootfs_tar.stat().st_size == 0:
                raise RuntimeError("Failed to export container filesystem")
                
            # Extract rootfs
            self.logger.info("Extracting rootfs")
            self._run_command([
                "tar", "xf", str(rootfs_tar), "-C", str(mount_point)
            ])
            
            # Cleanup temporary tar
            rootfs_tar.unlink()
            
        finally:
            # Cleanup container
            self.logger.info("Cleaning up temporary container")
            self._run_command(["docker", "rm", container_id])

    def convert_to_qcow2(self, raw_image: Path) -> Path:
        """Convert raw image to qcow2 format."""
        self.logger.info(f"Converting {raw_image} to qcow2 format")
        
        qcow2_path = self.output_dir / f"{raw_image.stem}.qcow2"
        if qcow2_path.exists():
            self.logger.warning(f"Removing existing qcow2 image: {qcow2_path}")
            qcow2_path.unlink()
            
        self._run_command([
            "qemu-img", "convert", "-f", "raw", "-O", "qcow2",
            str(raw_image), str(qcow2_path)
        ])
        
        # Verify conversion
        if not qcow2_path.exists():
            raise RuntimeError(f"Failed to create qcow2 image: {qcow2_path}")
            
        return qcow2_path

    def generate_test_image(self, container: str = "ubuntu:22.04") -> Path:
        """Generate a complete test disk image."""
        # Check if image already exists
        container_safe_name = container.replace(":", "_").replace("/", "_")
        qcow2_path = self.output_dir / f"{container_safe_name}.qcow2"
        
        if qcow2_path.exists():
            self.logger.info(f"Test image {qcow2_path} already exists, skipping generation")
            return qcow2_path
            
        self.logger.info(f"Generating test image from {container}")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            mount_point = temp_dir_path / "mnt"
            
            # Change to temp directory to avoid busy mount point issues
            original_dir = os.getcwd()
            os.chdir(temp_dir)
            
            try:
                # Create and partition raw disk
                raw_image = self.create_raw_disk()
                self.partition_disk(raw_image)
                
                # Setup loop device
                loop_device = self.setup_loop_device(raw_image)
                try:
                    # Create filesystems
                    self.create_filesystems(loop_device)
                    
                    # Mount and populate root partition
                    self.mount_root_partition(loop_device, mount_point)
                    try:
                        self.populate_from_container(mount_point, container)
                    finally:
                        # Unmount with retries
                        self.logger.info(f"Unmounting {mount_point}")
                        if not self._ensure_unmounted(mount_point):
                            raise RuntimeError(f"Failed to unmount {mount_point} after multiple attempts")
                finally:
                    # Detach loop device with retries
                    self.logger.info(f"Detaching loop device {loop_device}")
                    if not self._ensure_loop_detached(loop_device):
                        raise RuntimeError(f"Failed to detach loop device {loop_device} after multiple attempts")
                
                # Return to original directory before conversion
                os.chdir(original_dir)
                
                # Convert to qcow2 with container-specific name
                qcow2_image = self.convert_to_qcow2(raw_image)
                final_path = self.output_dir / f"{container_safe_name}.qcow2"
                qcow2_image.rename(final_path)
                
                # Cleanup raw image
                raw_image.unlink()
                
                return final_path
                
            except Exception as e:
                self.logger.error(f"Failed during image generation: {str(e)}")
                os.chdir(original_dir)  # Ensure we return to original directory on error
                raise

def main():
    if os.geteuid() != 0:
        print("This script must be run as root")
        return 1

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('test_image_generator.log')
        ]
    )
    
    logger = logging.getLogger(__name__)
    
    # Generate test images from different base containers
    try:
        generator = TestImageGenerator()
    except CommandNotFoundException as e:
        logger.error(str(e))
        return 1
    
    test_images = [
        "ubuntu:22.04",
        "ubuntu:24.04",
        "debian:10",
        "debian:12",
        "fedora:latest",
        "alpine:3.10",
        "alpine:latest"
    ]
    
    success = True
    for container in test_images:
        try:
            image_path = generator.generate_test_image(container)
            logger.info(f"Successfully generated test image from {container}: {image_path}")
        except Exception as e:
            logger.error(f"Failed to generate image for {container}: {e}")
            success = False
            
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())