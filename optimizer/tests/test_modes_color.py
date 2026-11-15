import io
import json
import tempfile
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
from PIL import Image, ImageCms
from omfit.color import contact_sheet, rgb, SRGB
from omfit.model import Layout
from omfit.core import regularizer, search


class ModesAndColorTests(unittest.TestCase):
    def test_modes_bounds_and_disjoint_exports(self):
        for mode, n, limit in [("stock", 12, 5), ("hsl", 36, 7)]:
            layout = Layout(mode)
            lo, hi, trust = layout.bounds(2)
            self.assertTrue(np.all(hi[:n] == limit))
            self.assertEqual(len(lo), n + 10)
            x = layout.start([65, 2, -2, 2])
            x[:n] = 1
            profile = layout.recipe(x)
            scene = layout.adjustments(x)
            self.assertNotIn("custom_wb2", json.dumps(profile))
            self.assertNotIn("exposure_bias", json.dumps(profile))
            self.assertNotIn("saturation", json.dumps(scene))
            self.assertNotIn("tone_control", json.dumps(scene))
            self.assertEqual("hue" in profile["profile"], mode == "hsl")
            with tempfile.TemporaryDirectory() as t:
                path = Path(t) / "profile.oes"
                layout.oes(x, path)
                params = ET.parse(path).getroot().find("Parameters")
                self.assertIsNone(params.find("WhiteBalance"))
                self.assertIsNone(params.find("ExposureBias"))
                self.assertEqual(
                    params.find("ColorCreater2").get("HueValue"),
                    ",".join(["1" if mode == "hsl" else "0"] * 12),
                )
            initial = np.r_[np.zeros(layout.shared), [53, 0, 0, 0] * 2]
            R, z = regularizer(
                2, initial, 0.01, 0.03, 0.01, 0.01, wheel_channels=n // 12
            )
            self.assertEqual(R.shape[1], len(initial))
            self.assertTrue(np.isfinite(R).all())

    def test_comparison_uses_scoring_icc_path(self):
        with tempfile.TemporaryDirectory() as t:
            adobe = Path(
                "/Applications/OM Workspace.app/Contents/Resources/Profiles/AdobeRGB1998.icc"
            )
            if not adobe.exists():
                self.skipTest(
                    "Installed Adobe RGB profile required for wide-gamut fixture"
                )
            path = Path(t) / "adobe.tif"
            Image.new("RGB", (100, 100), (180, 30, 20)).save(
                path, icc_profile=adobe.read_bytes()
            )
            self.assertFalse(np.array_equal(rgb(path)[50, 50], [180, 30, 20]))
            sheet = Path(t) / "sheet.jpg"
            contact_sheet([(path, "target")], sheet)
            with Image.open(sheet) as im:
                self.assertEqual(im.info["icc_profile"], SRGB)
                np.testing.assert_allclose(
                    np.asarray(im)[200, 200], rgb(path)[50, 50], atol=3
                )

    def test_prefetch_keeps_solver_decisions(self):
        def run(batched):
            phases = []
            r = search(
                np.array([1, 0]),
                np.array([0, -5]),
                np.array([5, 5]),
                np.array([2, 2]),
                lambda x: np.array([x[0] ** 2 - 9.0, x[1] - 2.0]),
                np.zeros((0, 2)),
                np.zeros(0),
                max_iterations=4,
                prefetch=lambda vectors: phases.append([v.tolist() for v in vectors])
                if batched
                else None,
            )
            return r, phases

        a, _ = run(False)
        b, phases = run(True)
        self.assertEqual(a.history, b.history)
        np.testing.assert_array_equal(a.vector, b.vector)
        self.assertTrue(any(len(p) > 1 for p in phases))


if __name__ == "__main__":
    unittest.main()
