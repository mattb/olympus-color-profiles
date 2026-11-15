# Stock and HSL Olympus profile fitting

`omfit` deterministically fits actual native Olympus renders to ICC-tagged edited
references. The core is bounded regularized least squares, measured local finite
differences, integer candidates and acceptance on actual rendered loss. No LLM
or Workspace UI is involved. Installed Olympus frameworks, `exiftool`, `uv` and
an Apple Silicon Mac are required. Python dependencies are pinned in `uv.lock`.

```sh
cd /path/to/omworkspace-control
./omfit optimizer/examples/held-out.json --mode stock \
  --output /absolute/path/new-stock-run --cache /absolute/path/cache
./omfit optimizer/examples/held-out.json --mode hsl \
  --output /absolute/path/new-hsl-run --cache /absolute/path/cache
uv run --project optimizer python -m unittest discover -s optimizer/tests -v
```

`--mode` is mandatory: **stock** has 12 saturation controls ±5 and neutral H/L;
**hsl** has 12 saturation, 12 hue and 12 luminance controls ±7, representing the
unofficial HSL firmware. Both fit shared highlight/shadow ±7. HSL here validates
the desktop engine/control recipe; it does not install firmware or establish
physical-camera equivalence. Native development is 16-bit internally; fitting
and full-resolution validation export native 8-bit TIFF, matching the JPEG
reference's precision. Midtone, shading and other picture modes are not searched.

## Renderer invocation and batches

The default command is `omrender` from **PATH**. If absent, the adjacent repository
launcher is used. `--renderer COMMAND_OR_PATH` overrides this. No renderer is
copied, pinned by content, or rejected because it updates. Each phase observes
`omrender inspect`, resolves the current native build, and explicitly passes that
same `--build-dir` to `omrender batch`. `--build-dir DIR` optionally selects a
particular build. Launcher/native hashes are provenance and cache namespace
inputs, not update-blocking checks. Changes during a run are recorded as
`mixed_renderer_versions`; cached entries from earlier versions remain separate.
As requested, the fitter does not prevent mid-run renderer updates. Such runs
should not be described as a single fixed-engine reproducibility test.

GPU is required by default (`--backend gpu`). `--backend cpu` is an explicit
alternative; `--backend auto` permits the renderer's documented fallback.
Every native sidecar is checked for actual backend, control readback and output
dimensions. Reports retain actual backends, executable invocation, process IDs
and native batch reports. A failed development is not retried on another backend.

The initial image set, each **complete Jacobian probe set**, joint candidate
checks, fallback checks and reporting sets are submitted as batches. One native
process and GPU context persist across all jobs in each batch. Adaptive phases
start a new batch after scores determine the next candidates; this is not an
interactive renderer daemon persisting across the entire optimization. Process
counts refer to native development processes, excluding cheap capability queries.

## Manifest

JSON contains `pairs`, each with:

- `id`: unique safe filename component.
- `raw`, `target`: absolute paths or paths relative to the manifest.
- `group`: photos sharing one style, default `default`.
- `role`: `train` or `validation`, default `train`.
- `initial`: `[Kelvin/100, AB, GM, EV_thirds]`, default `[53,0,0,0]`.

Kelvin is 2000..14000K in 100K steps; AB/GM ±7; exposure ±1EV in thirds.
Training photos have independent fitted WB/exposure. Held-out photos keep their
**declared** WB/exposure unchanged and never contribute to the objective, shared
profile, early stopping or candidate selection. This conditional style-transfer
test does not demonstrate automatic WB estimation on unseen scenes. Each group
needs training images and budget for its complete initial evaluation.

The manifests in `examples/` are portable user-supplied-photo templates. Copy them beside your own RAWs and ICC-tagged targets and replace the scene values. No historical private study photographs are required or bundled. See the [user guide](../docs/users/fit-profiles.md).

## Separate style, scene and reproduction outputs

| Location | Contains | Intended use |
|---|---|---|
| `profiles/<group>-<mode>.json` | Shared S/H/L, highlight/shadow, finishing, mode/hardware labels | Reusable style recipe; **no WB or exposure** |
| `profiles/<group>-<mode>.oes` | Same style in Workspace preset form | Style preset; **no WB or exposure tags** |
| `adjustments/<photo>.json` | WB and exposure, train/held-out role and origin | Per-photo corrections; **no wheel or tone recipe** |
| `settings/<photo>.json` | Combined profile + scene native settings | Exact preview reproduction, not advertised as reusable |
| `settings/<held-out>-full.json` | Combined settings without resize | Full-resolution reproduction |
| `comparisons/<photo>.jpg` | Target, initial and final | Same ICC→sRGB conversion used by scoring, with explicit sRGB ICC |
| `diagnostics/`, `registrations/`, `batches/`, `events.jsonl` | Frozen geometry, native commands/readbacks and process evidence | Audit/debugging |
| `result.json` | Metrics, histories, separated profile/adjustment references, versions | Machine-readable report |

