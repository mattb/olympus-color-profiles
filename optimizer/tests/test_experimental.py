import unittest
from dataclasses import asdict, replace
from types import SimpleNamespace
import numpy as np
from skimage.color import deltaE_ciede2000

from omfit.core import BudgetExhausted
from omfit.experimental import (
    TuningPolicy,
    run_strategy,
    screen_policies,
    scene_ablation,
    scoring_residual,
)


class EvaluatorFixture:
    """Existing Evaluator protocol, with real per-image logical admission costs."""

    def __init__(self, residual, *, shared=1, n_images=1, budget=128, warm=False):
        self.residual = residual
        self.layout = SimpleNamespace(shared=shared)
        self.train = [None] * n_images
        self.budget = budget
        self.warm = warm
        self.requested = set()
        self.request_order = []
        self.materialized = set()
        self.residuals = {}
        self.renderer = SimpleNamespace(calls=0, native_processes=0)
        self.jacobians = []
        self.rendered_vectors = set()

    def keys(self, vector):
        return [(i, tuple(map(int, vector))) for i in range(len(self.train))]

    def reserve(self, key):
        if key not in self.requested:
            if len(self.requested) >= self.budget:
                return False
            self.requested.add(key)
            self.request_order.append(key)
        return True

    def render_phase(self, keys):
        missing = [key for key in keys if key not in self.materialized]
        if missing and not self.warm:
            self.renderer.native_processes += 1
            self.renderer.calls += len(set(missing))
        self.materialized.update(keys)

    def prefetch(self, vectors):
        admitted = []
        for vector in vectors:
            for key in self.keys(vector):
                if not self.reserve(key):
                    self.render_phase(admitted)
                    return
                admitted.append(key)
        self.render_phase(admitted)

    def __call__(self, vector):
        key = tuple(map(int, vector))
        if key not in self.residuals:
            keys = self.keys(vector)
            if not all(self.reserve(k) for k in keys):
                raise BudgetExhausted()
            self.render_phase(keys)
            self.residuals[key] = np.asarray(self.residual(vector), dtype=float)
            self.rendered_vectors.add(key)
        return self.residuals[key]

    def inspect_jacobian(self, vector, matrix):
        self.jacobians.append((vector.copy(), matrix.copy()))


def no_penalty(n):
    return np.zeros((0, n)), np.zeros(0)


