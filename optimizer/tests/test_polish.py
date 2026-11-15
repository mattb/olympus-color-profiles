import unittest
import numpy as np

from omfit.core import BudgetExhausted, search
from omfit.polish import polish, legal_neighbors
from omfit.directional import directional_proposals


def no_penalty(n):
    return np.zeros((0, n)), np.zeros(0)


class PrefixBudget:
    """Vector-cost callback fixture; disk warmth cannot change request admission."""
    def __init__(self, residual, budget, warm=False):
        self.residual = residual
        self.budget = budget
        self.warm = warm
        self.requested = []
        self.seen = set()
        self.native = 0
        self.phases = []

    def reserve(self, x):
        key = tuple(map(int, x))
        if key not in self.seen:
            if len(self.seen) == self.budget:
                return False
            self.seen.add(key)
            self.requested.append(key)
            if not self.warm:
                self.native += 1
        return True

    def prefetch(self, vectors):
        admitted = []
        for vector in vectors:
            if not self.reserve(vector):
                break
            admitted.append(tuple(vector))
        self.phases.append(admitted)

    def __call__(self, x):
        if not self.reserve(x):
            raise BudgetExhausted()
        return self.residual(x)


class PolishTests(unittest.TestCase):
    def test_complete_neighborhood_and_measured_monotonic_acceptance(self):
        seen, phases = [], []
        def residual(x):
            seen.append(tuple(x))
            return np.array([x[0]**2-9., x[1]-2.])
        result = polish([1,0], [0,-5], [5,5], residual, *no_penalty(2),
                        max_sweeps=10, prefetch=lambda v: phases.append([tuple(x) for x in v]))
        np.testing.assert_array_equal(result.vector, [3,2])
        self.assertEqual(result.stop, 'no_measured_improvement')
        self.assertEqual(phases[0], [(0,0),(2,0),(1,-1),(1,1)])
        self.assertIn(tuple(result.vector), seen)
        for row in result.history[1:]:
            self.assertTrue(row['complete'])
            if row['accepted']:
                self.assertLess(row['objective'], row['previous']-1e-4)
        # Distinct-vector memoization skips previously measured reverse moves.
        self.assertEqual(len(seen), len(set(seen)))

    def test_asymmetric_response_benefit_over_one_sided_coarse_model(self):
        def asymmetric(x):
            return np.array([10*x[0]-3. if x[0]>=0 else -x[0]-3.])
        coarse = search(np.array([0]), np.array([-4]), np.array([4]), np.array([3]),
                        asymmetric, *no_penalty(1), max_iterations=1)
        np.testing.assert_array_equal(coarse.vector, [0])
        fine = polish(coarse.vector, [-4], [4], asymmetric, *no_penalty(1), max_sweeps=5)
        np.testing.assert_array_equal(fine.vector, [-3])
        self.assertEqual(fine.objective, 0.)

    def test_no_benefit_after_exact_linear_coarse_solution(self):
        residual = lambda x: np.array([x[0]-2., x[1]+1.])
        coarse = search(np.array([0,0]), np.array([-4,-4]), np.array([4,4]), np.array([3,3]),
                        residual, *no_penalty(2), max_iterations=1)
        measured = []
        def actual(x):
            measured.append(tuple(x)); return residual(x)
        fine = polish(coarse.vector, [-4,-4], [4,4], actual, *no_penalty(2))
        np.testing.assert_array_equal(fine.vector, coarse.vector)
        self.assertEqual(fine.objective, coarse.objective)
        self.assertEqual(fine.stop, 'no_measured_improvement')
        self.assertEqual(len(measured), 5)  # extra cost for no gain is intentional evidence

    def test_coordinate_optimum_is_not_joint_optimum(self):
        residual = lambda x: np.array([2.+x[0]+x[1], 3.*(x[0]-x[1])])
        fine = polish([0,0], [-3,-3], [3,3], residual, *no_penalty(2))
        np.testing.assert_array_equal(fine.vector, [0,0])
        self.assertEqual(fine.stop, 'no_measured_improvement')
        self.assertEqual(float(residual(np.array([-1,-1])) @ residual(np.array([-1,-1]))), 0.)

    def test_same_regularization_and_tie_rule(self):
        result = polish([0], [-3], [3], lambda x: np.array([x[0]-2.]),
                        np.array([[2.]]), np.zeros(1))
        np.testing.assert_array_equal(result.vector, [0])
        # As in core.search, an equal-loss lower-norm measured point may be
        # returned without being accepted to start another sweep.
        tied = polish([1], [-1], [2], lambda x: np.zeros(1), *no_penalty(1))
        np.testing.assert_array_equal(tied.vector, [0])
        self.assertFalse(tied.history[-1]['accepted'])

    def test_bounds_fixed_dimensions_and_stationarity(self):
        neighbors = legal_neighbors(np.array([0,2]), np.array([0,2]), np.array([1,2]))
        self.assertEqual([v.tolist() for v in neighbors], [[1,2]])
        result = polish([0], [0], [0], lambda x: np.ones(1), *no_penalty(1))
        self.assertEqual(result.stop, 'quantized_stationary')

    def test_external_prefix_budget_is_deterministic_cold_and_warm(self):
        results, callbacks = [], []
        for warm in (False, True):
            callback = PrefixBudget(lambda x: np.array([x[0]+3., x[1]+1.]), 3, warm)
            results.append(polish([0,0], [-5,-5], [5,5], callback, *no_penalty(2),
                                  prefetch=callback.prefetch, max_sweeps=5))
            callbacks.append(callback)
        self.assertEqual(results[0].history, results[1].history)
        np.testing.assert_array_equal(results[0].vector, [-1,0])
        self.assertEqual(results[0].stop, 'evaluation_budget')
        self.assertFalse(results[0].history[-1]['complete'])
        self.assertEqual(callbacks[0].requested, [(0,0),(-1,0),(1,0)])
        self.assertEqual(callbacks[0].requested, callbacks[1].requested)
        self.assertEqual(callbacks[1].native, 0)

    def test_internal_vector_budget_limits_prefetch_and_returns_complete_best(self):
        phases, seen = [], []
        def residual(x):
            seen.append(tuple(x)); return np.array([x[0]+3.,x[1]+1.])
        result = polish([0,0], [-5,-5], [5,5], residual, *no_penalty(2),
                        max_evaluations=3, prefetch=lambda v: phases.append([tuple(x) for x in v]))
        np.testing.assert_array_equal(result.vector, [-1,0])
        self.assertEqual(phases, [[(-1,0),(1,0)]])
        self.assertEqual(len(seen), 3)
        self.assertEqual(result.stop, 'evaluation_budget')

    def test_invalid_settings_and_residual_fail_closed(self):
        for initial in ([.5], [np.nan]):
            with self.assertRaises(ValueError):
                polish(initial, [-1], [1], lambda x: np.ones(1), *no_penalty(1))
        with self.assertRaises(ValueError):
            polish([0], [-1], [1], lambda x: np.array([np.nan]), *no_penalty(1))
        with self.assertRaises(ValueError):
            polish([0], [-1], [1], lambda x: np.ones(1), *no_penalty(1), max_evaluations=0)


