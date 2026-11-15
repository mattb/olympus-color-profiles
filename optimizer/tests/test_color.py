import io
import struct
import unittest
from PIL import Image, ImageCms
from omfit.color import SRGB, _stable_srgb_profile


class StableColorTests(unittest.TestCase):
    def test_export_profile_has_fixed_valid_date_and_unassigned_id(self):
        self.assertEqual(struct.unpack_from(">6H", SRGB, 24), (2000, 1, 1, 0, 0, 0))
        self.assertEqual(SRGB[84:100], bytes(16))
        self.assertEqual(SRGB, _stable_srgb_profile())

    def test_canonical_header_does_not_change_transform(self):
        im = Image.new("RGB", (10, 10), (123, 43, 210))
        original = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
        stable = ImageCms.ImageCmsProfile(io.BytesIO(SRGB))
        a = ImageCms.profileToProfile(im, original, original, outputMode="RGB")
        b = ImageCms.profileToProfile(im, original, stable, outputMode="RGB")
        self.assertEqual(a.tobytes(), b.tobytes())


if __name__ == "__main__":
    unittest.main()
