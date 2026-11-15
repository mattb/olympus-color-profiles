import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import xml.etree.ElementTree as ET
import numpy as np
from omfit.mono_model import FILTER_STATES, MonoLayout
from omfit.renderer import verify_readback


def report_for(settings):
    p = settings["profile"]
    f = p["color_filter"]
    o = settings["raw_overrides"]
    from omfit.mono_model import FILTER_ROTATIONS

    c = dict(
        custom_wb2=dict(status=0, kelvin=5300, ab_adjust=0, gm_adjust=0),
        exposure_bias=dict(status=0, numerator=0, denominator=3),
        tone_control=dict(
            status=0, mode=1, bright=o["tone_control"][1], dark=o["tone_control"][2]
        ),
        tone_control_with_mid=dict(status=0, mode=1, bright=0, dark=0, mid=0),
        white_balance_mode=dict(status=0, value=4),
        color_space_mode=dict(status=0, value=1),
    )
    for ch in ("saturation", "hue", "luminance"):
        c[ch] = dict(status=0, mode=0, values=[0] * 12)
    m = dict(
        active_processing_family="native_monochrome_profile",
        get_parameters_status=0,
        finishing_mode=dict(status=0, value=2),
        monochrome=dict(
            status=0,
            mode=2,
            radial=f["strength"],
            rotation=FILTER_ROTATIONS[f["color"]],
            filter_color=f["color"],
            strength=f["strength"],
        ),
    )
    for key in ("contrast", "sharpness"):
        m[key] = dict(status=0, mode=1, value=p[key], adjust=0)
    for key, value in (
        ("grain", 0),
        ("toning", 2),
        ("creative_shading", 0),
        ("legacy_monochro_shading", 0),
    ):
        m[key] = dict(status=0, mode=2, value=value)
    return dict(
        renderer_protocol="omrender-native/2",
        backend=dict(used="gpu"),
        bits=8,
        current_parameters=c,
        mono_parameters=m,
        profile_kind="stock_pen_f_mono",
        mono_creative_shading_stage=dict(applied=False, value=0),
    )


class MonoModelTests(unittest.TestCase):
    def test_all_filters_round_trip_without_photo_settings(self):
        layout = MonoLayout()
        pair = dict(rotate=0, resize=[800, 600])
        self.assertEqual(len(set(FILTER_STATES)), 25)
        with TemporaryDirectory() as d:
            for index, (color, strength) in enumerate(FILTER_STATES):
                v = layout.start([53, 0, 0, 0])
                v[:4] = [index, 1, -2, 3]
                s = layout.settings(pair, v, "gpu")
                self.assertEqual(
                    s["profile"]["color_filter"], dict(color=color, strength=strength)
                )
                self.assertEqual(verify_readback(s, report_for(s)), "gpu")
                recipe = layout.recipe(v)
                scene = layout.adjustments(v)
                self.assertNotIn("custom_wb2", json.dumps(recipe))
                self.assertNotIn("exposure_bias", json.dumps(recipe))
                self.assertNotIn("color_filter", json.dumps(scene))
                path = Path(d) / "profile.oes"
                layout.oes(v, path)
                params = ET.parse(path).getroot().find("Parameters")
                self.assertIsNone(params.find("WhiteBalance"))
                self.assertIsNone(params.find("ExposureBias"))
                self.assertEqual(params.find("MonochroCreater").get("Mode"), "Manual")
                self.assertEqual(
                    params.find("MonochroCreater").get("SatValue"), str(strength)
                )
                self.assertEqual(params.find("ShadingCreator").get("Value"), "0")

    def test_readbacks_reject_inactive_or_leaking_state(self):
        layout = MonoLayout()
        s = layout.settings(
            dict(rotate=0, resize=[800, 600]), layout.start([53, 0, 0, 0]), "gpu"
        )
        cases = [
            ("mono_parameters", "active_processing_family", "other"),
            ("mono_parameters", "creative_shading", dict(status=0, mode=2, value=1)),
            ("mono_parameters", "contrast", dict(status=0, mode=2, value=0, adjust=0)),
            (
                "current_parameters",
                "saturation",
                dict(status=0, mode=2, values=[0] * 12),
            ),
            (
                "current_parameters",
                "tone_control_with_mid",
                dict(status=0, mode=1, mid=2),
            ),
        ]
        for section, key, value in cases:
            r = report_for(s)
            r[section][key] = value
            with self.subTest(section=section, key=key), self.assertRaises(ValueError):
                verify_readback(s, r)

    def test_no_numeric_category_prior_and_inherited_wb(self):
        layout = MonoLayout()
        initial = np.r_[np.zeros(4), [53, 0, 0, 0] * 2]
        R, z = layout.regularizer(2, initial)
        self.assertTrue(np.all(R[:, 0] == 0))
        self.assertEqual(R.shape[1], len(initial))
        p = dict(rotate=0, resize=[800, 600], scene_wb_anchor="as_shot")
        s = layout.settings(p, layout.start([53, 0, 0, 0]), "gpu")
        self.assertNotIn("custom_wb2", s["raw_overrides"])
        self.assertNotIn("white_balance_mode", s["raw_overrides"])
        lo, hi, _ = layout.bounds(2)
        np.testing.assert_array_equal(lo[:4], [0, -2, -7, -7])
        np.testing.assert_array_equal(hi[:4], [24, 2, 7, 7])


if __name__ == "__main__":
    unittest.main()
