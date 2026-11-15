# OM Workspace control

Render Olympus RAW files with the locally installed OM Workspace desktop engine, fit reusable camera looks to edited references, and inspect or transfer selected PEN-F stock profiles.

Two commands are provided: **`omrender`** develops images and handles profile files; **`omfit`** searches measured renders for matching settings. Normal rendering does not drive Workspace's UI or require a connected camera. No proprietary frameworks are bundled.

This is unofficial software using undocumented interfaces. The verified native ABI is **OM Workspace 2.5.0.2 on Apple Silicon**. See the [compatibility matrix](docs/compatibility.md), [installation guide](docs/install.md), and [license scope](NOTICE.md). Publication remains blocked by the [release gates](docs/release-readiness.md), including unresolved vendor/provenance questions and genuine fresh-Mac qualification.

## First render

Install the prerequisites in the [installation guide](docs/install.md), then run from this checkout:

```sh
python3 scripts/doctor.py
./omrender build
RAW="/absolute/path/to/your-photo.ORF"
OUTPUT_DIR="/absolute/path/to/new-render-output"
mkdir -p "$OUTPUT_DIR"
./omrender capabilities --input "$RAW"
./omrender render "$RAW" --settings examples/settings/color-neutral.json \
  --output "$OUTPUT_DIR/neutral.tif"
```

Use your own compatible RAW; no sample photographs are bundled. Existing output files are protected. Neutral wheel settings retain other ORF shooting parameters; they are not a reset of every development setting. The default build is `.build/native`; `--build-dir` selects another build.

## Next tasks

- [Render and batch images](docs/users/render.md).
- [Fit a look](docs/users/fit-profiles.md), then inspect reusable profiles separately from per-photo adjustments.
- [Export, inspect and transfer a selected stock profile](docs/users/transfer-profiles.md). Only the explicit camera-load command writes a camera.
- [Create experimental Adobe presets](docs/users/lightroom.md). Successful preset import is separate from render parity.
- [Contribute or extend controls](CONTRIBUTING.md); coding agents start at [AGENTS.md](AGENTS.md).

The [complete CLI reference](docs/CLI-HELP.md) documents settings, native readbacks and failure semantics. Historical research is retained privately; the public candidate uses the current compatibility matrix rather than private reports.

Original code/documentation is [MIT licensed](LICENSE). Artistic profiles and dependencies have [separate terms](legal/THIRD-PARTY-NOTICES.md). Read the [unofficial-status and device/data limits](legal/UNOFFICIAL-STATUS-AND-RISKS.md). Nothing here supplies a license to vendor applications or firmware, or establishes physical unofficial-firmware equivalence.
