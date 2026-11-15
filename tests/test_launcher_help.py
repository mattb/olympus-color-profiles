"""Help is usable before installation and keeps the full reference discoverable."""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class LauncherHelpTests(unittest.TestCase):
    def test_subcommand_help_does_not_need_required_inputs_or_native_build(self):
        result = subprocess.run([sys.executable, str(ROOT/'omrender'), 'render', '--help'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('usage:', result.stdout)
        self.assertIn('--settings', result.stdout)
        self.assertLess(len(result.stdout.splitlines()), 100)

    def test_full_guide_comes_from_one_reference(self):
        result = subprocess.run([sys.executable, str(ROOT/'omrender'), 'guide'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), (ROOT/'docs/CLI-HELP.md').read_text().strip())


if __name__ == '__main__':
    unittest.main()