class StrategyTests(unittest.TestCase):
    def test_original_algorithm_retained_with_inspection_hook(self):
        e = EvaluatorFixture(lambda x: np.array([x[0] - 2.0]))
        r = run_strategy(TuningPolicy(), [0], [-4], [4], [2], e, *no_penalty(1))
        np.testing.assert_array_equal(r.vector, [2])
        self.assertEqual([s["name"] for s in r.stages], ["coarse"])
        self.assertGreater(len(e.jacobians), 0)
        self.assertEqual(r.objective, 0.0)
        self.assertIn(tuple(r.vector), e.rendered_vectors)
        self.assertEqual(e.budget, 128)

    def test_asymmetric_strategies_and_equal_caps(self):
        def asymmetric(x):
            return np.array([10 * x[0] - 3.0 if x[0] >= 0 else -x[0] - 3.0])

        results = {}
        for strategy in ("original", "coarse1_polish", "directional_polish"):
            e = EvaluatorFixture(asymmetric)
            p = TuningPolicy(
                name=strategy, strategy=strategy, render_budget_per_image=20
            )
            results[strategy] = run_strategy(p, [0], [-4], [4], [2], e, *no_penalty(1))
            self.assertLessEqual(results[strategy].cost["requests_total"], 20)
            self.assertEqual(results[strategy].cost["request_cap"], 20)
        self.assertEqual(results["original"].objective, 9.0)
        self.assertEqual(results["coarse1_polish"].objective, 0.0)
        self.assertEqual(results["directional_polish"].objective, 0.0)
        self.assertEqual(
            [s["name"] for s in results["coarse1_polish"].stages], ["coarse", "polish"]
        )
        self.assertEqual(
            [s["name"] for s in results["directional_polish"].stages],
            ["directional", "polish"],
        )

    def test_directional_predictions_cannot_be_accepted_without_actual_score(self):
        e = EvaluatorFixture(lambda x: np.array([x[0] ** 3 - 3.0]))
        r = run_strategy(
            TuningPolicy(strategy="directional_polish"),
            [0],
            [-4],
            [4],
            [2],
            e,
            *no_penalty(1),
        )
        np.testing.assert_array_equal(r.vector, [1])
        self.assertEqual(r.objective, 4.0)
        row = r.stages[0]["history"][1]
        self.assertIn([2], row["proposed"])
        self.assertIn((2,), e.rendered_vectors)  # actual residual is +5, loss25
        self.assertEqual(row["objective"], 4.0)
        self.assertLess(min(row["model_predictions"]), row["objective"])

    def test_original_regularizer_target_is_not_reset_after_coarse(self):
        e = EvaluatorFixture(lambda x: np.array([x[0] - 3.0]))
        policy = TuningPolicy(strategy="coarse1_polish", trust_steps=1)
        R, z = np.array([[0.5]]), np.array([0.0])
        r = run_strategy(policy, [0], [-4], [4], [2], e, R, z)
        np.testing.assert_array_equal(r.vector, [2])
        self.assertEqual(r.objective, 2.0)
        np.testing.assert_array_equal(z, [0.0])
        self.assertEqual(r.stages[0]["vector"], [1])
        self.assertEqual(r.stages[1]["vector"], [2])

    def test_primary_scene_frozen_and_explicit_free_scene_ablation(self):
        def residual(x):
            return np.array([x[0] + x[1] - 2.0, 0.2 * x[0]])

        results = []
        for p in (TuningPolicy(), scene_ablation(TuningPolicy())):
            e = EvaluatorFixture(residual, shared=1)
            results.append(
                run_strategy(p, [0, 0], [-4, -4], [4, 4], [2, 2], e, *no_penalty(2))
            )
        self.assertEqual(results[0].vector[1], 0)
        self.assertEqual(results[1].vector[1], 2)
        self.assertLess(results[1].objective, results[0].objective)
        self.assertEqual(results[0].policy["scene_mode"], "frozen")
        self.assertEqual(results[1].policy["scene_mode"], "free")

    def test_budget_warm_and_cold_admit_same_requests_for_every_strategy(self):
        for strategy in ("original", "coarse1_polish", "directional_polish"):
            results = []
            evaluators = []
            for warm in (False, True):
                e = EvaluatorFixture(
                    lambda x: np.array([x[0] + 3.0]), budget=4, n_images=2, warm=warm
                )
                p = TuningPolicy(strategy=strategy, render_budget_per_image=2)
                results.append(run_strategy(p, [0], [-5], [5], [2], e, *no_penalty(1)))
                evaluators.append(e)
            np.testing.assert_array_equal(results[0].vector, results[1].vector)
            self.assertEqual(results[0].objective, results[1].objective)
            self.assertEqual(results[0].history, results[1].history)
            self.assertEqual(evaluators[0].request_order, evaluators[1].request_order)
            self.assertEqual(results[1].cost["native_calls"], 0)
            self.assertLessEqual(results[0].cost["requests_total"], 4)
            self.assertEqual(results[0].cost["request_cap"], 4)

    def test_partial_multi_photo_candidate_does_not_win(self):
        e = EvaluatorFixture(lambda x: np.array([x[0] + 3.0]), budget=3, n_images=2)
        r = run_strategy(
            TuningPolicy(strategy="directional_polish"),
            [0],
            [-5],
            [5],
            [2],
            e,
            *no_penalty(1),
        )
        np.testing.assert_array_equal(r.vector, [0])
        self.assertEqual(r.objective, 9.0)
        self.assertEqual(r.stop, "evaluation_budget")
        self.assertEqual(r.cost["requests_total"], 3)
        self.assertNotIn((-1,), e.rendered_vectors)

    def test_caller_hard_cap_is_never_increased_and_restored_on_error(self):
        e = EvaluatorFixture(lambda x: np.array([x[0] - 3.0]), budget=2)
        r = run_strategy(
            TuningPolicy(render_budget_per_image=100),
            [0],
            [-5],
            [5],
            [2],
            e,
            *no_penalty(1),
        )
        self.assertEqual(r.cost["request_cap"], 2)
        self.assertEqual(e.budget, 2)
        bad = EvaluatorFixture(lambda x: np.array([np.nan]), budget=12)
        with self.assertRaises(ValueError):
            run_strategy(
                TuningPolicy(render_budget_per_image=3),
                [0],
                [-5],
                [5],
                [2],
                bad,
                *no_penalty(1),
            )
        self.assertEqual(bad.budget, 12)

    def test_no_false_benefit_on_linear_case(self):
        r = []
        for strategy in ("original", "coarse1_polish", "directional_polish"):
            e = EvaluatorFixture(lambda x: np.array([x[0] - 2.0]))
            r.append(
                run_strategy(
                    TuningPolicy(strategy=strategy),
                    [0],
                    [-5],
                    [5],
                    [2],
                    e,
                    *no_penalty(1),
                )
            )
        self.assertEqual([x.objective for x in r], [0.0, 0.0, 0.0])


