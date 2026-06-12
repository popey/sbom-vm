import importlib.util, pathlib, sys, unittest
spec = importlib.util.spec_from_file_location("sbom_vm", str(pathlib.Path(__file__).resolve().parents[1] / "sbom-vm.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
ImageMounter = getattr(mod, "ImageMounter")

class TestParseSize(unittest.TestCase):
    def setUp(self):
        # construct ImageMounter with dummy path to avoid requiring a real file
        self.im = ImageMounter(__file__)

    def test_gb(self):
        self.assertAlmostEqual(self.im.parse_size("1GB"), 1024.0)

    def test_mb(self):
        self.assertAlmostEqual(self.im.parse_size("512MB"), 512.0)

    def test_kb(self):
        self.assertAlmostEqual(self.im.parse_size("1024KB"), 1.0)

    def test_plain(self):
        self.assertAlmostEqual(self.im.parse_size("100"), 100.0)

    def test_invalid(self):
        self.assertEqual(self.im.parse_size("not-a-number"), 0)

if __name__=="__main__":
    unittest.main()
