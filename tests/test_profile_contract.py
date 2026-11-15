"""File-only camera-profile contract: reject lossy transfer and ambiguous targets."""
import importlib.machinery
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('omrender_cli', str(ROOT / 'omrender'))
spec = importlib.util.spec_from_loader(loader.name, loader)
cli = importlib.util.module_from_spec(spec)
loader.exec_module(cli)


def metadata():
    return {
        'stock_wheel_transport_eligible': True,
        'native_camera_loader': {'accepted': True, 'would_adjust_parameters': False},
        'path': '/new/profile.jpg', 'jpeg_sha256': 'a' * 64,
        'saturation': {'values': [-3, -2, -1, 0, 1, 2, 3, 4, 5, -4, -5, 2]},
        'finishing_mode': {'value': 9},
        'highlight_shadow_metadata': {'status': 0, 'bright': 4, 'dark': -2},
        'midtone_metadata': {'status': 0, 'value': 1},
        **{k: {'status': 0, 'value': 0} for k in ('contrast', 'sharpness', 'shading')},
    }


class ProfileContractTests(unittest.TestCase):
    def test_non_neutral_recipe_and_explicit_destination(self):
        m = metadata()
        for bank in ('current', 'c1', 'c2', 'c3', 'c4'):
            for slot in (1, 2, 3):
                plan = cli.profile_plan(m, bank, slot)
                self.assertEqual(plan['destination'], {'bank': bank, 'color_slot': slot})
                self.assertEqual(plan['camera_profile']['saturation'], m['saturation']['values'])
                self.assertEqual(plan['camera_profile']['midtone'], 1)
                self.assertFalse(plan['hardware_operations'])
                self.assertNotIn('white_balance', plan['camera_profile'])
                self.assertNotIn('development_exposure', plan['camera_profile'])

    def test_refuses_hsl_or_non_profile_carrier(self):
        m = metadata(); m['stock_wheel_transport_eligible'] = False
        with self.assertRaisesRegex(ValueError, 'verified supported stock COLOR or MONO profile carrier'):
            cli.profile_plan(m, 'current', 2)

    def test_refuses_native_tone_clamping(self):
        for key, field in (('highlight_shadow_metadata', 'bright'),
                           ('highlight_shadow_metadata', 'dark'),
                           ('midtone_metadata', 'value')):
            for value in (-8, 8):
                m = metadata(); m[key][field] = value
                with self.assertRaisesRegex(ValueError, 'clamp'):
                    cli.profile_plan(m, 'current', 2)

    def test_refuses_unreadable_inherited_field(self):
        for key in ('contrast', 'sharpness', 'shading', 'midtone_metadata', 'highlight_shadow_metadata'):
            m = metadata(); m[key]['status'] = -1
            with self.assertRaises(ValueError):
                cli.profile_plan(m, 'c4', 3)

    def test_readback_exact_subset_preserves_other_settings(self):
        expected=b'1,PEN-F,3.1,S,Current,current\r\n2,PARAM_A,MODE_STEP_P4\r\n3\r\n'
        actual=b'1,PEN-F,3.1,S,Current,current\r\n2,OTHER,KEEP\r\n2,PARAM_A,MODE_STEP_P4\r\n3\r\n'
        self.assertTrue(cli.verify_camera_readback(expected,actual)['verified'])
        self.assertFalse(cli.verify_camera_readback(expected,actual.replace(b'MODE_STEP_P4',b'MODE_STEP_P3'))['verified'])
        self.assertFalse(cli.verify_camera_readback(expected,actual.replace(b'Current',b'Myset1'))['verified'])
        self.assertFalse(cli.verify_camera_readback(expected,b'\xff\x00opaque')['verified'])

    def test_no_default_or_source_inferred_destination(self):
        for bank, slot in ((None, 2), ('current', None), ('c5', 2), ('current', 0), ('current', 4)):
            with self.assertRaises(ValueError):
                cli.profile_plan(metadata(), bank, slot)


if __name__ == '__main__':
    unittest.main()
