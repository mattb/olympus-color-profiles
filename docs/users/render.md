# Render and batch

Start with the [quickstart](../quickstart.md). Generate complete settings with `./omrender settings --profile stock|mono|hsl --output /absolute/new-settings.json` (replace the profile choice with one value). Validate them before rendering. Use `--backend auto|gpu|cpu` and an explicit `--build-dir` only when selecting a nondefault build.

The JSON distinguishes `profile` (shared creative controls), `raw_overrides` (photo development adjustments), and `output` (depth, rotation, optional resize). Inheritance from ORF shooting parameters remains explicit. Neutral wheel values are not a universal reset.

Use `batch JOBS.json --report /absolute/new-report.json` for bounded candidate sets, reusing one native GPU context. Optimizer batches are limited to 50 jobs. Jobs and reports must use new output paths. See the exact job schema, time/memory bounds and native report fields in the [CLI reference](../CLI-HELP.md).

Use `compare` only for decoded sample/ICC comparison; it does not color-convert or align photos. Fitting comparisons instead use the scoring ICC/geometry path. Do not equate file hashes of encoded TIFFs with decoded pixel equality.
