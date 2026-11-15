"""Verify persisted synthetic inputs before cache use and report publication."""

from pathlib import Path
from .renderer import digest


def input_checksums(pairs, looks):
    """RAW hashes are required; older manifests may omit derived-file hashes."""
    expected = {}

    def add(path, sha):
        path = str(Path(path).resolve())
        if not isinstance(sha, str) or not sha:
            raise ValueError(f"Missing input checksum: {path}")
        if path in expected and expected[path] != sha:
            raise ValueError(f"Conflicting input checksums: {path}")
        expected[path] = sha

    for pair in pairs:
        add(pair["raw"], pair.get("raw_hash"))
        for field in ("baseline_full", "baseline_preview"):
            if field + "_sha256" in pair:
                add(pair[field], pair[field + "_sha256"])
        for look in looks:
            proof = look.get("target_provenance", {}).get(pair["id"], {})
            if "output_sha256" in proof:
                add(look["targets"][pair["id"]], proof["output_sha256"])
    return expected


def verify_checksums(expected):
    for path, sha in expected.items():
        if digest(path) != sha:
            raise ValueError(f"Dataset input checksum mismatch: {path}")