OES is a Workspace preset, not a camera backup or USB upload. Natural finishing is
explicit. Unexposed noise/lens/sharpening settings remain inherited from the ORF;
this is not a complete reset of every development parameter. Creative WB intent
cannot be uniquely inferred alongside free per-photo WB, so no fitted scene WB
is silently exported as a shared creative look.

## Fixed fitting and validation policy

1. Initial neutral wheel/tone, declared WB/exposure, 800-pixel long edge. Crop
   dimensions and orientation come from ORF metadata, not sensor-border dimensions.
2. ICC→sRGB, relative colorimetric intent. SIFT ratio .75 and seeded affine RANSAC;
   reject <20 inliers, <25% inliers, >2-degree rotation, extreme scale, or <85%
   interior coverage. Freeze the transform per photo.
3. For fitting, resize to 96×96, Gaussian sigma .7, D65 Lab. Fixed valid-coverage
   mask excludes outer four pixels. Equal image weights. Objective is squared
   Lab residual plus L2 wheel .01, circular smoothness .03, tone .01, scene-prior
   .01. Penalty normalizations are explicit in `core.regularizer`.
4. Fixed-order one-sided unit probes, backwards at the upper bound. BVLS tolerance
   1e-10, max500 solver steps. Trust region: two wheel/tone/axis/EV steps and500K.
   Render rounded full/half joint steps; if neither improves, try four
   gradient-ranked unit moves. Probes can win. Tie rules: objective rounded to12
   places, squared vector norm, lexicographic integer order.
5. Accept actual improvement >0.0001, remeasure after each accepted move. Default
   budget-governed continuation with a100-iteration safety cap and200 unique
   requests per training photo (`--render-budget-per-photo 200`). An explicit
   `--max-renders N` overrides this with an absolute group cap. Scaling by photo
   count affords complete HSL Jacobians and four two-step moves to reach±7.
   `--iterations 3 --max-renders 200` retains the earlier prototype allocation.
   Cache hits consume the same search budget as misses. A partial final Jacobian
   never produces an unrendered winner; return the best completely scored vector.
   Preparation and reporting renders are outside the search budget.
6. Report baseline, style-only (declared scene), fully fitted scene, and zero-wheel
   ablation with tone/WB/exposure fixed. Lab RMSE and mean CIEDE2000 are distinct;
   ΔE00 is reported, not the primary acceptance objective.
7. By default render held-out baseline/final/ablation at **full developed pixel
   dimensions** without resize. Scale the frozen registration mathematically;
   do not re-register candidates. Score every valid interior pixel in row tiles,
   without the fitting blur/downsample. Report actual dimensions and pixel count.
   `--skip-full-validation` is explicitly marked in policy when requested.

A held-out `improved` label means mean full-resolution ΔE00 improved against its
fixed-scene baseline. It is not an automatic deployment decision; all small-data
recipes remain provisional, and individual image metrics remain visible.

## Operational limits

Output directories must be new. Cache entries are immutable and checked for
TIFF/readback corruption. An interrupted/incomplete entry fails with its path;
inspect its batch log and remove only that incomplete entry before retrying.
Do not run concurrent jobs against one cache. Native batches default to4096MiB
RSS and a job-count-based timeout. stdout contains a single JSON result pointer;
commands, stderr and reports are retained in `batches/`.

This local integer search is not globally optimal. Stock controls cannot reproduce
arbitrary Lightroom masks, local edits, film LUTs or curves. No held-out reference
is used to tune the recipe after seeing validation scores. Research recommendations
and the distinction between demonstrated methods and experiments are in
community survey (historical private study; see [compatibility](../docs/compatibility.md)).


## Empirical tuning and synthetic film benchmarks

See empirical decisions (historical private study; see [compatibility](../docs/compatibility.md)) for adoption/discard evidence
and a reproducible final HSL validation command.

The production default keeps Lab loss, the original regularization and two-step
trust region. Measured budget-aware continuation replaced the arbitrary three
round stop. Full-resolution preselected Velvia tests improved scene-mean ΔE00
4.76045→4.54469 (E-M10II:4 eligible frames/3 timestamp groups) and
3.43894→3.29419 (PEN-F:2frames/1group); every primary frame improved. These are
small conditional tests, not physical-film or broad camera qualification.
PEN-F HSL confirmation also passed: 2.39707→2.37005 (1.13%), both test frames
improved, using600 versus363 logical requests. This modest gain costs more
renders; the evidence still covers only one independent PEN-F test group.