class PolicyTests(unittest.TestCase):
    def test_screen_is_predeclared_small_and_fixed_budget(self):
        policies = screen_policies(render_budget_per_image=128)
        self.assertLessEqual(len(policies), 20)
        self.assertEqual(len({p.name for p in policies}), len(policies))
        self.assertTrue(all(p.render_budget_per_image == 128 for p in policies))
        self.assertTrue(all(p.scene_mode == "frozen" for p in policies))
        base = asdict(policies[0])
        combined = next(p for p in policies if p.name == "grid_192_blur_none")
        self.assertEqual(combined.grid_size, 192)
        self.assertEqual(combined.blur_sigma, 0.0)
        for p in policies[1:]:
            changed = {k for k, v in asdict(p).items() if v != base[k] and k != "name"}
            self.assertLessEqual(len(changed), 2)
        self.assertEqual(
            policies[0].score_options(),
            dict(size=96, blur=0.7, loss="lab", weighting="spatial"),
        )

    def test_regularizer_uses_policy_values_with_original_initial(self):
        p = TuningPolicy(wheel_l2=0.1, wheel_smooth=0.0, tone_l2=0.2)
        initial = np.array([0] * 14 + [53, 0, 0, 0])
        R, z = p.make_regularizer(1, initial)
        self.assertEqual(R.shape[1], 18)
        np.testing.assert_allclose(R @ initial - z, 0.0)

    def test_losses_have_declared_objectives_and_immutable_weights(self):
        target = np.array([[[50.0, 0.0, 0.0], [80.0, 5.0, -3.0]]])
        candidate = target + np.array([[[3.0, 4.0, 0.0], [1.0, 0.0, 2.0]]])
        w = np.array([[1.0, 3.0]])
        original = w.copy()
        lab = scoring_residual(candidate, target, w, loss="lab")
        de = scoring_residual(candidate, target, w, loss="delta_e00_squared")
        self.assertAlmostEqual(
            float(lab @ lab),
            float(np.sum((candidate - target) ** 2 * np.array([[[0.25], [0.75]]])) / 3),
        )
        expected = float(
            np.sum(deltaE_ciede2000(candidate, target) ** 2 * np.array([[0.25, 0.75]]))
        )
        self.assertAlmostEqual(float(de @ de), expected)
        np.testing.assert_array_equal(w, original)
        with self.assertRaises(ValueError):
            scoring_residual(candidate, target, np.zeros_like(w))

    def test_invalid_policy_values_rejected(self):
        for kwargs in (
            dict(strategy="unknown"),
            dict(loss="DEmean"),
            dict(weighting="anything"),
            dict(trust_steps=0),
            dict(grid_size=100),
            dict(render_budget_per_image=0),
            dict(wheel_smooth=-1),
            dict(blur_sigma=np.nan),
        ):
            with self.assertRaises(ValueError):
                TuningPolicy(**kwargs)


if __name__ == "__main__":
    unittest.main()
