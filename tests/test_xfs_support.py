import importlib.util
from pathlib import Path
import logging
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, call


MODULE_PATH = Path(__file__).resolve().parents[1] / "sbom-vm.py"
SPEC = importlib.util.spec_from_file_location("sbom_vm", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
sbom_vm = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sbom_vm)


class XfsSupportTest(unittest.TestCase):
    def setUp(self):
        setattr(sbom_vm, "logger", logging.getLogger("sbom-vm-test"))
        self.mounter = sbom_vm.ImageMounter("dummy.qcow2")
        self.mounter.nbd_device = "/dev/nbd0"

    def test_selects_xfs_partition_as_linux_root_candidate(self):
        parted_output = """\
Model: Unknown (unknown)
Disk /dev/nbd0: 10.7GB
Partition Table: gpt
Number  Start   End     Size    File system  Name  Flags
 1      1049kB  538MB   537MB   fat32              boot, esp
 2      538MB   10.7GB  10.2GB  xfs
"""
        self.mounter._run_command = Mock(
            return_value=subprocess.CompletedProcess(
                args=["parted"], returncode=0, stdout=parted_output
            )
        )

        selected = self.mounter.find_filesystem_partition()

        self.assertEqual(selected, "/dev/nbd0p2")
        self.mounter._run_command.assert_called_once_with(
            ["parted", "-s", "/dev/nbd0", "print"]
        )

    def test_mounts_xfs_read_only_without_replaying_the_log(self):
        with tempfile.TemporaryDirectory() as mount_dir:
            self.mounter.mount_point = Path(mount_dir) / "image"
            self.mounter.find_filesystem_partition = Mock(
                return_value="/dev/nbd0p2"
            )
            self.mounter._run_command = Mock(
                side_effect=[
                    subprocess.CompletedProcess(
                        args=["blkid"], returncode=0, stdout="xfs\n"
                    ),
                    subprocess.CompletedProcess(
                        args=["mount"], returncode=0, stdout=""
                    ),
                ]
            )

            self.mounter.mount_filesystem()

            self.mounter._run_command.assert_has_calls(
                [
                    call(
                        [
                            "blkid",
                            "-o",
                            "value",
                            "-s",
                            "TYPE",
                            "/dev/nbd0p2",
                        ]
                    ),
                    call(
                        [
                            "mount",
                            "-t",
                            "xfs",
                            "-o",
                            "ro,norecovery",
                            "/dev/nbd0p2",
                            str(self.mounter.mount_point),
                        ]
                    ),
                ]
            )


if __name__ == "__main__":
    unittest.main()
