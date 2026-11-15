from types import SimpleNamespace
import unittest
from omfit.cli import request_budget
from omfit.model import Layout


class BudgetPolicyTests(unittest.TestCase):
    def test_default_scales_enough_for_four_hsl_models(self):
        args = SimpleNamespace(max_renders=None, render_budget_per_photo=200)
        for n in (1, 2, 8):
            # Four complete shared+scene Jacobians plus two joint candidates each,
            # from neutral with two-step moves, make the ±7 bounds reachable.
            required = n * (1 + 4 * (Layout("hsl").shared + 4 + 2))
            self.assertGreaterEqual(request_budget(args, n), required)

    def test_explicit_total_cap_remains_authoritative(self):
        args = SimpleNamespace(max_renders=26, render_budget_per_photo=200)
        self.assertEqual(request_budget(args, 2), 26)
        with self.assertRaises(ValueError):
            request_budget(args, 27)

    def test_as_shot_anchor_does_not_export_unused_kelvin(self):
        layout = Layout("stock")
        p = dict(rotate=0, resize=[800, 600], scene_wb_anchor="as_shot")
        v = layout.start([53, 0, 0, 0])
        s = layout.settings(p, v, "gpu")
        a = layout.adjustments(v, p)
        self.assertNotIn("custom_wb2", s["raw_overrides"])
        self.assertNotIn("white_balance_mode", s["raw_overrides"])
        self.assertNotIn("custom_wb2", a)
        self.assertEqual(a["white_balance_anchor"], "inherited_ORF_as_shot")


if __name__ == "__main__":
    unittest.main()
