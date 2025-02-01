# sbom-vm

Generate Software Bill of Materials (SBOM) from virtual machine disk images, without booting the VM.

In its current state, this script leverages common Linux utilities (gdisk, qemu-nbd, and others) to present partitions to the host in a read-only manner, such that [Syft](https://github.com/anchore/syft) running on the host can read the files to generate an SBOM.

## Features

* Read-only mounting of VM disk images via qemu-nbd
* Supports multiple VM disk formats (qcow2, vmdk)
* Automatic detection and mounting of common filesystems:
  * Windows (NTFS)
  * Linux (ext4)
  * macOS (HFS+, APFS)
  * BSD (ZFS)
* Safe, non-destructive SBOM generation using Syft

## Background

[Syft](https://github.com/anchore/syft) is a general-purpose SBOM generator, optimised for creating SBOMs from containers, directories and repositories. 

Some users scan entire filesystems. This can be computationally intensive when a large number of files are present. It can also generate very large SBOM documents. In some reported cases, running Syft inside the VM will cause it to exhaust all the available memory, and get killed by the kernel OOM (Out Of Memory) killer, failing to create the SBOM.

Will Murphy collated some conversations from around the community on the [Anchore Community Discourse](https://anchore.com/discourse) in a topic titled "[Improvements to scanning whole machine](https://anchorecommunity.discourse.group/t/improvements-to-scanning-whole-machine/301?u=popey)".

## Project Goal

The goal of this project is to prototype building an SBOM from a disk image from outside the running VM. The lessons from this could be used to improve or extend Syft, or add features to [stereoscope](https://github.com/anchore/stereoscope), the library used by Syft to inspect containers.

A side-benefit might be to enable those Syft users who need to scan VM disk images now, to do so in the interim, until contributions to Syft and/or Stereoscope bake this in.

## Project Scope

Here's what I envisage for an MVP (Minimum Viable Product), to generate SBOMs from VM disk images.

### MVP

* Examine common disk image formats (raw, ami, qcow2, vmdk)
* Mount common partition types (ntfs, hfsplus', apfs, ext4, vfat, zfs)
* Launch Syft with appropriate options to generate an SBOM

### Out of scope

* Encrypted disk images or partitions

## Using sbom-vm

Note: This has so far only been tested on my Ubuntu 24.04 workstation.

## Pre-requisites

The following packages are required:

* [Syft](https://github.com/anchore/syft) - Generate SBOM
* qemu-utils - For mounting disk images
* gzip - Unpack zipped ami
* gdisk - For GPT partition handling
* fdisk - For partition analysis
* parted - For detailed partition information
* util-linux - For mount/umount commands
* ntfs-3g - For Windows NTFS filesystem support
* hfsprogs - For MacOS HFS+ filesystem support
* apfs-dkms & apfsprogs - For MacOS APFS filesystem support

On Ubuntu 24.04 these can be installed via:

```bash
$ snap install syft
$ sudo apt install qemu-utils gdisk fdisk parted util-linux ntfs-3g hfsprogs apfs-dkms apfsprogs
```

## Installation

* Clone the repo, or grab the single python script in it

## Running

* Run the python script with a disk image as the only parameter

## Example output

### Ubuntu 24.04 qcow2 image

```
$ sudo sbom-vm.py test_images/ubuntu_22.04.qcow2
2025-02-01 18:45:59,394 - INFO - Loading NBD kernel module
2025-02-01 18:46:00,405 - INFO - Detecting format of /home/popey/sbom-vm/test_images/ubuntu_22.04.qcow2
2025-02-01 18:46:00,409 - INFO - qemu-img detected format: qcow2
2025-02-01 18:46:00,409 - INFO - Connecting image /home/popey/sbom-vm/test_images/ubuntu_22.04.qcow2 to NBD device
2025-02-01 18:46:01,426 - INFO - Analyzing partitions
2025-02-01 18:46:01,438 - INFO - Found EFI system partition /dev/nbd0p1
2025-02-01 18:46:01,438 - INFO - Found usable partition /dev/nbd0p2 of type ext4
2025-02-01 18:46:01,438 - INFO - Found filesystem partition(s): /dev/nbd0p1 (fat32), /dev/nbd0p2 (ext4)
2025-02-01 18:46:01,438 - INFO - Selected partition /dev/nbd0p2 (priority: 3, size: 547MB)
2025-02-01 18:46:01,442 - INFO - Mounting ext4 filesystem
2025-02-01 18:46:01,450 - INFO - Generating SBOM for mounted filesystem at /mnt/image_analysis
2025-02-01 18:46:01,451 - INFO - Filesystem type: ext4
2025-02-01 18:46:03,679 - INFO - SBOM generated: 20250201_184601_sbom_ubuntu_22.04_nbd0p2_ext4.json
2025-02-01 18:46:03,679 - INFO - Starting cleanup
2025-02-01 18:46:03,684 - INFO - Exporting ZFS pool default
2025-02-01 18:46:03,700 - INFO - Unmounting /mnt/image_analysis
2025-02-01 18:46:03,714 - INFO - Disconnecting NBD device
2025-02-01 18:46:03,717 - INFO - Removing NBD kernel module
2025-02-01 18:46:03,719 - INFO - Removing temporary directory: /tmp/sbomvm_ch80d0zx
```

### Windows 10 QEMU qcow2 image 

```
$  sudo sbom-vm.py /VMs/windows-10/disk.qcow2
2025-02-01 13:47:10,405 - INFO - Loading NBD kernel module
2025-02-01 13:47:11,408 - INFO - Detecting format of /VMs/windows-10/disk.qcow2
2025-02-01 13:47:11,415 - INFO - qemu-img detected format: qcow2
2025-02-01 13:47:11,415 - INFO - Connecting image /VMs/windows-10/disk.qcow2 to NBD device
2025-02-01 13:47:12,440 - INFO - Analyzing partitions
2025-02-01 13:47:12,456 - INFO - Skipping system partition /dev/nbd0p1
2025-02-01 13:47:12,456 - INFO - Found EFI system partition /dev/nbd0p2
2025-02-01 13:47:12,456 - INFO - Skipping system partition /dev/nbd0p3
2025-02-01 13:47:12,456 - INFO - Found usable partition /dev/nbd0p4 of type ntfs
2025-02-01 13:47:12,456 - INFO - Found filesystem partition(s): /dev/nbd0p2 (fat32), /dev/nbd0p4 (ntfs)
2025-02-01 13:47:12,456 - INFO - Selected partition /dev/nbd0p4 (priority: 2, size: 68.2GB)
2025-02-01 13:47:12,461 - INFO - Mounting ntfs filesystem
2025-02-01 13:47:12,482 - INFO - Generating SBOM for mounted filesystem at /mnt/image_analysis
2025-02-01 13:47:12,482 - INFO - Filesystem type: ntfs
2025-02-01 13:47:12,576 - INFO - Inspecting mount point contents:
2025-02-01 13:47:12,586 - INFO - Mount points in system:
2025-02-01 13:47:12,592 - INFO - Running syft with scope limited to mount point
2025-02-01 15:05:26,375 - INFO - SBOM generated: 20250201_133444_disk_nbd0p4_ntfs.json
2025-02-01 15:05:26,375 - INFO - Starting cleanup
2025-02-01 15:05:26,382 - INFO - Exporting ZFS pool default
2025-02-01 15:05:26,398 - INFO - Unmounting /mnt/image_analysis
2025-02-01 15:05:27,247 - INFO - Disconnecting NBD device
2025-02-01 15:05:27,259 - INFO - Removing NBD kernel module
$ 
```

## Test images

If you don't have any disk images handy, use the `generate-test-images.py` script which creates some test virtual machine disk images based on container content from docker.

```
sudo /home/popey/sbom-from-vm-image/generate-test-images.py
2025-02-01 19:18:41,993 - INFO - Creating output directory at /home/popey/sbom-vm/test_images
2025-02-01 19:18:41,993 - INFO - Generating test image from ubuntu:22.04
2025-02-01 19:18:41,993 - INFO - Creating 1024MB raw disk image at /home/popey/sbom-vm/test_images/disk_oo09o9fi.raw
2025-02-01 19:18:42,039 - INFO - Creating partition table on /home/popey/sbom-vm/test_images/disk_oo09o9fi.raw
2025-02-01 19:18:44,110 - INFO - Setting up loop device for /home/popey/sbom-vm/test_images/disk_oo09o9fi.raw
2025-02-01 19:18:46,136 - INFO - Creating filesystems
2025-02-01 19:18:46,171 - INFO - Mounting root partition to /tmp/tmpbe37knv6/mnt
2025-02-01 19:18:46,180 - INFO - Populating root filesystem from container ubuntu:22.04
2025-02-01 19:18:46,228 - INFO - Pulling container ubuntu:22.04
2025-02-01 19:18:47,142 - INFO - Creating temporary container
2025-02-01 19:18:47,220 - INFO - Exporting container filesystem
2025-02-01 19:18:47,329 - INFO - Extracting rootfs
2025-02-01 19:18:47,428 - INFO - Cleaning up temporary container
2025-02-01 19:18:47,452 - INFO - Unmounting /tmp/tmpbe37knv6/mnt
2025-02-01 19:18:47,675 - INFO - Detaching loop device /dev/loop278
2025-02-01 19:18:48,682 - INFO - Converting /home/popey/sbom-vm/test_images/disk_oo09o9fi.raw to qcow2 format
2025-02-01 19:18:48,752 - INFO - Successfully generated test image from ubuntu:22.04: /home/popey/sbom-vm/test_images/ubuntu_22.04.qcow2
2025-02-01 19:18:48,752 - INFO - Generating test image from alpine:latest
2025-02-01 19:18:48,752 - INFO - Creating 1024MB raw disk image at /home/popey/sbom-vm/test_images/disk_wnvt4c0a.raw
2025-02-01 19:18:48,796 - INFO - Creating partition table on /home/popey/sbom-vm/test_images/disk_wnvt4c0a.raw
2025-02-01 19:18:50,894 - INFO - Setting up loop device for /home/popey/sbom-vm/test_images/disk_wnvt4c0a.raw
2025-02-01 19:18:52,927 - INFO - Creating filesystems
2025-02-01 19:18:52,966 - INFO - Mounting root partition to /tmp/tmpuxmynvaz/mnt
2025-02-01 19:18:52,975 - INFO - Populating root filesystem from container alpine:latest
2025-02-01 19:18:53,026 - INFO - Pulling container alpine:latest
2025-02-01 19:18:53,906 - INFO - Creating temporary container
2025-02-01 19:18:54,059 - INFO - Exporting container filesystem
2025-02-01 19:18:54,087 - INFO - Extracting rootfs
2025-02-01 19:18:54,106 - INFO - Cleaning up temporary container
2025-02-01 19:18:54,128 - INFO - Unmounting /tmp/tmpuxmynvaz/mnt
2025-02-01 19:18:54,183 - INFO - Detaching loop device /dev/loop279
2025-02-01 19:18:55,190 - INFO - Converting /home/popey/sbom-vm/test_images/disk_wnvt4c0a.raw to qcow2 format
2025-02-01 19:18:55,221 - INFO - Successfully generated test image from alpine:latest: /home/popey/sbom-vm/test_images/alpine_latest.qcow2
```

Scan generated images:

```
$ for f in $(ls -1 test_images/*.qcow2); do sudo /home/popey/sbom-vm/sbom-vm.py  /home/popey/sbom-vm/$f; done
2025-02-01 19:22:55,833 - INFO - Loading NBD kernel module
2025-02-01 19:22:56,842 - INFO - Detecting format of /home/popey/sbom-vm/test_images/alpine_latest.qcow2
2025-02-01 19:22:56,847 - INFO - qemu-img detected format: qcow2
2025-02-01 19:22:56,848 - INFO - Connecting image /home/popey/sbom-vm/test_images/alpine_latest.qcow2 to NBD device
2025-02-01 19:22:57,872 - INFO - Analyzing partitions
2025-02-01 19:22:57,885 - INFO - Found EFI system partition /dev/nbd0p1
2025-02-01 19:22:57,885 - INFO - Found usable partition /dev/nbd0p2 of type ext4
2025-02-01 19:22:57,885 - INFO - Found filesystem partition(s): /dev/nbd0p1 (fat32), /dev/nbd0p2 (ext4)
2025-02-01 19:22:57,885 - INFO - Selected partition /dev/nbd0p2 (priority: 3, size: 547MB)
2025-02-01 19:22:57,889 - INFO - Mounting ext4 filesystem
2025-02-01 19:22:57,896 - INFO - Generating SBOM for mounted filesystem at /mnt/image_analysis
2025-02-01 19:22:57,896 - INFO - Filesystem type: ext4
2025-02-01 19:22:59,229 - INFO - SBOM generated: 20250201_192257_sbom_alpine_latest_nbd0p2_ext4.json
2025-02-01 19:22:59,229 - INFO - Starting cleanup
2025-02-01 19:22:59,234 - INFO - Exporting ZFS pool default
2025-02-01 19:22:59,250 - INFO - Unmounting /mnt/image_analysis
2025-02-01 19:22:59,282 - INFO - Disconnecting NBD device
2025-02-01 19:22:59,286 - INFO - Removing NBD kernel module
2025-02-01 19:22:59,639 - INFO - Removing temporary directory: /tmp/sbomvm_2kz4k6yk
2025-02-01 19:22:59,684 - INFO - Loading NBD kernel module
2025-02-01 19:23:00,707 - INFO - Detecting format of /home/popey/sbom-vm/test_images/ubuntu_22.04.qcow2
2025-02-01 19:23:00,712 - INFO - qemu-img detected format: qcow2
2025-02-01 19:23:00,712 - INFO - Connecting image /home/popey/sbom-vm/test_images/ubuntu_22.04.qcow2 to NBD device
2025-02-01 19:23:01,726 - INFO - Analyzing partitions
2025-02-01 19:23:01,740 - INFO - Found EFI system partition /dev/nbd0p1
2025-02-01 19:23:01,740 - INFO - Found usable partition /dev/nbd0p2 of type ext4
2025-02-01 19:23:01,740 - INFO - Found filesystem partition(s): /dev/nbd0p1 (fat32), /dev/nbd0p2 (ext4)
2025-02-01 19:23:01,740 - INFO - Selected partition /dev/nbd0p2 (priority: 3, size: 547MB)
2025-02-01 19:23:01,744 - INFO - Mounting ext4 filesystem
2025-02-01 19:23:01,753 - INFO - Generating SBOM for mounted filesystem at /mnt/image_analysis
2025-02-01 19:23:01,753 - INFO - Filesystem type: ext4
2025-02-01 19:23:03,937 - INFO - SBOM generated: 20250201_192301_sbom_ubuntu_22.04_nbd0p2_ext4.json
2025-02-01 19:23:03,937 - INFO - Starting cleanup
2025-02-01 19:23:03,941 - INFO - Exporting ZFS pool default
2025-02-01 19:23:03,957 - INFO - Unmounting /mnt/image_analysis
2025-02-01 19:23:03,987 - INFO - Disconnecting NBD device
2025-02-01 19:23:03,992 - INFO - Removing NBD kernel module
2025-02-01 19:23:04,293 - INFO - Removing temporary directory: /tmp/sbomvm_ozumw2qz
```

Scan the SBOMs for vulnerabilities.

```
$ for f in 20250201_192*.json; do grype $f; done
 ✔ Scanned for vulnerabilities     [2 vulnerability matches]
   ├── by severity: 0 critical, 0 high, 2 medium, 0 low, 0 negligible
   └── by status:   0 fixed, 2 not-fixed, 0 ignored
NAME        INSTALLED  FIXED-IN  TYPE  VULNERABILITY   SEVERITY
libcrypto3  3.3.2-r4             apk   CVE-2024-13176  Medium
libssl3     3.3.2-r4             apk   CVE-2024-13176  Medium
 ✔ Scanned for vulnerabilities     [60 vulnerability matches]
   ├── by severity: 0 critical, 0 high, 23 medium, 30 low, 7 negligible
   └── by status:   0 fixed, 60 not-fixed, 0 ignored
NAME                INSTALLED                 FIXED-IN  TYPE  VULNERABILITY   SEVERITY
coreutils           8.32-4.1ubuntu1.2                   deb   CVE-2016-2781   Low
gcc-12-base         12.3.0-1ubuntu1~22.04               deb   CVE-2023-4039   Medium
gcc-12-base         12.3.0-1ubuntu1~22.04               deb   CVE-2022-27943  Low
gpgv                2.2.27-3ubuntu2.1                   deb   CVE-2022-3219   Low
libc-bin            2.35-0ubuntu3.8                     deb   CVE-2025-0395   Medium
libc-bin            2.35-0ubuntu3.8                     deb   CVE-2016-20013  Negligible
libc6               2.35-0ubuntu3.8                     deb   CVE-2025-0395   Medium
libc6               2.35-0ubuntu3.8                     deb   CVE-2016-20013  Negligible
libgcc-s1           12.3.0-1ubuntu1~22.04               deb   CVE-2023-4039   Medium
libgcc-s1           12.3.0-1ubuntu1~22.04               deb   CVE-2022-27943  Low
libgcrypt20         1.9.4-3ubuntu3                      deb   CVE-2024-2236   Low
...
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.
