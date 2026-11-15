import json
import unittest
import numpy as np
from omfit.observability import analyze_jacobian


class ObservabilityTests(unittest.TestCase):
    def test_zero_is_not_learned_and_only_zero_frozen(self):
        j = np.array([[1., 0., 0.], [0., 0., 1e-250], [1., 0., 0.]])
        d = analyze_jacobian(j, ['supported', 'absent', 'tiny'])
        self.assertEqual(d['exact_zero_indices'], [1])
        self.assertEqual(d['default_local_freeze_mask'], [False, True, False])
        self.assertFalse(d['controls'][1]['measured_response_supported'])
        self.assertFalse(d['controls'][1]['learned_value_claim_permitted'])
        self.assertTrue(d['controls'][2]['measured_response_supported'])
        self.assertGreater(d['controls'][2]['norm'], 0)
        self.assertTrue(d['remeasure_zero_controls_after_move'])
        json.dumps(d, allow_nan=False)

    def test_collinear_controls_not_individually_identified(self):
        j = np.array([[1., 2., 0.], [2., 4., 1.], [3., 6., 0.]])
        d = analyze_jacobian(j, ['a', 'twice_a', 'independent'])
        self.assertEqual(d['normalized_numerical_rank'], 2)
        self.assertTrue(d['normalized_rank_deficient'])
        self.assertEqual(d['numerically_collinear_pairs'][0]['indices'], [0, 1])
        self.assertFalse(d['controls'][0]['identifiable_from_data_numerically'])
        self.assertFalse(d['controls'][1]['identifiable_from_data_numerically'])
        self.assertTrue(d['controls'][2]['identifiable_from_data_numerically'])
        self.assertEqual(d['default_local_freeze_mask'], [False]*3)
        self.assertIsNone(d['normalized_condition_number'])

    def test_linear_combination_detected_without_pair_collinearity(self):
        j = np.array([[1., 0., 1.], [0., 1., 1.], [0., 0., 0.]])
        d = analyze_jacobian(j)
        self.assertEqual(d['normalized_numerical_rank'], 2)
        self.assertEqual(d['numerically_collinear_pairs'], [])
        self.assertTrue(all(not c['identifiable_from_data_numerically'] for c in d['controls']))

    def test_weak_ratio_is_optional_reporting_not_freezing(self):
        j = np.diag([1., 1e-6])
        d = analyze_jacobian(j)
        self.assertTrue(all(c['weak_response_by_configured_ratio'] is None for c in d['controls']))
        configured = analyze_jacobian(j, weak_relative_threshold=.01)
        self.assertTrue(configured['controls'][1]['weak_response_by_configured_ratio'])
        self.assertEqual(configured['default_local_freeze_mask'], [False, False])
        self.assertFalse(configured['weak_threshold_is_empirically_validated'])

    def test_empty_and_all_zero_controls(self):
        empty = analyze_jacobian(np.empty((3, 0)))
        self.assertEqual(empty['controls'], [])
        zeros = analyze_jacobian(np.zeros((2, 3)))
        self.assertEqual(zeros['numerical_rank'], 0)
        self.assertEqual(zeros['default_local_freeze_mask'], [True]*3)
        json.dumps(zeros, allow_nan=False)

    def test_underdetermined_and_invalid(self):
        d = analyze_jacobian(np.array([[1., 2.]]))
        self.assertTrue(d['normalized_rank_deficient'])
        self.assertFalse(any(c['identifiable_from_data_numerically'] for c in d['controls']))
        for j in (np.array([1.]), np.empty((0, 2)), np.array([[np.nan]])):
            with self.assertRaises(ValueError): analyze_jacobian(j)
        with self.assertRaises(ValueError): analyze_jacobian(np.eye(2), ['same', 'same'])
        for threshold in (0, -1, 2, True, np.nan):
            with self.assertRaises(ValueError): analyze_jacobian(np.eye(2), weak_relative_threshold=threshold)

if __name__ == '__main__': unittest.main()