class DirectionalTests(unittest.TestCase):
    def test_separate_signed_effects_make_asymmetric_negative_proposal(self):
        residual = lambda x: np.array([10*x[0]-3. if x[0]>=0 else -x[0]-3.])
        result = directional_proposals([0], [-4], [4], [3], residual, *no_penalty(1))
        self.assertTrue(result.complete)
        np.testing.assert_array_equal(result.effects[(0,-1)], [1.])
        np.testing.assert_array_equal(result.effects[(0,1)], [10.])
        self.assertIn([-3], [x.tolist() for x in result.vectors])
        self.assertIn([0.], [residual(x).tolist() for x in result.vectors])
        self.assertEqual(result.evaluations, 3)
        # The returned best measurement is -1, not the unrendered -3 proposal.
        np.testing.assert_array_equal(result.best_measured_vector, [-1])
        self.assertEqual(result.best_measured_objective, 4.)

    def test_symmetric_linear_case_has_no_accuracy_advantage(self):
        residual = lambda x: np.array([x[0]-2.])
        coarse = search(np.array([0]), np.array([-4]), np.array([4]), np.array([3]),
                        residual, *no_penalty(1), max_iterations=1)
        proposal = directional_proposals([0], [-4], [4], [3], residual, *no_penalty(1))
        self.assertIn(coarse.vector.tolist(), [x.tolist() for x in proposal.vectors])
        self.assertEqual(min(float(residual(x) @ residual(x)) for x in proposal.vectors), coarse.objective)

    def test_nonlinear_prediction_is_not_an_accepted_measurement(self):
        residual = lambda x: np.array([x[0]**3-3.])
        result = directional_proposals([0], [-4], [4], [3], residual, *no_penalty(1))
        index = [x.tolist() for x in result.vectors].index([3])
        self.assertEqual(result.predicted_objectives[index], 0.)
        self.assertGreater(float(residual(result.vectors[index]) @ residual(result.vectors[index])), result.best_measured_objective)
        np.testing.assert_array_equal(result.best_measured_vector, [1])

    def test_budget_determinism_and_no_partial_model(self):
        outcomes = []
        for warm in (False, True):
            callback = PrefixBudget(lambda x: np.array([x[0]+2.,x[1]-3.]), 3, warm)
            outcomes.append(directional_proposals([0,0], [-4,-4], [4,4], [3,3],
                callback, *no_penalty(2), prefetch=callback.prefetch))
        for result in outcomes:
            self.assertFalse(result.complete)
            self.assertEqual(result.vectors, [])
            self.assertEqual(result.evaluations, 3)
        np.testing.assert_array_equal(outcomes[0].best_measured_vector, outcomes[1].best_measured_vector)
        self.assertEqual(outcomes[0].best_measured_objective, outcomes[1].best_measured_objective)

    def test_zero_trust_and_bounds_produce_no_illegal_proposals(self):
        result = directional_proposals([0,1], [0,1], [2,1], [0,0],
                                       lambda x: np.array([x[0]-2.]), *no_penalty(2))
        self.assertEqual(result.vectors, [])
        for trust in ([-1,0], [np.nan,0], [1]):
            with self.assertRaises(ValueError):
                directional_proposals([0,1], [0,1], [2,1], trust,
                                       lambda x: np.ones(1), *no_penalty(2))


if __name__ == '__main__':
    unittest.main()
