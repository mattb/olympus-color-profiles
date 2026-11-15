import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import numpy as np
from PIL import Image
from omfit.renderer import Renderer, digest, save, verify_readback
from omfit.model import Layout
from omfit.color import SRGB


def readback(settings, pair, pid=123):
    p = settings["profile"]
    o = settings["raw_overrides"]
    wb = o["custom_wb2"]
    tone = o["tone_control"]
    c = {
        k: dict(status=0, mode=2, values=p.get(k, [0] * 12))
        for k in ("saturation", "hue", "luminance")
    }
    c.update(
        white_balance_mode=dict(status=0, value=4),
        color_space_mode=dict(status=0, value=1),
        custom_wb2=dict(status=0, kelvin=wb[0], ab_adjust=wb[1], gm_adjust=wb[2]),
        exposure_bias=dict(
            status=0, numerator=o["exposure_bias"][0], denominator=o["exposure_bias"][1]
        ),
        tone_control=dict(status=0, mode=tone[0], bright=tone[1], dark=tone[2]),
    )
    return dict(
        renderer_protocol="omrender-native/2",
        backend=dict(used="gpu", device=dict(context_initialization_seconds=0.4)),
        current_parameters=c,
        bits=8,
        input=pair["raw"],
        process_id=pid,
    )


class CacheTests(unittest.TestCase):
    def test_installed_package_missing_renderer_has_actionable_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'run').mkdir()
            with patch('omfit.renderer.shutil.which', return_value=None), patch(
                'omfit.renderer.__file__', str(root / 'venv/lib/python3.12/site-packages/omfit/renderer.py')
            ), self.assertRaisesRegex(ValueError, 'companion renderer.*--renderer'):
                Renderer('omrender', root / 'cache', root / 'run')

    def test_batch_resolution_cache_and_live_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            cli = root / "omrender"
            cli.write_text("# fake launcher")
            build = root / "new-gpu-build"
            build.mkdir()
            native = build / "omrender"
            native.write_bytes(b"new GPU executable")
            out = root / "run"
            out.mkdir()
            cache = root / "cache"
            pair = dict(
                raw=str(root / "source.ORF"),
                raw_hash="fixture",
                rotate=0,
                resize=[12, 8],
                developed_size=[12, 8],
            )

            def inspect(cmd):
                self.assertEqual(cmd[0], str(cli))
                return json.dumps(
                    dict(
                        build_dir=str(build),
                        native_binary=str(native),
                        native_sha256=digest(native),
                    )
                ).encode()

            calls = []

            def batch(cmd, **kwargs):
                calls.append(cmd)
                self.assertEqual(cmd[cmd.index("--build-dir") + 1], str(build))
                jobs = json.loads(Path(cmd[2]).read_text())
                for j in jobs:
                    s = json.loads(Path(j["settings"]).read_text())
                    path = Path(j["output"])
                    Image.fromarray(np.full((8, 12, 3), 128, np.uint8)).save(
                        path, icc_profile=SRGB
                    )
                    save(str(path) + ".json", readback(s, pair))
                return SimpleNamespace(returncode=0, stdout="{}", stderr="")

            with (
                patch("omfit.renderer.subprocess.check_output", side_effect=inspect),
                patch("omfit.renderer.subprocess.run", side_effect=batch),
            ):
                r = Renderer(cli, cache, out)
                layout = Layout("hsl")
                v = layout.start([53, 0, 0, 0])
                s = layout.settings(pair, v, "gpu")
                v[12] = 1
                t = layout.settings(pair, v, "gpu")
                paths = r.render_many([(pair, s), (pair, t), (pair, s)])
                self.assertEqual(len(calls), 1)
                self.assertEqual(paths[0], paths[2])
                self.assertEqual(r.calls, 2)
                self.assertEqual(r.identity["native_sha256"], digest(native))
                self.assertEqual(r.batches[0]["process_id"], 123)
                r.render_many([(pair, s)])
                self.assertEqual(len(calls), 1)
                native.write_bytes(b"updated GPU executable")
                r.render_many([(pair, s)])
                self.assertEqual(len(calls), 2)
                self.assertEqual(len(r.identities), 2)
                # Existing old-version entries remain valid but aren't used for the new executable.
                self.assertNotEqual(r.key(pair, s), paths[0].parent.name)
                side = Path(str(r.render(pair, s)) + ".json")
                side.write_text('{"tampered":true}')
                with self.assertRaises(ValueError):
                    r.render(pair, s)
                # Sharding preserves caller order and duplicate reuse while each
                # native process stays below the configured candidate limit.
                split_out = root / "split-run"
                split_out.mkdir()
                split = Renderer(cli, root / "split-cache", split_out, batch_size=1)
                split_paths = split.render_many([(pair, s), (pair, t), (pair, s)])
                self.assertEqual(split_paths[0], split_paths[2])
                self.assertEqual([b["jobs"] for b in split.batches], [1, 1])
                self.assertEqual(split.native_processes, 2)
                self.assertEqual(split.calls, 2)

    def test_batch_limit_cannot_exceed_temporary_native_safety_cap(self):
        for size in (0, 51, 1.5):
            with self.subTest(size=size), self.assertRaises(ValueError):
                Renderer("unused", "unused", "unused", batch_size=size)

    def test_wrong_actual_backend_and_hsl_readback_rejected(self):
        pair = dict(raw="x", rotate=0, resize=[12, 8])
        layout = Layout("hsl")
        v = layout.start([53, 0, 0, 0])
        v[12] = 2
        s = layout.settings(pair, v, "gpu")
        report = readback(s, pair)
        report["current_parameters"]["hue"]["values"] = [0] * 12
        with self.assertRaises(ValueError):
            verify_readback(s, report)
        report = readback(s, pair)
        report["backend"]["used"] = "cpu"
        with self.assertRaises(ValueError):
            verify_readback(s, report)


if __name__ == "__main__":
    unittest.main()
