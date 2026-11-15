import unittest
import cv2
import numpy as np
from omfit.cli import align


class RegistrationTests(unittest.TestCase):
    def test_known_translation(self):
        rng = np.random.default_rng(42)
        im = rng.integers(0, 256, (400, 500, 3), dtype=np.uint8)
        im = cv2.GaussianBlur(im, (3, 3), 0)
        expected = np.array([[1.0, 0.0, 3.0], [0.0, 1.0, -2.0]])
        target = cv2.warpAffine(im, expected, (500, 400))
        a, mask, info = align(im, target)
        np.testing.assert_allclose(a, expected, atol=0.15)
        self.assertGreater(info["inliers"], 20)

    def test_blank_rejected(self):
        with self.assertRaises(ValueError):
            align(np.zeros((400, 400, 3), np.uint8), np.zeros((400, 400, 3), np.uint8))


if __name__ == "__main__":
    unittest.main()
