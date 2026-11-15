# Repository instructions

- Product entry points: root `omrender` and `omfit`. Native production source is `src/omrender.mm` plus its includes; Python package is `optimizer/src/omfit`.
- Read [compatibility](docs/compatibility.md), [build/test commands](docs/developers/build-and-test.md), and [release status](docs/release-readiness.md) for current authority. Full settings/output contract: `docs/CLI-HELP.md`. Historical investigations are not current support claims.
- Build: `./omrender build`; diagnose: `python3 scripts/doctor.py`. Default native output is ignored `.build/native`; explicit `--build-dir` remains supported.
- Checks: `python3 -m unittest discover -s tests -v`; `uv run --locked --project optimizer python -m unittest discover -s optimizer/tests -v`; file-only native checks: `python3 scripts/test-profile-readback.py`.
- Never silently stage concurrent native work or discard untracked production includes. Preserve source RAWs, private evidence and installed vendor files. Generated caches/builds do not belong in commits.
- Use the user's PATH-selected renderer; record actual backend/provenance without adding an update-blocking identity lock. Keep candidate batches ≤50 and actual rendered acceptance.
- Preserve ICC-managed scoring/comparisons, frozen held-out selection, and reusable styles without photo WB/exposure. Physical firmware equivalence and Lightroom parity require their own evidence.
- Camera writes require an explicit user-selected camera/destination. Do not run hardware uploads in CI/default tests or infer backup restorability from backup creation/readback.
- Keep unresolved rights marked in `legal/` and release gates; MIT does not cover third-party assets. No vendor binaries, private photos/serials, staged apps or backups in release artifacts. Do not publish without a separate user instruction.
- Do not expand the historical framework architecture manuscript as part of routine changes; use targeted research references only when needed.
