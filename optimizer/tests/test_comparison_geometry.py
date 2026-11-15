from pathlib import Path
import tempfile
import unittest
import cv2
import numpy as np
from PIL import Image
from omfit.color import SRGB, contact_sheet
from omfit.scoring import Scorer


class ComparisonGeometryTests(unittest.TestCase):
    def test_frozen_reference_geometry_and_srgb_array_export(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            a = np.zeros((200, 300, 3), np.uint8)
            a[40:70, 60:90] = [180, 25, 50]
            path = d / "native.tif"
            Image.fromarray(a).save(path, icc_profile=SRGB)
            scorer = Scorer.__new__(Scorer)
            scorer.baseline_small_shape = (200, 300)
            scorer.target_small = np.zeros((180, 250, 3), np.uint8)
            scorer.M = np.array([[1.0, 0.0, -20.0], [0.0, 1.0, -10.0]])
            got = scorer.comparison_rgb(path)
            expected = cv2.warpAffine(a, scorer.M, (250, 180))
            np.testing.assert_array_equal(got, expected)
            sheet = d / "paired.jpg"
            contact_sheet([(got, "Registered native")], sheet)
            with Image.open(sheet) as im:
                self.assertEqual(im.info["icc_profile"], SRGB)

    def test_untyped_arrays_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(ValueError):
                contact_sheet(
                    [(np.zeros((10, 10, 3), float), "bad")], Path(t) / "x.jpg"
                )


if __name__ == "__main__":
    unittest.main()
