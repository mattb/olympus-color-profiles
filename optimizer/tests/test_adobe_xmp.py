import tempfile
from pathlib import Path
import unittest
import numpy as np
from omfit.adobe_xmp import (
    base_settings,
    write_preset,
    write_sidecar,
    read_settings,
    read_preset,
    SCENE_KEYS,
)
from omfit.adobe import settings_for, load_pairs, controls_for, initial_vector, run


class AdobeXMPTests(unittest.TestCase):
    def test_preset_excludes_scene_and_roundtrips_tone_curve(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "preset.xmp"
            s = settings_for(
                np.arange(13),
                "mono",
                dict(WhiteBalance="Custom", Temperature=5000, Tint=4, Exposure2012=1),
            )
            write_preset(p, s, "A & B <test>")
            a = p.read_bytes()
            values = read_settings(p)
            self.assertFalse(SCENE_KEYS & set(values))
            self.assertEqual(values["GrayMixerRed"], "25")
            self.assertNotIn("AutoGray", values)
            self.assertEqual(values["ToneCurvePV2012"], ["0, 0", "255, 255"])
            self.assertEqual(values["PresetType"], "Normal")
            self.assertEqual(len(values["UUID"]), 32)
            write_preset(p, s, "A & B <test>")
            self.assertEqual(a, p.read_bytes())
            self.assertEqual(
                read_preset(p), {k: v for k, v in s.items() if k not in SCENE_KEYS}
            )

    def test_sidecar_retains_scene_separately(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "photo.xmp"
            s = dict(base_settings(), WhiteBalance="As Shot", Exposure2012=2)
            write_sidecar(p, s)
            r = read_settings(p)
            self.assertEqual(r["Exposure2012"], "2")
            self.assertEqual(r["ConvertToGrayscale"], "True")

    def test_settings_mapping_and_scene_whitelist(self):
        s = settings_for(np.ones(13, dtype=int), "mono", dict(Exposure2012=0))
        self.assertEqual(s["Contrast2012"], 5)
        self.assertEqual(s["GrayMixerMagenta"], 5)
        with tempfile.TemporaryDirectory() as d:
            import json

            root = Path(d)
            (root / "raw").write_bytes(b"x")
            (root / "target").write_bytes(b"x")
            p = root / "manifest.json"
            p.write_text(
                json.dumps(
                    dict(
                        pairs=[
                            dict(
                                id="a",
                                raw="raw",
                                target="target",
                                scene=dict(Contrast2012=5),
                            )
                        ]
                    )
                )
            )
            with self.assertRaises(ValueError):
                load_pairs(p)

    def test_color_controls_and_seed_preserve_scene_boundary(self):
        controls = controls_for("color")
        self.assertEqual(len(controls), 31)
        self.assertEqual(len(set(controls)), 31)
        v = np.arange(31) % 9 - 4
        s = settings_for(v, "color", dict(WhiteBalance="As Shot", Exposure2012=0))
        self.assertEqual(s["LuminanceAdjustmentMagenta"], int(v[-1]) * 5)
        self.assertFalse(s["ConvertToGrayscale"])
        self.assertFalse(any(k.startswith("GrayMixer") for k in s))
        self.assertTrue(all(s[k] == int(i) * 5 for k, i in zip(controls, v)))
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "preset.xmp"
            write_preset(p, s, "Color")
            self.assertTrue(np.array_equal(initial_vector(p, "color"), v))
            self.assertFalse(SCENE_KEYS & read_preset(p).keys())
            with self.assertRaises(ValueError):
                initial_vector(p, "mono")
            s["Saturation"] = 101
            write_preset(p, s, "Invalid")
            with self.assertRaises(ValueError):
                initial_vector(p, "color")
        with self.assertRaises(ValueError):
            settings_for(np.zeros(5), "color", {})

    def test_selected_camera_profile_reaches_all_render_and_export_paths(self):
        import json
        from contextlib import redirect_stdout
        from io import StringIO
        from types import SimpleNamespace
        from unittest.mock import patch
        from PIL import Image
        from omfit.color import SRGB

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            image = root / "render.png"
            Image.new("RGB", (800, 600), (70, 100, 140)).save(image, icc_profile=SRGB)
            for name in ("train", "validation"):
                (root / name).write_bytes(name.encode())
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps(dict(pairs=[
                dict(id=n, raw=n, target=str(image), role=n)
                for n in ("train", "validation")
            ])))
            args = SimpleNamespace(manifest=str(manifest), output=str(root/"out"),
                cache=str(root/"cache"), converter=None, mode="color", name="Fixture",
                camera_profile="Camera Natural", max_renders=1, iterations=0,
                identity_geometry=True, skip_full_validation=True, initial_preset=None)
            with patch("omfit.adobe_renderer.AdobeRenderer") as factory, redirect_stdout(StringIO()):
                renderer = factory.return_value
                renderer.render.return_value = image
                renderer.identity = {}
                renderer.calls = 2
                renderer.hits = 0
                run(args)
            self.assertTrue(renderer.render.call_args_list)
            self.assertTrue(all(c.args[1]["CameraProfile"] == "Camera Natural"
                                for c in renderer.render.call_args_list))
            self.assertEqual(read_preset(root/"out/profile.xmp")["CameraProfile"], "Camera Natural")
            for name in ("train", "validation"):
                self.assertEqual(read_settings(root/"out/settings"/(name+".xmp"))["CameraProfile"], "Camera Natural")

    def test_no_train_validation_source_leak_and_finite_scene(self):
        import json

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "raw").write_bytes(b"raw")
            (root / "target").write_bytes(b"target")
            p = root / "manifest.json"
            for rows in [
                [
                    dict(id="a", raw="raw", target="target"),
                    dict(id="b", raw="raw", target="target", role="validation"),
                ],
                [
                    dict(
                        id="a",
                        raw="raw",
                        target="target",
                        scene=dict(Exposure2012=float("nan")),
                    )
                ],
                [
                    dict(
                        id="a",
                        raw="raw",
                        target="target",
                        scene=dict(WhiteBalance="Custom"),
                    )
                ],
            ]:
                p.write_text(json.dumps(dict(pairs=rows)))
                with self.assertRaises(ValueError):
                    load_pairs(p)


if __name__ == "__main__":
    unittest.main()
