import unittest
import numpy as np
from omfit.core import search, quantize, regularizer, BudgetExhausted


class SearchTests(unittest.TestCase):
    def test_quantization(self):
        np.testing.assert_array_equal(
            quantize([0.5, 1.5, 99], [-2] * 3, [2] * 3), [0, 2, 2]
        )

    def test_measured_nonlinear_and_repeat(self):
        def run():
            seen = []

            def residual(x):
                seen.append(tuple(x))
                return np.array([x[0] ** 2 - 9.0, x[1] - 2.0])

            r = search(
                np.array([1, 0]),
                np.array([0, -5]),
                np.array([5, 5]),
                np.array([2, 2]),
                residual,
                np.zeros((0, 2)),
                np.zeros(0),
                max_iterations=5,
            )
            self.assertIn(tuple(r.vector), seen)
            self.assertTrue(
                all(
                    h["objective"] < h["previous"]
                    for h in r.history[1:]
                    if h["accepted"]
                )
            )
            return r

        a, b = run(), run()
        self.assertEqual(a.history, b.history)
        np.testing.assert_array_equal(a.vector, [3, 2])

    def test_budget_returns_complete_best(self):
        seen = []

        def residual(x):
            if len(seen) == 2:
                raise BudgetExhausted()
            seen.append(tuple(x))
            return np.array([x[0] - 3.0, x[1] - 2.0])

        r = search(
            np.array([0, 0]),
            np.array([-5] * 2),
            np.array([5] * 2),
            np.array([2] * 2),
            residual,
            np.zeros((0, 2)),
            np.zeros(0),
        )
        self.assertEqual(r.stop, "evaluation_budget")
        self.assertIn(tuple(r.vector), seen)
        np.testing.assert_array_equal(r.vector, [1, 0])

    def test_circular_penalty(self):
        R, z = regularizer(1, np.array([0] * 14 + [53, 0, 0, 0]), 0, 1, 0, 0)
        x = np.zeros(18)
        x[0] = 1
        y = np.zeros(18)
        y[11] = 1
        self.assertAlmostEqual(np.linalg.norm(R @ x), np.linalg.norm(R @ y))


if __name__ == "__main__":
    unittest.main()
