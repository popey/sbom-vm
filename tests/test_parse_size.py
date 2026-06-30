import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "sbom-vm.py"
SPEC = importlib.util.spec_from_file_location("sbom_vm", MODULE_PATH)
sbom_vm = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sbom_vm)


class ParseSizeTest(unittest.TestCase):
    def setUp(self):
        self.mounter = sbom_vm.ImageMounter("dummy.qcow2")

    def test_parses_standard_units_as_mib(self):
        self.assertEqual(self.mounter.parse_size("1GB"), 1024)
        self.assertEqual(self.mounter.parse_size("512MB"), 512)
        self.assertEqual(self.mounter.parse_size("1024KB"), 1)

    def test_parses_parted_style_units(self):
        self.assertEqual(self.mounter.parse_size("1.5GB"), 1536)
        self.assertEqual(self.mounter.parse_size("2048kB"), 2)
        self.assertEqual(self.mounter.parse_size("2MiB"), 2)

    def test_rejects_invalid_values(self):
        self.assertEqual(self.mounter.parse_size(None), 0)
        self.assertEqual(self.mounter.parse_size("not-a-size"), 0)
        self.assertEqual(self.mounter.parse_size("12XB"), 0)


if __name__ == "__main__":
    unittest.main()
