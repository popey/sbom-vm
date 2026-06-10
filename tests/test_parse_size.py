import unittest
from importlib.machinery import SourceFileLoader

# Load the sbom-vm script as a module (filename contains a hyphen)
module = SourceFileLoader("sbom_vm", "sbom-vm.py").load_module()
ImageMounter = module.ImageMounter

class TestParseSize(unittest.TestCase):
    def setUp(self):
        self.m = ImageMounter("/tmp/fake.img")

    def test_gb(self):
        self.assertEqual(self.m.parse_size('10GB'), 10 * 1024)
        self.assertEqual(self.m.parse_size('1gb '), 1 * 1024)

    def test_mb(self):
        self.assertEqual(self.m.parse_size('512MB'), 512)

    def test_kb(self):
        self.assertAlmostEqual(self.m.parse_size('1024KB'), 1.0)

    def test_plain_number(self):
        self.assertEqual(self.m.parse_size('42'), 42.0)

    def test_invalid(self):
        self.assertEqual(self.m.parse_size('nothing'), 0)

if __name__ == '__main__':
    unittest.main()
