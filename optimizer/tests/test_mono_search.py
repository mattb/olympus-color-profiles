import unittest
import numpy as np

from omfit.core import BudgetExhausted
from omfit.mono import regularizer, search


class MonoSearchTests(unittest.TestCase):
    def arguments(self):
        return (
            np.array([0, 0, 0, 0, 53, 0, 0, 0]),
            np.array([0, -2, -7, -7, 53, 0, 0, 0]),
            np.array([24, 2, 7, 7, 53, 0, 0, 0]),
            np.array([0, 1, 2, 2, 5, 2, 2, 2]),
        )

    def test_enumerates_categorical_states_then_locks_winner(self):
        seen, phases, jacobians = [], [], []

        def residual(x):
            seen.append(tuple(x))
            # No relationship between ordinal state and its response.
            filter_error = 0 if x[0] == 23 else 10 + (x[0] % 3)
            return np.array([filter_error, x[1] - 1, x[2] - 3, x[3] + 2])

        result = search(
            *self.arguments(),
            residual,
            np.zeros((0, 8)),
            np.zeros(0),
            max_iterations=6,
            prefetch=lambda v: phases.append(v),
            inspect_jacobian=lambda x, j: jacobians.append(j),
        )
        self.assertEqual([v[0] for v in seen[:25]], list(range(25)))
        self.assertTrue(all(v[0] == 23 for v in seen[25:]))
        np.testing.assert_array_equal(result.vector[:4], [23, 1, 3, -2])
        np.testing.assert_array_equal(result.vector[4:], [53, 0, 0, 0])
        self.assertEqual(len(phases[0]), 24)
        self.assertTrue(all(np.all(j[:, 0] == 0) for j in jacobians))
        self.assertIn(tuple(result.vector), seen)

    def test_budget_during_enumeration_returns_best_fully_measured(self):
        seen = []

        def residual(x):
            if len(seen) == 7:
                raise BudgetExhausted()
            seen.append(tuple(x))
            return np.array([0 if x[0] == 5 else 1])

        result = search(*self.arguments(), residual, np.zeros((0, 8)), np.zeros(0))
        self.assertEqual(result.stop, "evaluation_budget")
        self.assertEqual(result.vector[0], 5)
        self.assertIn(tuple(result.vector), seen)
        self.assertEqual(len(result.history), 7)

    def test_ties_choose_off_and_replay_is_exact(self):
        results = [
            search(
                *self.arguments(), lambda x: np.zeros(1), np.zeros((0, 8)), np.zeros(0)
            )
            for _ in range(2)
        ]
        self.assertEqual(results[0].vector[0], 0)
        self.assertEqual(results[0].history, results[1].history)
        self.assertEqual(results[0].stop, results[1].stop)

    def test_numeric_filter_prior_is_rejected(self):
        penalty = np.zeros((1, 8))
        penalty[0, 0] = 0.1
        with self.assertRaisesRegex(ValueError, "numeric penalties"):
            search(*self.arguments(), lambda x: np.zeros(1), penalty, np.zeros(1))

    def test_regularizer_has_no_filter_prior_and_keeps_scene_anchor(self):
        initial = self.arguments()[0]
        matrix, target = regularizer(1, initial)
        np.testing.assert_array_equal(matrix[:, 0], 0)
        np.testing.assert_allclose(matrix @ initial, target)
        other_filter = initial.copy()
        other_filter[0] = 24
        np.testing.assert_allclose(matrix @ other_filter, target)
        altered_scene = initial.copy()
        altered_scene[4] += 5
        self.assertGreater(np.linalg.norm(matrix @ altered_scene - target), 0)


if __name__ == "__main__":
    unittest.main()
