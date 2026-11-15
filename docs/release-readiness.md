# Release candidate status

**Source publication authorized by the maintainer on 2026-11-15; legal and fresh-Mac qualification remain incomplete.** The curated source export is a smaller distribution boundary, not a rewrite or deletion of the development repository and its history.

Implementation checks and actual CPU/GPU RAW smoke results are recorded in [source-candidate validation](developers/release-validation.md). Build/install fixes, portable documentation/examples, packaging notices and the candidate exporter are implemented. Genuine fresh-Mac provisioning and the marked legal decisions remain outstanding.

## Candidate creation

After committing all intended production source and documentation:

```sh
python3 scripts/release-audit.py --ref HEAD --output ../candidate-source
python3 scripts/release-audit.py --tree ../candidate-source
```

The output directory must be new. Selection reads only the named commit, follows the production native include closure, preserves executable modes, records file hashes and exclusions, and excludes research/instrumentation, historical evidence, private experiment reports, generated environments, and community-recipe files under unresolved rights holds. Selection alone is available by omitting `--output`.

Audit rejects known personal home paths, the studied camera's identity pattern, credential patterns, symlinks, binary/media/vendor-profile/backup assets and held recipe filenames. This is a deterministic guard against known problems, not a complete secret scanner or legal clearance. A failed candidate is retained for inspection; the script neither deletes source files nor edits evidence to hide a finding. It never publishes, installs vendor applications or accesses a camera.

## Required checks

1. Build the exact exported commit in a directory containing spaces, without developer build caches or untracked includes.
2. Run root and optimizer unit/contract tests and file-only profile checks.
3. Install the optimizer wheel outside the checkout; verify companion renderer discovery and actionable missing optional dependency errors.
4. Follow [installation](install.md) and [quickstart](quickstart.md) on a genuinely fresh supported Apple Silicon Mac. Record actual versions and results. Host source-export tests do not satisfy this gate.
5. Qualify vendor-dependent RAW development, bounded persistent batches, native readbacks and repeat behavior separately. Use only owned or rights-cleared RAWs/references; do not distribute them by default.
6. Treat actual Lightroom qualification and physical USB writes as separate opt-in tests. Do not equate import/readback with exact render parity or a tested camera restore.
7. Resolve or explicitly exclude the issues in [legal release blockers](../legal/RELEASE-BLOCKERS.md), inspect the complete candidate archive, and decide public-history strategy separately.

The candidate manifest always records `publication_cleared: false`. Passing automated tests cannot clear contractual or provenance decisions. The exporter itself never publishes or changes visibility. The maintainer separately authorized pushing the curated source to `mattb/olympus-color-profiles`; package publication and release uploads remain separate actions.
