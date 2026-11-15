import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from omfit.dataset_integrity import input_checksums, verify_checksums
from omfit.renderer import digest
from omfit.validate_benchmark import run as validate


class DatasetIntegrityTests(unittest.TestCase):
    def test_raw_baselines_and_targets_checked_before_and_after(self):
        with TemporaryDirectory() as d:
            paths = {
                k: Path(d) / k
                for k in ("raw", "baseline_full", "baseline_preview", "target")
            }
            for k, p in paths.items():
                p.write_bytes(k.encode())
            pair = dict(
                id="photo", raw=str(paths["raw"]), raw_hash=digest(paths["raw"])
            )
            for field in ("baseline_full", "baseline_preview"):
                pair[field] = str(paths[field])
                pair[field + "_sha256"] = digest(paths[field])
            look = dict(
                targets={"photo": str(paths["target"])},
                target_provenance={
                    "photo": dict(output_sha256=digest(paths["target"]))
                },
            )
            checksums = input_checksums([pair], [look])
            self.assertEqual(len(checksums), 4)
            verify_checksums(checksums)
            for name, p in paths.items():
                original = p.read_bytes()
                p.write_bytes(b"changed")
                with (
                    self.subTest(name=name),
                    self.assertRaisesRegex(ValueError, "checksum mismatch"),
                ):
                    verify_checksums(checksums)
                p.write_bytes(original)

    def test_legacy_derived_hashes_optional_but_raw_required(self):
        with TemporaryDirectory() as d:
            raw = Path(d) / "raw"
            raw.write_bytes(b"raw")
            pair = dict(id="photo", raw=str(raw), raw_hash=digest(raw))
            checksums = input_checksums([pair], [dict(targets={"photo": "unused"})])
            verify_checksums(checksums)
            self.assertEqual(len(checksums), 1)
            pair.pop("raw_hash")
            with self.assertRaisesRegex(ValueError, "Missing input checksum"):
                input_checksums([pair], [])

    def test_full_validation_rejects_wrong_dataset_before_renderer(self):
        with TemporaryDirectory() as d:
            dataset = Path(d) / "dataset.json"
            dataset.write_text("{}")
            record = Path(d) / "result.json"
            record.write_text(json.dumps(dict(source_data_hash="another-dataset")))
            # No renderer/output arguments: rejection must precede native setup.
            with self.assertRaisesRegex(ValueError, "source_data_hash"):
                validate(SimpleNamespace(dataset=str(dataset), results=[str(record)]))


if __name__ == "__main__":
    unittest.main()
