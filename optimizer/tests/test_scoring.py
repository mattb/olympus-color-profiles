import tempfile
import unittest
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
from omfit.color import SRGB
from omfit.scoring import Scorer, resize_long
from omfit.cli import Evaluator
from omfit.model import Layout


class ScoringTests(unittest.TestCase):
    def test_full_resolution_mask_frozen_and_all_pixels_measured(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            rng = np.random.default_rng(32)
            data = cv2.GaussianBlur(
                rng.integers(30, 220, (360, 480, 3), dtype=np.uint8), (3, 3), 0
            )
            target = d / "target.tif"
            preview = d / "preview.tif"
            bad = d / "clipped.tif"
            Image.fromarray(data).save(target, icc_profile=SRGB)
            Image.fromarray(resize_long(data)).save(preview, icc_profile=SRGB)
            Image.new("RGB", (480, 360), "white").save(bad, icc_profile=SRGB)
            scorer = Scorer(preview, target)
            matrix = scorer.M.copy()
            report = scorer.full(
                target, {"baseline": target, "fitted": target, "clipped": bad}
            )
            a = report["metrics"]
            self.assertEqual(a["baseline"]["delta_e00"], a["fitted"]["delta_e00"])
            self.assertGreater(a["clipped"]["delta_e00"], a["baseline"]["delta_e00"])
            self.assertEqual(
                a["clipped"]["pixels_scored"], a["baseline"]["pixels_scored"]
            )
            self.assertGreater(a["baseline"]["pixels_scored"], 96 * 96)
            np.testing.assert_array_equal(scorer.M, matrix)

    def test_evaluator_only_requests_training_photos(self):
        class FakeRenderer:
            def __init__(self):
                self.seen = []

            def render_many(self, requests):
                self.seen.extend(p["id"] for p, s in requests)
                return [p["id"] for p, s in requests]

        class FakeScorer:
            def small(self, path):
                return np.ones((2, 2, 3)), {}

        train = [dict(id="train", raw_hash="a", rotate=0, resize=[10, 10])]
        renderer = FakeRenderer()
        layout = Layout("hsl")
        e = Evaluator(
            renderer,
            layout,
            train,
            {"train": FakeScorer(), "held": FakeScorer()},
            "gpu",
            2,
        )
        x = layout.start([53, 0, 0, 0])
        probe = x.copy()
        probe[0] = 1
        e.prefetch([x, probe])
        e(x)
        e(probe)
        self.assertTrue(renderer.seen)
        self.assertEqual(set(renderer.seen), {"train"})
        self.assertEqual(len(e.requested), 2)


if __name__ == "__main__":
    unittest.main()