Jacobian diagnostics are report-only: response norms, exact-zero controls,
rank/conditioning and collinearity are saved under `diagnostics/`. Regularization
is not observational evidence. Zero/weak responses are not globally frozen after
one linearization. Higher-res scoring, capped hue/lightness weighting, stronger
penalties, directional models and polishing remain explicit benchmark experiments,
not hidden defaults. A larger squared-ΔE00 objective was inconsistent across looks
and regressed the HSL check; relative Lab-delta targets improve a different goal
while worsening absolute-match ΔE00 on the tested Lightroom pairs.

`dataset.py`, `benchmark.py`, `validate_benchmark.py` and `relative_benchmark.py`
provide reproducible experiment entry points (`python -m omfit.<module> --help`).
They create full native baseline → ICC-managed RGB → full3DLUT → full tagged PNG
pairs. Resize happens after the LUT, since these operations do not commute.
Synthetic pairs test compression of a known transform into camera controls;
they are not real film scans, grain simulation or approximate XMP interpretation.

The active corpus is20 user RAWs sampled without replacement from the user's
512-path list with seed20261113:12E-M10II and8PEN-F, fitted separately. One
identical-content duplicate was excluded before sampling. Timestamp-connected
bursts stay together; invalid timestamps need a conservative camera/folder
eligibility audit. Two undated E-M10II test frames are secondary diagnostics,
not part of the primary independent test metric. Film targets include6color
transforms and Tri-X400,HP5Plus400,Delta100 monochrome transforms. Licenses,
pinned source revisions, attribution, checksums and exact generation order are
retained beside dataset manifests; private photographs are not redistributed.

The neutral-color baseline experiment and inherited-WB robustness experiment
remain separate. Fixed5300K is a controlled encoding, not proof of correct scene
neutrality. The inherited-WB version reduced some clipping but failed the
predeclared broad-color-coverage gate. Training/dev scene-group cross-validation
therefore broadens calibration without silently changing the random draw or
using final-test candidate scores for selection.

Comparison JPEGs now use both the scoring ICC conversion and the fixed reference
registration. Generated sRGB ICC headers use a fixed valid creation date to avoid
metadata-only byte differences across runs. Full-resolution scoring remains
unblurred; display JPEGs are previews and are not scoring artifacts.

## Native MONO fitting

`--mode mono` uses the renderer's genuine `stock_pen_f_mono` family. It enumerates
25 categorical color-filter states at neutral tones, then locks the selected
filter while measured integer search fits contrast and highlight/shadow. This is
a staged search, not a joint global optimum. Filter numbers have no numeric
penalty or derivative. Contrast is -2..2, highlight/shadow -7..7. Shading and
sharpness stay zero, grain stays off and toning neutral. Reusable JSON/OES recipes
exclude per-photo WB/exposure. MONO output labels the filter ablation `zero_filter`.

For generated, exactly aligned LUT targets, use `--freeze-scene` to preserve the
known WB/exposure anchors and `--identity-geometry` to declare pixel alignment.
Do not declare identity for independently cropped/edited reference photographs.
By default real-photo fits retain per-photo adjustment fitting and registration.

Native batches are split into at most50 uncached photo-candidate jobs per process,
without changing evaluator ordering or logical budgets. `--batch-size 1..50`
can lower this limit while native memory work continues. Each chunk reuses one
GPU context. Current MONO qualification uses the explicitly supplied build:

```bash
./omfit /absolute/paired-manifest.json --mode mono \
  --output /absolute/new-fit --cache /absolute/cache \
  --build-dir .build/native \
  --batch-size 50 --freeze-scene --identity-geometry
```

Profile JPEG export and physical camera loading remain separate, deliberate final
operations. Optimizer candidate evaluation never opens a camera connection.

## Adobe / Lightroom preset fitting (experimental)

`./omfit adobe manifest.json --output NEW_DIR --cache CACHE --mode mono`
fits Adobe Develop settings against paired Olympus renders, then writes an XMP
preset and separate scene adjustments. It uses the installed Adobe DNG Converter
and adjacent scratch XMP to produce full-size embedded previews. Original ORFs
and sidecars remain untouched. `--converter` selects another executable.

Manifest `pairs` contain `id`, `raw`, `target`, and `role` (`train` or `validation`).
Optional `scene` defines frozen `WhiteBalance`/`Exposure2012`, or Custom WB with
Temperature/Tint. Targets require ICC profiles. Default registration uses image
features; `--identity-geometry` is only for known identical alignment.

