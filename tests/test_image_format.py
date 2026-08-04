import importlib.util
import logging
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "sbom-vm.py"
SPEC = importlib.util.spec_from_file_location("sbom_vm", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
sbom_vm = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sbom_vm)


class ImageFormatTest(unittest.TestCase):
    def setUp(self):
        setattr(sbom_vm, "logger", logging.getLogger("sbom-vm-test"))

    def test_qemu_detected_format_takes_precedence_over_img_suffix(self):
        mounter = sbom_vm.ImageMounter("firmware.img")
        mounter._run_command = Mock(
            return_value=subprocess.CompletedProcess(
                args=["qemu-img"],
                returncode=0,
                stdout="image: firmware.img\nfile format: qcow2\n",
            )
        )

        self.assertEqual(mounter._detect_image_format(), "qcow2")

    def test_img_falls_back_to_raw_when_qemu_cannot_identify_it(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "firmware.img"
            image_path.write_bytes(b"raw image content")
            mounter = sbom_vm.ImageMounter(str(image_path))
            mounter._run_command = Mock(
                side_effect=subprocess.CalledProcessError(
                    returncode=1,
                    cmd=["qemu-img", "info", str(image_path)],
                )
            )

            self.assertEqual(mounter._detect_image_format(), "raw")

    def test_img_falls_back_to_raw_when_qemu_is_unavailable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "firmware.IMG"
            image_path.write_bytes(b"raw image content")
            mounter = sbom_vm.ImageMounter(str(image_path))
            mounter._run_command = Mock(side_effect=FileNotFoundError("qemu-img"))

            self.assertEqual(mounter._detect_image_format(), "raw")

    def test_img_with_gzip_magic_still_falls_back_to_raw(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "firmware.img"
            image_path.write_bytes(b"\x1f\x8bcompressed image")
            mounter = sbom_vm.ImageMounter(str(image_path))
            mounter._run_command = Mock(
                side_effect=subprocess.CalledProcessError(
                    returncode=1,
                    cmd=["qemu-img", "info", str(image_path)],
                )
            )

            self.assertEqual(mounter._detect_image_format(), "raw")


if __name__ == "__main__":
    unittest.main()
