import unittest
import os
import importlib.util
from pathlib import Path

# Load sbom-vm.py as a module by file location (filename contains a dash)
MODULE_PATH = Path(__file__).resolve().parents[1] / 'sbom-vm.py'

spec = importlib.util.spec_from_file_location('sbom_vm_module', str(MODULE_PATH))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

ImageMounter = module.ImageMounter

class TestParseSize(unittest.TestCase):
    def setUp(self):
        self.m = ImageMounter('dummy.img')

    def test_gb(self):
        self.assertAlmostEqual(self.m.parse_size('1GB'), 1024.0)
        self.assertAlmostEqual(self.m.parse_size('1.5GB'), 1536.0)

    def test_mb_kb(self):
        self.assertAlmostEqual(self.m.parse_size('512MB'), 512.0)
        self.assertAlmostEqual(self.m.parse_size('1024KB'), 1.0)

    def test_plain_number(self):
        self.assertAlmostEqual(self.m.parse_size('2048'), 2048.0)

    def test_invalid(self):
        self.assertEqual(self.m.parse_size('not-a-number'), 0)

if __name__ == '__main__':
    unittest.main()