MONO fits eight B&W mixer controls and five tone controls in five-unit steps.
Color mode fits the five tone controls, Vibrance/Saturation, and eight-sector
hue, saturation and luminance (31 shared controls total). Color trust steps are
20 slider units per iteration; MONO uses10. `--initial-preset FILE.xmp` seeds
only shared controls, rounded to the nearest five units, while baseline metrics
remain measured against the neutral Adobe baseline. Seed treatment must match
the selected fitting mode. `--camera-profile "Camera Natural"` explicitly selects
a fixed Adobe base for baseline, fitting and exported preset; the default remains
Adobe Standard. Actual Converter readback verifies profile availability. A
training-only base-profile probe (historical private study; see [compatibility](../docs/compatibility.md)) motivates
a separate Camera Natural Velvia candidate. `--max-renders` limits logical training
requests; baseline and reporting renders are additional. The shared preset excludes
WB/exposure. Outputs include actual Adobe readbacks, canonical sRGB comparisons,
held-out full-resolution metrics and explicit parity/import qualification flags.

This backend extracts Adobe-generated `JpgFromRaw`, never the Olympus MakerNote
preview. It converts sRGB or Gray Gamma2.2 according to DNG metadata into tagged
sRGB. Unknown color spaces fail. It requires ExifTool and system LittleCMS2 for
gray profile construction. JPEG quantization remains part of this rendering path.

DNG Converter preview validation does not establish matching Lightroom TIFF
exports or a successful Lightroom preset import. Those remain separate acceptance
checks; each new fit retains unvalidated flags until externally tested. See
Adobe renderer research (historical private study; see [compatibility](../docs/compatibility.md)).

Historical control qualification passed 99 unit tests; the release ledger records the current suite. All24 HSL controls and both global color
controls pass actual Converter XMP readback; perturbing each HSL family or global
control changes the rendered pixels. See
control measurements (historical private study; see [compatibility](../docs/compatibility.md)). Installed Converter B&W mixer and contrast
perturbations produce measured pixel changes; fresh baseline pixels repeat exactly.
A 30-request MONO fit against our Olympus Pan F render improves full-resolution
held-out DeltaE00 from3.68323 to1.63828 (one training and one held-out photograph).
Re-reading the exported preset and combining it with frozen scene settings produces
pixel- and ICC-exact output in a fresh Converter run. This validates the Converter
path. Warm replay reproduces the exact vector, objective and search history with
zero new renders. Actual Lightroom Classic 16.0 preset import/application also passes
on the two isolated test copies. Full-resolution TIFF16 exports preserve every fitted
control, dimensions and orientation; ICC-managed mean DeltaE00 versus Converter
previews is 0.3165 (portrait) and 0.3923 (landscape), with P95 0.9980/1.1333.
Pixel-exact parity fails. Lightroom initially uses process15.4 despite preset11.0;
a controlled process11.0 landscape export gives essentially unchanged error
(0.39223). Lightroom TIFF16 repeats also vary slightly. These observations qualify
a close visual approximation for this preset and these installed versions only.
See Lightroom validation (historical private study; see [compatibility](../docs/compatibility.md)).

A separate native HSL target-to-Adobe test verifies all 36 native HSL values and
actual Lightroom import of all 31 fitted/all 45 persistent style controls. Its initial
full-frame TIFF16 comparisons **fail** the predeclared practical parity gate
(mean≤1, P95≤2): meanΔE00 1.9623/2.0709 and P95 4.9872/5.0117. The original failure
and one controlled ProcessVersion11 diagnostic are retained separately in
HSL Lightroom qualification (historical private study; see [compatibility](../docs/compatibility.md)). The separate
[research HSL preset](recipes/lightroom/penf-hsl-velvia-research.xmp) retains this
failed pixel-parity qualification; the six stock preset files are unchanged.
This is native desktop HSL validation; physical patched-camera rendering remains
untested. New fits retain unqualified Lightroom parity flags.

The preset includes its fixed Adobe baseline (including detail/noise/lens settings),
so applying it resets those included controls as well as applying the fitted look.
Example: `optimizer/recipes/penf-panf-adobe-experimental.xmp`. Validation evidence:
adobe-validation.json (historical private study; see [compatibility](../docs/compatibility.md)). Original source photos,
profile-study final renders and reports were preserved during authorized cache
cleanup; its deletion manifest lives beside the private study artifacts.

The development studies included six COLOR/MONO Lightroom approximations. The public candidate includes only assets selected by its rights-reviewed allowlist; forum-derived COLOR recipes remain on hold. See [profile attribution](recipes/lightroom/ATTRIBUTION.md) and [release blockers](../legal/RELEASE-BLOCKERS.md). Fresh Converter replay does not establish actual Lightroom TIFF parity for every look.
