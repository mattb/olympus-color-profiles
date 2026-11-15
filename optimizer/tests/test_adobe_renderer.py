import io
import unittest
import numpy as np
from PIL import Image
from omfit.adobe_renderer import canonical_preview, _equivalent, AdobeRenderer
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from types import SimpleNamespace


class AdobePreviewTests(unittest.TestCase):
    def test_optional_lcms_is_not_loaded_at_import(self):
        import importlib
        import omfit.adobe_renderer as module
        with patch('ctypes.util.find_library', return_value=None):
            importlib.reload(module)
            with self.assertRaisesRegex(RuntimeError, 'brew install little-cms2'):
                module.gray_profile_bytes()

    def fixture(self, value=128):
        b = io.BytesIO()
        Image.new("RGB", (8, 6), (value,) * 3).save(b, format="JPEG")
        return b.getvalue(), {
            "SubIFD2:PreviewColorSpace": "Gray Gamma 2.2",
            "SubIFD2:PreviewApplicationName": "Adobe DNG Converter",
            "SubIFD2:ImageWidth": 8,
            "SubIFD2:ImageHeight": 6,
        }

    def test_gray_is_converted_not_tagged(self):
        jpeg, md = self.fixture()
        a = np.asarray(canonical_preview(jpeg, md))
        self.assertGreater(int(a[0, 0, 0]), 128)
        self.assertLess(int(a[0, 0, 0]), 132)
        self.assertLessEqual(int(a.max()) - int(a.min()), 1)

    def test_unknown_color_space_and_wrong_preview_rejected(self):
        jpeg, md = self.fixture()
        for key, value in [
            ("SubIFD2:PreviewColorSpace", "unknown"),
            ("SubIFD2:PreviewApplicationName", "Olympus"),
            ("SubIFD2:ImageWidth", 9),
        ]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                canonical_preview(jpeg, dict(md, **{key: value}))

    def test_portrait_orientation_comes_from_dng(self):
        jpeg, md = self.fixture()
        self.assertEqual(
            canonical_preview(jpeg, dict(md, **{"IFD0:Orientation": 8})).size, (6, 8)
        )
        with self.assertRaises(ValueError):
            canonical_preview(jpeg, dict(md, **{"IFD0:Orientation": 99}))

    def test_scalar_readback_comparison(self):
        self.assertTrue(_equivalent("+2.00", 2))
        self.assertTrue(_equivalent("False", False))
        self.assertFalse(_equivalent("False", True))
        self.assertFalse(_equivalent(None, 0))


class AdobeDiskTests(unittest.TestCase):
    def test_low_disk_fails_before_raw_copy_or_converter(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            converter = root / "converter"
            converter.write_bytes(b"fixture")
            raw = root / "photo.ORF"
            raw.write_bytes(b"raw")
            renderer = AdobeRenderer(root / "cache", root / "work", converter=converter)
            with (
                patch(
                    "omfit.adobe_renderer.shutil.disk_usage",
                    return_value=SimpleNamespace(free=1),
                ),
                patch("omfit.adobe_renderer.shutil.copy2") as copy,
            ):
                with self.assertRaisesRegex(RuntimeError, "Insufficient disk space"):
                    renderer.render(raw, {"Exposure2012": 0})
                copy.assert_not_called()
            self.assertEqual(list((root / "cache").iterdir()), [])
