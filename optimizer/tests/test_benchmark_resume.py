import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import numpy as np

from omfit.benchmark import completed_case, controlled_bounds, controlled_policy
from omfit.model import Layout
from omfit.experimental import TuningPolicy


class BenchmarkResumeTests(unittest.TestCase):
    def test_identical_request_resumes_without_renderer_lock(self):
        expected = dict(
            source_data_hash="dataset-A",
            policy=dict(budget=200),
            evaluation_split="test",
            training_ids=["a", "b"],
        )
        with TemporaryDirectory() as d:
            p = Path(d) / "result.json"
            p.write_text(json.dumps(dict(expected, renderer_versions=["old-build"])))
            self.assertEqual(
                completed_case(p, expected)["renderer_versions"], ["old-build"]
            )

    def test_changed_experiment_cannot_silently_reuse_result(self):
        original = dict(
            source_data_hash="dataset-A",
            policy=dict(budget=200),
            evaluation_split="test",
            training_ids=["a", "b"],
        )
        with TemporaryDirectory() as d:
            p = Path(d) / "result.json"
            p.write_text(json.dumps(original))
            for key, changed in (
                ("source_data_hash", "dataset-B"),
                ("policy", dict(budget=400)),
                ("evaluation_split", "dev"),
                ("training_ids", ["b", "c"]),
            ):
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, key):
                    completed_case(p, dict(original, **{key: changed}))


class ControlledHSLBoundsTests(unittest.TestCase):
    def test_matched_saturation_range_changes_only_hsl_saturation(self):
        layout = Layout("hsl")
        normal = layout.bounds(3)
        matched = controlled_bounds(layout, 3, 5)
        self.assertTrue(np.all(matched[0][:12] == -5))
        self.assertTrue(np.all(matched[1][:12] == 5))
        for actual, expected in zip(matched[:2], normal[:2]):
            np.testing.assert_array_equal(actual[12:], expected[12:])
        np.testing.assert_array_equal(matched[2], normal[2])
        for actual, expected in zip(controlled_bounds(layout, 3), normal):
            np.testing.assert_array_equal(actual, expected)
        for actual, expected in zip(controlled_bounds(Layout("stock"), 3, 5), Layout("stock").bounds(3)):
            np.testing.assert_array_equal(actual, expected)
        with self.assertRaises(ValueError):
            controlled_bounds(layout, 3, 6)

    def test_matched_penalty_equal_for_identical_saturation_vector(self):
        policy = TuningPolicy(name="original_budget")
        stock, hsl = Layout("stock"), Layout("hsl")
        a = stock.start([53, 0, 0, 0])
        b = hsl.start([53, 0, 0, 0])
        a[:12] = b[:12] = np.arange(12) % 5 - 2
        matched = controlled_policy(policy, hsl, True)
        self.assertEqual(matched.wheel_l2, 3 * policy.wheel_l2)
        self.assertEqual(matched.wheel_smooth, 3 * policy.wheel_smooth)
        Ra, za = policy.make_regularizer(1, stock.start([53, 0, 0, 0]), wheel_channels=1)
        Rb, zb = matched.make_regularizer(1, hsl.start([53, 0, 0, 0]), wheel_channels=3)
        self.assertAlmostEqual(float(np.sum((Ra @ a - za)**2)), float(np.sum((Rb @ b - zb)**2)))
        self.assertIs(controlled_policy(policy, hsl), policy)
        self.assertIs(controlled_policy(policy, stock, True), policy)

    def test_changed_saturation_constraint_cannot_resume(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "result.json"
            p.write_text(json.dumps(dict(hsl_saturation_limit=7)))
            with self.assertRaisesRegex(ValueError, "hsl_saturation_limit"):
                completed_case(p, dict(hsl_saturation_limit=5))

    def test_default_request_rejects_constrained_record_but_accepts_legacy(self):
        defaults = dict(hsl_saturation_limit=7, match_stock_wheel_penalty=False)
        with TemporaryDirectory() as d:
            p = Path(d) / "result.json"
            p.write_text(json.dumps(dict(hsl_saturation_limit=5)))
            with self.assertRaisesRegex(ValueError, "hsl_saturation_limit"):
                completed_case(p, defaults)
            p.write_text(json.dumps(dict(match_stock_wheel_penalty=True)))
            with self.assertRaisesRegex(ValueError, "match_stock_wheel_penalty"):
                completed_case(p, defaults)
            p.write_text("{}")
            self.assertEqual(completed_case(p, defaults), {})


if __name__ == "__main__":
    unittest.main()
