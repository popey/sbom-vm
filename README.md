# sbom-vm

Generate Software Bill of Materials (SBOM) from virtual machine disk images, without booting the VM.

In its current state, this script leverages common Linux utilities (gdisk, qemu-nbd, and others) to present partitions to the host in a read-only manner, such that [Syft](https://github.com/anchore/syft) running on the host can read the files to generate an SBOM.

## Features

* Read-only mounting of VM disk images via qemu-nbd
* Supports multiple VM disk formats (qcow2, vmdk)
* Automatic detection and mounting of common filesystems:
  * Windows (NTFS)
  * Linux (ext4, ZFS, BTRFS)
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
* Mount common partition types (ntfs, hfsplus, apfs, ext4, vfat, zfs)
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
* zfsutils-linux - For ZFS filesystem support

On Ubuntu 24.04 these can be installed via:

```bash
$ snap install syft
$ sudo apt install qemu-utils gdisk fdisk parted util-linux ntfs-3g hfsprogs apfs-dkms apfsprogs zfsutils-linux
```

## Installation

* Clone the repo, or grab the single python script in it

## Running

* Run the python script with a disk image as the only parameter

## Example output

### Ubuntu 24.04 qcow2 image with ext4

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
2025-02-01 18:46:03,684 - INFO - Unmounting /mnt/image_analysis
2025-02-01 18:46:03,714 - INFO - Disconnecting NBD device
2025-02-01 18:46:03,717 - INFO - Removing NBD kernel module
2025-02-01 18:46:03,719 - INFO - Removing temporary directory: /tmp/sbomvm_ch80d0zx
```

### Ubuntu 24.04 qcow2 image with ZFS

```
$ sudo sbom-vm.py test_images/ubuntu_22.04_zfs.qcow2
2025-02-02 15:27:12,157 - INFO - Loading NBD kernel module
2025-02-02 15:27:13,159 - INFO - Detecting format of /home/alan/Temp/sbom-vm/test_images/ubuntu_22.04_zfs.qcow2
2025-02-02 15:27:13,163 - INFO - qemu-img detected format: qcow2
2025-02-02 15:27:13,163 - INFO - Connecting image /home/alan/Temp/sbom-vm/test_images/ubuntu_22.04_zfs.qcow2 to NBD device
2025-02-02 15:27:14,184 - INFO - Analyzing partitions
2025-02-02 15:27:14,195 - INFO - Found usable partition /dev/nbd0p1 of type zfs_member (via blkid)
2025-02-02 15:27:14,195 - INFO - Found filesystem partition(s): /dev/nbd0p1 (zfs_member)
2025-02-02 15:27:14,195 - INFO - Selected partition /dev/nbd0p1 (priority: 1, size: 1072MB)
2025-02-02 15:27:14,196 - INFO - Mounting zfs_member filesystem
2025-02-02 15:27:14,196 - INFO - Attempting to import ZFS pool from /dev/nbd0p1
2025-02-02 15:27:14,205 - INFO - Found ZFS pool: sbomtmp
2025-02-02 15:27:14,226 - INFO - Generating SBOM for mounted filesystem at /mnt/image_analysis
2025-02-02 15:27:14,226 - INFO - Filesystem type: zfs_member
2025-02-02 15:27:17,462 - INFO - SBOM generated: 20250202_152714_sbom_ubuntu_22.04_zfs_nbd0p1_zfs_member.json
2025-02-02 15:27:17,462 - INFO - Starting cleanup
2025-02-02 15:27:17,465 - INFO - Exporting ZFS pool sbomtmp
2025-02-02 15:27:17,479 - INFO - Disconnecting NBD device
2025-02-02 15:27:17,483 - INFO - Removing NBD kernel module
2025-02-02 15:27:17,485 - INFO - Removing temporary directory: /tmp/sbomvm_41rnscs4
```

## Test images

If you don't have any disk images handy, use the `generate-test-images.py` script which creates some test virtual machine disk images based on container content from docker. The script supports creating test images with various filesystems including ext4 and ZFS.

```
$ sudo ./generate-test-images.py
2025-02-02 15:23:13,365 - INFO - Creating output directory at /home/alan/Temp/sbom-vm/test_images
2025-02-02 15:23:13,365 - INFO - Generating zfs test image from ubuntu:22.04
2025-02-02 15:23:13,366 - INFO - Creating 1024MB raw disk image at /home/alan/Temp/sbom-vm/test_images/disk_2jucd3yv.raw
2025-02-02 15:23:13,375 - INFO - Creating partition table for zfs on /home/alan/Temp/sbom-vm/test_images/disk_2jucd3yv.raw
2025-02-02 15:23:14,950 - INFO - Setting up loop device for /home/alan/Temp/sbom-vm/test_images/disk_2jucd3yv.raw
2025-02-02 15:23:16,983 - INFO - Creating zfs filesystem
2025-02-02 15:23:17,042 - INFO - Mounting root partition to /tmp/tmpsfp6mhg0/mnt
2025-02-02 15:23:17,043 - INFO - Populating root filesystem from container ubuntu:22.04
2025-02-02 15:23:17,355 - INFO - Pulling container ubuntu:22.04
2025-02-02 15:23:18,286 - INFO - Creating temporary container
2025-02-02 15:23:18,364 - INFO - Exporting container filesystem
2025-02-02 15:23:19,000 - INFO - Extracting rootfs
2025-02-02 15:23:19,344 - INFO - Cleaning up temporary container
2025-02-02 15:23:19,370 - INFO - Cleaning up ZFS pool sbomtmp
2025-02-02 15:23:19,479 - INFO - Detaching loop device /dev/loop154
2025-02-02 15:23:20,485 - INFO - Converting /home/alan/Temp/sbom-vm/test_images/disk_2jucd3yv.raw to qcow2 format
2025-02-02 15:23:20,564 - INFO - Successfully generated zfs test image: /home/alan/Temp/sbom-vm/test_images/ubuntu_22.04_zfs.qcow2
```

Generating an SBOM for every generated image is easiest with a simple loop:

```
for f in $(ls -1 $PWD/test_images/*.qcow2); do echo $f ; sudo $PWD/sbom-vm.py $f; done
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.