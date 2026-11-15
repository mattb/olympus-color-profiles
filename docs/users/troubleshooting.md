# Troubleshooting

Run `python3 scripts/doctor.py` first. Keep its result with dependency/app versions when reporting setup failures, but remove personal paths and camera identifiers before sharing.

- Missing native build: run `./omrender build`; check a consistently selected `--build-dir`.
- Workspace not found: the tested runtime expects the official app at `/Applications/OM Workspace.app`; do not copy individual frameworks around to bypass setup.
- Installed optimizer cannot find renderer: install the companion renderer and use PATH or `--renderer /absolute/path/to/omrender`.
- Adobe unavailable: install Converter, ExifTool and a discoverable LittleCMS2 shared library, or skip the optional Adobe workflow.
- Existing output refused: choose a new output name/directory; do not remove source files to fix an output collision.
- GPU unavailable: inspect capabilities and select CPU explicitly if suitable. Do not claim GPU parity from CPU-only tests.
- Camera not detected: quit Workspace, verify power/data cable/Storage mode and inspect saved results. Never retry an uncertain upload before checking whether a write already occurred.

The [full reference](../CLI-HELP.md) documents exact exit/report semantics. Include a minimal reproducible settings file and a rights-cleared input only if needed; do not post backups or private photographs by default.
