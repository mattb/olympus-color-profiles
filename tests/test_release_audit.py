import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

spec = importlib.util.spec_from_file_location('release_audit', Path(__file__).resolve().parents[1] / 'scripts/release-audit.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)

class ReleaseAuditTests(unittest.TestCase):
    def test_distribution_boundary(self):
        for name in ['instrumentation/stage.py', 'evidence/example.json', 'optimizer/experiments/results.json', 'FRAMEWORK-ARCHITECTURE.md', 'optimizer/recipes/lightroom/kodachrome25.xmp']:
            self.assertFalse(release.allowed(name), name)
        for name in ['omrender', 'optimizer/src/omfit/core.py', 'legal/RELEASE-BLOCKERS.md', 'docs/users/render.md']:
            self.assertTrue(release.allowed(name), name)

    def test_sensitive_content_is_reported_without_values(self):
        with TemporaryDirectory() as directory:
            tree = Path(directory)
            (tree/'example.txt').write_bytes(b'/Users/' + b'private-owner/photo.ORF')
            issues = release.audit(tree)
            self.assertEqual(issues, [{'path':'example.txt','issue':'personal_path'}])
            self.assertNotIn('private-owner', str(issues))

    def test_binary_and_held_recipe_are_not_cleared(self):
        with TemporaryDirectory() as directory:
            tree = Path(directory)
            (tree/'vendor.bin').write_bytes(b'\xcf\xfa\xed\xfe' + bytes(8))
            (tree/'velvia50.xmp').write_text('<xmp/>')
            issues = release.audit(tree)
            self.assertEqual(len(issues), 2)
            self.assertIn('community recipe rights hold', [x['issue'] for x in issues])

    def test_missing_documentation_link_fails(self):
        with TemporaryDirectory() as directory:
            tree = Path(directory)
            (tree/'README.md').write_text('[guide](missing.md)')
            self.assertEqual(release.audit(tree), [{'path':'README.md','issue':'missing or external local documentation target'}])

    def test_symlinks_are_rejected_without_reading_target(self):
        with TemporaryDirectory() as directory:
            tree = Path(directory)
            (tree/'link').symlink_to('/nonexistent-release-target')
            self.assertEqual(release.audit(tree), [{'path':'link','issue':'symlink forbidden in candidate'}])

if __name__ == '__main__': unittest.main()
