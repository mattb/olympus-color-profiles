import json
import unittest
import numpy as np
from skimage.color import rgb2lab
from omfit.relative import construct_relative_target


class RelativeTargetTests(unittest.TestCase):
    def test_no_edit_is_baseline_even_when_adobe_baseline_differs(self):
        base = np.array([[[.2, .3, .4], [.8, .4, .3]]])
        reset = np.array([[[.3, .5, .7], [.6, .4, .2]]])
        result = construct_relative_target(base, reset, reset)
        np.testing.assert_allclose(result['target_lab'], rgb2lab(base), atol=1e-12)
        np.testing.assert_allclose(result['display_rgb'], base, atol=1e-6)
        self.assertFalse(result['diagnostics']['display_is_scoring_target'])
        self.assertTrue(result['diagnostics']['changes_absolute_matching_objective'])
        json.dumps(result['diagnostics'], allow_nan=False)

    def test_same_baseline_as_reset_reconstructs_edited(self):
        base = np.array([[[.2, .3, .4], [.8, .4, .3]]])
        edit = np.array([[[.3, .2, .5], [.7, .4, .3]]])
        result = construct_relative_target(base, base, edit)
        np.testing.assert_allclose(result['target_lab'], rgb2lab(edit), atol=1e-12)
        np.testing.assert_allclose(result['display_rgb'], edit, atol=1e-6)
        self.assertFalse(result['out_of_gamut_mask'].any())

    def test_neutral_and_near_zero_chroma_have_no_hue_discontinuity(self):
        base = np.array([[[.0, .0, .0], [.5, .5, .5], [1., 1., 1.]]])
        reset = np.array([[[.1, .1, .1], [.4, .4, .4], [.8, .8, .8]]])
        edit = reset.copy(); edit[..., 0] += 1e-8
        result = construct_relative_target(base, reset, edit)
        expected = rgb2lab(base) + rgb2lab(edit) - rgb2lab(reset)
        np.testing.assert_allclose(result['target_lab'], expected, atol=1e-12)
        self.assertTrue(np.isfinite(result['target_lab']).all())
        self.assertLess(np.max(np.abs(result['target_lab']-rgb2lab(base))), 1e-4)

    def test_out_of_gamut_is_preserved_for_scoring_or_explicitly_projected(self):
        base = np.array([[[1., 0., 0.], [.5, .5, .5]]])
        reset = np.array([[[.3, .3, .3], [.5, .5, .5]]])
        edit = np.array([[[1., 0., 0.], [.5, .5, .5]]])
        preserved = construct_relative_target(base, reset, edit)
        clipped = construct_relative_target(base, reset, edit, gamut='clip_srgb')
        self.assertTrue(preserved['out_of_gamut_mask'][0, 0])
        np.testing.assert_allclose(preserved['target_lab'],rgb2lab(base)+rgb2lab(edit)-rgb2lab(reset))
        np.testing.assert_allclose(clipped['target_lab'],rgb2lab(clipped['display_rgb']))
        self.assertGreater(clipped['diagnostics']['mean_projection_error_lab'],0)
        self.assertEqual(preserved['diagnostics']['mean_projection_error_lab'],0)
        self.assertTrue(np.all((preserved['display_rgb']>=0)&(preserved['display_rgb']<=1)))
        np.testing.assert_array_equal(preserved['absolute_target_lab'],rgb2lab(edit))

    def test_uint8_and_validation(self):
        rgb = np.array([[[0,128,255]]],np.uint8)
        result = construct_relative_target(rgb,rgb,rgb)
        np.testing.assert_allclose(result['target_lab'],rgb2lab(rgb/255.))
        for bad in (rgb.astype(np.uint16),np.array([[[2.,0,0]]]),np.array([[[np.nan,0,0]]])):
            with self.assertRaises(ValueError):construct_relative_target(bad,rgb,rgb)
        with self.assertRaises(ValueError):construct_relative_target(rgb,rgb,np.zeros((2,2,3)))
        with self.assertRaises(ValueError):construct_relative_target(rgb,rgb,rgb,gamut='silent')

if __name__ == '__main__': unittest.main()
