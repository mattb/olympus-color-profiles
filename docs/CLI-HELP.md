---
name: omrender
description: Render Olympus ORFs through installed OM Workspace for stock PEN-F COLOR, native MONO and experimental firmware-HSL fitting; export verified recipe JPEGs and load camera profile memories.
---

# OM Workspace native renderer

This is the complete command/settings contract. The [compatibility matrix](compatibility.md) is the authority for current supported scope; numerical/hardware observations below retain their experiment-specific limits.

Use this CLI when matching Olympus desktop RAW development matters. It loads
installed proprietary frameworks into a fresh standalone arm64 process. It does
not drive Workspace's UI, extract embedded JPEG previews, use USB RAW development,
or invoke a substitute RAW engine. Workspace need not be running. No framework
binaries are bundled. The current verified ABI is OM Workspace 2.5.0.2 on Apple
Silicon; an app update requires revalidation. Current parameter readback supports
the DC11 engine used by the E-M10 II test ORFs and the PEN-F test input. Other engines fail closed.

The native 16-bit desktop TIFF pipeline is the default, with GPU selected
automatically when available. A GPU initialization failure in auto mode is
reported and selects CPU; --backend gpu requires GPU and fails instead of
falling back. There is no silent retry after a development error. Native GPU
TIFF16 and TIFF8 output is pixel-exact with matched Workspace exports for the validated
inputs/settings. This is not physical PEN-F or hacked-firmware ISP validation.

## Current validation status

On Apple M1 Max / Workspace 2.5.0.2, native Peony GPU development executed 393
successful Olympus OpenCL kernels per 16 MP input. All eight TIFF16/TIFF8 baseline /
sector0 comparisons for the two E-M10 II acceptance ORFs have EXACT decoded pixels
and identical ICC profiles with Workspace. All 12 saturation controls and 24 H/L
controls were perturbation-tested; current GPU 36+6 nuisance settings, repeated
A/B/A candidates, mixed CPU/GPU selection, and clean-home independence were tested.

Warm two-image GPU batches measured about 2.5 seconds versus desktop 2.84–2.96 seconds.
First-process GPU context setup adds startup cost; single-image process latency
must not be confused with warm development throughput. Use batch for an optimizer.
CPU remains available for explicit comparisons; its rounding can differ slightly
from desktop GPU output. Physical profile upload/readback is tested separately; no firmware installation is performed.

## Discover, build, and render

Run from the repository or use its absolute executable path:

```sh
cd /path/to/omworkspace-control
./omrender inspect
./omrender build
./omrender settings --profile stock --output /absolute/new-settings.json
./omrender validate /absolute/new-settings.json
./omrender render /absolute/input.ORF --settings /absolute/new-settings.json \
  --output /absolute/new-output.tif
./omrender compare /absolute/workspace-reference.tif /absolute/new-output.tif
```

`build` requires the installed Xcode command-line compiler and Apple SDK. It
writes only own compiled harnesses under
`.build/native` unless `--build-dir DIR` is
provided. Use the same `--build-dir DIR` on `render` and `compare`.
The launcher supplies both DYLD_FRAMEWORK_PATH and DYLD_LIBRARY_PATH pointing to
the installed app's Frameworks directory. This resolves XMPCore dependencies;
linker rpath alone is insufficient. No app configuration edits or Workspace caches are needed. GPU programs load from installed encrypted resources; tests confirmed the app's compiled-cache path produces the same pixels. A capability/protocol check rejects stale native binaries before writing output artifacts.

All data/report commands emit JSON. `build` prints artifact paths/compiler output.
`--help` prints this complete agent guide; `SUBCOMMAND --help` prints the same complete guide.
Image, settings and report outputs are protected from overwriting. Builds replace compiled executables atomically. Create the output parent directory first.

## Commands and options

- `inspect [--build-dir DIR]`: report installed app version, architecture and resolved native build.
- `capabilities [--input FILE.ORF] [--build-dir DIR]`: report native features; include an ORF to query verified MONO support, legal controls and native startup RNG policy for that input. No camera session or output pixels are created.
- `build [--build-dir DIR]`: compile native renderer and pixel comparator.
- `settings --profile stock|hsl|mono [--backend auto|gpu|cpu] [--output FILE]`: emit a complete neutral JSON
  template. The default profile is stock. Without --output, print JSON.
- `validate SETTINGS.json`: validate schema/ranges only. This neither loads an
  ORF nor proves capability, transfer, or renderer equivalence.
- `batch JOBS.json --report NEW.json [--backend auto|gpu|cpu] [--build-dir DIR] [--timeout 600] [--max-rss-mb 2048]`: preflight and render a job array in one native process, reusing the initialized native GPU context.
- `render INPUT.ORF --settings FILE --output NEW.tif [options below]`:
  render one ORF in a fresh process and write TIFF plus provenance sidecars.
- `compare REFERENCE CANDIDATE [--build-dir DIR]`: decode both image files and
  report dimensions, depth, ICC identities, sample hashes, exact equality,
  changed pixels/channels, MAE, RMSE and maximum error. No color conversion or
  geometric alignment occurs. Hash canonical samples, not encoded TIFF bytes.

Render overrides, applied after the JSON settings:

| Option | Meaning |
| --- | --- |
| `--backend auto\|gpu\|cpu` | Backend selection; default auto prefers a verified GPU. Explicit gpu never silently falls back. |
| `--saturation CSV12` | Twelve signed sector saturation values; use `--saturation=-1,0,...` for a leading minus. |
| `--hue CSV12` | Twelve signed hue sliders; requires HSL settings. |
| `--luminance CSV12` | Twelve signed luminance sliders; requires HSL settings. |
| `--kelvin INT --ab INT --gm INT` | Explicit Custom2 WB, AB/GM -7..7; unspecified AB/GM use the explicit tuple in settings or zero when Kelvin starts a new tuple. |
| `--exposure RATIONAL` | Exposure EV, e.g. `0`, `-0.3`, or `-3/10`; exact int32 numerator/denominator; use `--exposure=-3/10` for a negative fraction. |
| `--highlight INT --shadow INT --midtone INT` | Manual tone controls; unspecified values use explicit settings, otherwise zero. Nonzero midtone is rejected on cameras that lack it. |
| `--bits 16\|8` | Always develop16; TIFF16 uses lossless encoding, TIFF8 uses installed FileSave quantization after the desktop filters. Default16. |
| `--rotate 0|90|180|270` | Olympus rotation angle, explicit; no automatic EXIF transform. For the two supplied portrait E-M10 II ORFs, use 270 to match Workspace export. |
| `--resize WIDTH HEIGHT` | Olympus native resize (quality1); optional. Omit for lossless full-resolution comparison. |
| `--timeout SECONDS` | Per-process wall limit, default 120. |
| `--max-rss-mb MB` | Native child RSS limit, default 2048. |
| `--build-dir DIR` | Directory holding compiled native harness. |

For batch, JOBS.json is a nonempty array:

```json
[
  {"input":"/absolute/photo.ORF","settings":"/absolute/A.json","output":"/absolute/A.tif"},
  {"input":"/absolute/photo.ORF","settings":"/absolute/B.json","output":"/absolute/B.tif"}
]
```

Relative job paths resolve against the manifest directory. OES paths resolve
against each settings file. All output names are preflighted before any render;
duplicates/existing artifacts fail. --backend overrides all jobs, otherwise each
settings file controls its backend. Native settings are applied anew per image;
A/B/A and mixed CPU/GPU tests verify isolation. On a native error the batch stops;
already completed outputs/sidecars remain valid. Use new paths when retrying.
The batch report/log/effective-jobs manifest are separate from per-image reports.

Run candidate renders serially unless you have measured memory and CPU headroom.
Observed native render RSS was approximately 1–1.5 GB. TIFF16 for a 16 MP input
uses about 96 MB before metadata; compare two images can consume hundreds of MB.
Keep baselines and selected candidates; delete disposable intermediates only
when authorized, after recording pixel hashes/statistics.

## Settings contract

```json
{
  "schema": "omrender/1",
  "inherit": "orf_shooting_parameters",
  "decode_instructions": 0,
  "backend": "auto",
  "profile": {
    "kind": "stock_pen_f",
    "mode": "manual",
    "saturation": [0,0,0,0,0,0,0,0,0,0,0,0]
  },
  "raw_overrides": {},
  "output": {"bits": 16, "rotate": 0}
}
```

All twelve sector values are required. `mode: manual` selects native profile
mode 2. Stock mode accepts saturation -5..5 and explicitly neutralizes desktop
H/L; there are no stock twelve-sector independent H/L controls. The desktop API
accepts -7..7, but that wider range is exposed only in `firmware_hsl_research`.
That profile kind requires all three twelve-element arrays: `saturation`, `hue`,
and `luminance`, each integer -7..7. These are native Olympus parameter sliders,
not degrees, percentages, or an approximate RGB/HSV transform.

Sector order (for all three arrays):

`yellow, orange, red, rose, magenta, violet, blue, azure, cyan, teal, green, lime`.

The CLI overrides the rendered profile directly; it does not write camera
COLOR1/2/3 memories. Those profile banks are a later transfer concern. Hacked
firmware has nonlinear luminance coefficients and native metadata behavior;
never substitute a linear slider-to-luminance model or assume a desktop match
proves camera equivalence. Embedded captured CMIO effects and the current slider
values are distinct; an explicit manual override intentionally replaces embedded
profile controls.

`inherit` is mandatory. Settings omitted from `raw_overrides` come from the ORF's
shooting defaults and installed engine resources. There is no implicit load of
the running Workspace session's edit history or preset. The JSON sidecar records
resolved procedure values and native current/default modes where recovered.
Mode 0 in a native display-parameter field often means shooting/default;
resolved wrapper getters can therefore differ. Do not equate an inherited
setting with an explicit neutral reset.

Optional `oes_file` is an absolute OES path or a path relative to SETTINGS.json.
The installed OMBatchProcess parser and OMRawDevControl transfer its raw settings
first. Explicit JSON profile arrays and raw overrides then take precedence.
The sidecar retains the decoded OES dictionary. Arbitrary post-development image
filters in OES files are not implemented by this raw-parameter bridge; use only
recovered raw settings. Do not mistake parser success for applying every OES edit.

Typed raw overrides (arrays are native integer tuples):

| JSON key | Value |
| --- | --- |
| `exposure_bias` | `[numerator, denominator]`; positive denominator; EV within ±5. |
| `custom_wb2` | `[kelvin, AB, GM]`; Kelvin 2000..20000, AB/GM -7..7. This tuple alone does not select WB mode. |
| `white_balance_mode` | Native uint16; 4 is Custom2. Prefer convenience WB flags for selecting Custom2. |
| `tone_control` | `[mode, highlight, shadow]` or `[mode, highlight, shadow, midtone]`; manual mode 1, shooting mode 0, tone values -7..7. Midtone capability varies by RAW/camera. |
| `contrast` | `[mode, value, adjust]` via native SetContrast. |
| `sharpness` | `[mode, value, adjust]` via native SetSharpness. |
| `global_saturation` | `[mode, value, adjust]`, distinct from the twelve-sector profile. |
| `color_space_mode` | Native color-space selector; 1=sRGB, 2=Adobe RGB; 0=shooting/default. |
| `finishing_mode` | Native picture-mode enum; prefer OES `FinishingMode` names when the mapping is unverified. |
| `gradation_mode` | Native uint16 gradation enum. |
| `noise_filter_setting_mode` | Native uint16 noise-filter selector. |

Mode selectors are not interchangeable: the wheel uses manual 2; tone control
uses manual 1. Unknown enum values are forwarded only through explicitly typed
JSON and can fail in the installed engine; use observed readbacks or a known OES
file. Do not guess camera-specific mode mappings. Remaining noise, false-color,
acnode, chromatic-aberration, shading and other controls are inherited and
reported where recovered, not silently advertised as fully exposed.

GPU pipeline order is native RAW YCbCr development, physical rotation, external
GPU MFTS lens correction, native YCbCr-to-RGB conversion, then TIFF. TIFF8 is written by the installed FileSave exporter; the generic
OlyIP2_ConvertTo8Bits shortcut is not equivalent. Distorting
before rotation gives small nonzero differences and is not the desktop pipeline.
The CPU alternative retains the earlier direct CPU path and is not claimed
pixel-identical to desktop GPU processing.

Output is integer RGB TIFF. The wrapper attaches the installed sRGB or Adobe RGB
ICC profile according to resolved color-space mode without transforming pixels.
In JSON (including batch settings), native resize is `"output":{"bits":16,"rotate":0,"resize":[800,600]}`. The two integers are width and height, not a long-side setting; omit `resize` for full resolution.

`rotate` is explicit, `resize` absent means full sensor-developed dimensions,
and aspect/crop handling must be matched deliberately against the reference.

## Artifacts and reproducibility

For `result.tif`, rendering writes:

- `result.tif`: developed pixels plus installed ICC profile.
- `result.tif.json`: input, app version, requested and native-read-back settings,
  decoded OES settings, dimensions/depth/channel order, ICC source and inheritance.
  It also records requested/used backend, native GPU device/type, context timing,
  process ID, per-stage timings, and renderer protocol. GPU availability is verified
  through a real GPU command queue and the Peony raw procedure, not a name alone.
- `result.tif.effective-settings.json`: normalized settings actually submitted.
- `result.tif.log`: native diagnostics; retain it when a render fails.

A failed attempt may leave settings/log sidecars. Use a new output name for the
next experiment. Do not overwrite references or source ORFs. Exit 0 means the
command completed; nonzero means a validation, native, resource or comparison
layout failure. `compare` exit 0 means compatible layouts, not equality: inspect
`comparison.exact_decoded_pixels_equal` and `icc_profiles_equal` in its JSON.

For fitting: use shared H/S/L profile values with per-image WB/exposure/tone
nuisance parameters; preserve one fixed baseline-derived geometry/weight mask.
Render candidates through this CLI, compute ICC-aware target-space error, and
remeasure local derivatives after large parameter moves. Native slider nonlinear
responses and gamut clipping make a single global linear approximation unreliable.
Use held-out photographs and regularization before calling a profile reusable.
The CLI performs rendering and comparison; it does not implement the optimizer.

## Validate before claiming equivalence

1. Match ORF bytes, all raw parameters, orientation/crop, depth and output profile.
2. Render in fresh processes; require identical decoded samples on repetition.
3. Perturb each requested control independently; verify readbacks and pixel changes.
4. Compare at least one neutral and one non-neutral profile with Workspace exports.
   Prefer full-resolution TIFF16. Require exact decoded samples when paths allow.
5. Explain and experimentally isolate every discrepancy. A loaded framework,
   zero return code, plausible preview, or small error does not establish equality.
6. Desktop equivalence and hacked-firmware physical-camera equivalence are separate.

If an ABI guard, missing resource, unsupported capability, or version check fails,
retain the failure and inspect the owning installed binary/caller. Do not fall back
to LibRaw/Apple RAW, fake unsupported settings, modify the installed app, inject
into a user's running session, or change a camera to obtain a success status.

## Stock JPEG profile export and camera loading

These commands are separate from desktop RAW development. Native JPEG metadata,
CSV generation and COLOR upload/readback have been validated on the attached
PEN-F. Hardware validation is limited to the documented camera, firmware and
destinations; backup restoration and power-cycle persistence are separate checks.
Do not interpret exact desktop pixels as proof of camera rendering equivalence.

```sh
./omrender profile-jpeg /absolute/input.ORF --settings /absolute/fitted.json \
  --output /absolute/new-profile.jpg
./omrender profile-info /absolute/new-profile.jpg
./omrender camera-profile-plan /absolute/new-profile.jpg \
  --bank current --slot 2 --output /absolute/new-plan.json
```

`profile-jpeg` takes the same RAW overrides, backend, rotate/resize and resource
options as `render`. Output is always an 8-bit JPEG, native quality 100 with
embedded ICC and Olympus MakerNotes; configured 16-bit output is changed to 8 in
the saved effective settings. An explicit `--bits 16` is rejected. Development
still happens in 16 bits. The installed FileSave writer receives the configured
raw procedure; copying the source EXIF alone would carry the wrong recipe.

`stock_pen_f` and `stock_pen_f_mono` are accepted. Requested HSL export is rejected
before creating output artifacts. COLOR S values must be within -5..5; H/L are
neutralized. MONO is validated against its own filter/grain/toning/style metadata.
The exported JPEG is read back through both Olive file metadata and the real
installed `OlyDCFWUpProfileMaker`. Native loader acceptance, unchanged parameters,
all twelve saturation values and explicit tone values are checked. Its extra
`.profile.json` sidecar records the native classification, values and JPEG hash.
The original camera Model is retained; it is not forged to make a file loadable.
The unbundled CLI currently leaves the writer's Software label as `(null) (null)M`;
the native loader does not inspect that field, and recipe readback is verified.

`profile-info JPEG [--build-dir DIR]` is file-only JSON inspection. It reports
source finishing mode, S/H/L metadata including missing-field statuses, tone,
creative shading, contrast/sharpness, and the native camera-loader result.
`stock_profile_transport_eligible` requires native acceptance without adjustment.
It does not report the current camera state. Missing H/L tags in a stock camera
JPEG are distinct from explicit non-neutral H/L tags, which this route rejects.

`camera-profile-plan JPEG --bank BANK --slot N [--output NEW.json]
[--build-dir DIR]` performs offline preflight without constructing a transport.
BANK is `current`, `c1`, `c2`, `c3`, or `c4`; N is 1..3. `current` means the native
updater's Current bank. Source profile number never selects the destination.
The plan separates the transferable S/tone/creative-shading/contrast/sharpness
recipe from WB, development exposure, ICC and noise filtering. Those latter
settings may affect the sample JPEG but are not uploaded by this stock profile
operation. No bank or slot is inferred or defaulted.

`camera-profile-csv JPEG --bank BANK --slot N --target TARGET.json
--output NEW.csv [--build-dir DIR]` calls the installed native serializer offline.
TARGET contains exactly:

```json
{"model":"PEN-F","firmware":"31","serial":"ACTUAL-SERIAL","dial_myset_supported":true}
```

These are caller-supplied identities/capabilities, not a verified connection. Use the SDK identity string: the tested PEN-F firmware 3.1 reports `31`.
A native class method maps the requested bank to MySet types. If the real target
supports dial MySets, C1..C4 include both normal and dial records; Current has one.
Use the real capability rather than guessing. Output includes request/log/report
sidecars; CSV serialization performs no camera operations. A CSV is not a camera
backup and this command does not upload it.

The physical command, **only when the user intends that camera write**, is:

```sh
./omrender camera-profile-load /absolute/profile.jpg \
  --bank current --slot 2 --expected-serial ACTUAL-SERIAL \
  --backup-dir /absolute/new-camera-load-directory
```

Additional options: `--build-dir DIR`, `--timeout 180`, `--max-rss-mb 2048`,
`--family color|mono` (assert inferred JPEG family), `--skip-backup` (explicitly
omit the .set backup). `--output-dir` aliases `--backup-dir`. Slot N selects the
inferred family's COLOR or MONO memory, never the other family.
The backup directory and sibling `.request.json`/`.log` must not exist; its parent
must exist. Quit Workspace first: the command refuses a running Workspace session
and will not attach to or interrupt it. Connect the PEN-F in the native supported
USB mode (the official workflow starts with Storage).

Only this command constructs communication handlers. The native detector scans
storage/PTP, may change USB protocol mode, and must find exactly one supported
camera. USB mode changes can precede identity validation; no profile write occurs
before matching the expected serial and PEN-F model. Native queries establish
selectable banks, requested family loading support, profile count and dial-bank behavior.
Unless --skip-backup is set, a native combined settings backup (`before.set`) covers all selectable banks;
physical restoration/normal-and-dial coverage is not yet validated. Backup failure
prevents upload. The payload CSV is regenerated using the detected camera identity
and native bank/capability values, then the real MySet uploader runs with
`skipColdStart:YES`. No generic firmware-update command is exposed here.

The command retains payload, native result, progress checkpoint and raw post-write
settings bytes under the new backup directory. The raw bytes are not assumed to
be CSV: verification succeeds only if recognized CSV contains every expected
native parameter/value in the matching bank. Exit 0 requires upload success AND
that exact subset readback. For MONO, a read-only pre-upload settings capture is
also required, including with --skip-backup; every field outside the exact payload
must remain unchanged, preserving COLOR recipes and other MONO memories.
Exit 3 means the native upload completed but readback
could not be verified; inspect `uploaded`, the raw bytes and reports before taking
another action. Other failures can also occur after a write began; inspect the
saved progress/native result rather than assuming the camera is unchanged or
retrying automatically. Captured backup files are preserved on failure.

The documented optional HSL firmware does **not** accept a complete HSL recipe via
stock JPEG sharing. Loading a stock JPEG resets destination H/L. Firmware still
reports 3.1, so that version string cannot distinguish stock from the extension.
Full HSL camera-setting transfer remains a separate, unimplemented path. Never
advertise this command as an HSL uploader. The optimizer should call export/load
only for a selected final stock recipe, never during candidate evaluation.
No optimizer code is changed by these commands.

### Build provenance for fitting clients

`omrender inspect [--build-dir DIR]` reports the resolved `build_dir`,
`native_binary`, `native_sha256` and native capabilities. Fitting clients can pass
that build explicitly to `batch` so provenance describes the executable invoked.
This is observation, not a lock or snapshot; a later batch may use an updated build.

## Native PEN-F MONO profiles

Use `settings --profile mono` for genuine Monochrome Profile Control. This is
separate from generic Monotone and from desaturating a COLOR profile. Query the
installed engine for the actual input before fitting:

```sh
./omrender capabilities --input /absolute/PEN-F.ORF --build-dir /absolute/build
./omrender settings --profile mono --output /absolute/mono.json
```

The profile object is explicit:

```json
{"kind":"stock_pen_f_mono","mode":"manual",
 "color_filter":{"color":"red","strength":3},
 "grain":"off","toning":"neutral","shading":0,"contrast":0,"sharpness":0}
```

Filter colors are `off`, `yellow`, `orange`, `red`, `magenta`, `blue`, `cyan`,
`green`, and `yellow-green`. Active strength is 1, 2 or 3. Strength zero or color
off canonicalizes to off/0. Optimize over 25 categorical states: one off and eight
colors times three strengths. MONO 1/2/3 are destination memories, not distinct
rendering engines. Only grain off and neutral toning are currently exposed.
Contrast and sharpness are integers -2..2; creative shading is -5..5, separate
from lens shading compensation. Check the validation report for verified pixel
response and any remaining limitations before optimizing a control.

Keep photo adjustments in `raw_overrides`: `white_balance_mode:4` and
`custom_wb2:[5300,0,0]` select explicit Kelvin/AB/GM; `exposure_bias:[0,3]` is
rational EV. `tone_control:[1,highlight,shadow,midtone]` selects manual values
-7..7 (the fourth midtone item is optional). WB and EV are not changed by MONO
selection and are not part of a reusable camera recipe.

Precedence is ORF shooting parameters, optional OES overlay, explicit raw
adjustments, then explicit MONO style. A Natural/MonochroCreater Off OES cannot
silently disable the explicit MONO profile. MONO rejects raw overrides for
finishing_mode, contrast, sharpness and global_saturation; use the profile fields.
The native raw family is Natural base finishing2 + MonochroCreator manual2;
JPEG/OES family12 is a different enum domain. E-M10 II inputs that do not support
the native creator fail clearly.

`render`, native TIFF8/TIFF16, resize, rotation and `batch` operate as for COLOR.
A manifest can mix COLOR, MONO and HSL jobs; each result records process ID,
actual backend, stage timings, canonical profile, independently verified native
MONO getters, inherited/raw adjustment readbacks, dimensions, depth and ICC.
Use a single `batch` call for GPU context reuse. Resolve settings and renderer
from the caller's current paths; no executable snapshot or content pin is needed.

`profile-jpeg` accepts stock MONO and verifies filter, grain, toning, shading,
contrast, sharpness and explicit H/S/midtone against the installed native file
readers. `profile-info` reports `profile_family` and native transport eligibility.
`camera-profile-plan` and `camera-profile-csv` infer COLOR or MONO from this
verified metadata. The slot is 1..3 of that family. File-only commands do not
connect to or write a camera. See `docs/MONO-VALIDATION.md` for acceptance evidence
and the native OES representation. Reusable OES styles exclude WB/exposure;
full reproduction settings may include them explicitly.


### Verified camera slot behavior

On the attached PEN-F (serial redacted, native firmware string31), Current
COLOR1/2/3 community recipes and Current MONO1 red-strength3 were uploaded and
read back successfully. The MONO test compared 1116 current-bank settings and
required every field outside its native payload to remain unchanged; zero
unrelated differences were found. Other physical banks/slots and power-cycle
persistence remain untested, despite the native offline serializer matrix passing
all five banks times three slots. Do not infer backup restoration from these tests.
The uploader does not set photo WB or EV. Request hardware loading only for the
selected final recipe, never while evaluating optimizer candidates.

### Shading advice for optimizer agents

Set `profile.shading` in the MONO settings JSON; there is no separate `--shading`
flag. The verified integer range is -5..5 and zero is neutral. This is creative
vignetting, separate from lens-shading compensation and global exposure.

Start filter, tone, WB and exposure fitting with `shading:0`. This is the setting
used by the six pixel-exact Workspace neutral/red3/cyan3 TIFF references. Only
optimize nonzero shading when the target intentionally needs a spatial vignette;
a color-only LUT cannot represent a position-dependent effect. Confirm the chosen
style on full-resolution output after fitting with resized candidates.

Nonzero shading now has native parameter readback, a native pixel effect and
fixed-seed deterministic batch/fresh-process behavior. Its native gain dithering
is distinct from the simulated film-grain control, which remains off. Do not
adjust color/tone values merely to compensate for a different native dither
pattern in an unseeded GUI export. Exact GUI pixel parity for nonzero shading
requires matching its RNG history; that state is not exposed in Workspace's UI.
The measured extra comparisons and this limitation remain in the validation
report. The shading value transfers to a camera profile; the host RNG state does
not.

### Deterministic native shading

Olympus creative shading dithers its gain coefficients using process-global
`OLY_RAWART::CRand32`, even with film grain off. Uncontrolled nonzero shading can
therefore produce different pixels for identical jobs in one batch. The wrapper
uses the native startup seed for each nonzero MONO shading pass and restores the
previous native state afterward. It preserves the Olympus dithering algorithm;
it does not remove noise or correct pixels after rendering.

This is an extra host execution control beyond Workspace's UI, required for a
deterministic optimizer. It is not a PEN-F profile value and is not uploaded.
The private native constructor/destructor are resolved from the loaded arm64
Mach-O, with symbol/text/layout checks. The wrapper changes its own random-object
state, then uses the native non-deleting destructor to publish it under the
native mutex. Installed files and loaded library code are unchanged. Native jobs
are serialized; embedding callers must enforce the same rule.

Each nonzero shading result records `mono_creative_shading_stage.rng_control`,
including startup, prior, applied, advanced and restored seeds. Failed restoration
prevents output and stops the batch. On the verified installation the startup seed
is 1. Workspace UI exports may use another RNG history, so comparisons involving
nonzero shading must account for seed state; identical visible profile settings
alone do not identify its dither pattern. See the validation report for exact
GUI comparisons and the separately measured shaded-output difference.


### Persistent-worker memory policy

The launcher defaults its native child to `MallocAggressiveMadvise=1` and
`MallocLargeCache=0`. These macOS allocator settings reduce retention of free
pages in long batches; they do not change Olympus settings or pixel calculations.
Explicit caller environment values override these defaults. Results record the
actual `allocator_environment`. Direct native-binary invocation must supply the
same environment when reproducing the launcher memory behavior. Build replacement
is atomic so an already-running worker can finish on its loaded executable.

Use `--max-rss-mb` and `--timeout` to bound a batch. A resource-limit failure is
not success: inspect which output sidecars completed before retrying with fresh
output paths. Keep optimizer candidate batches bounded; reserve full-resolution
outputs for final checks. Current build support and provenance can be queried with
`inspect` and `capabilities --input`; pass `--build-dir` when the caller has selected
a specific current build. No snapshot or hash-pinning policy is required.

### Re-run the focused native checks

```sh
python3 scripts/test-profile-readback.py
python3 scripts/test-native-rng.py --output-dir /absolute/new-directory-under-Documents
```

The first check uses file-only payload/preservation fixtures. The second compiles
against the current native RNG helper and exercises real native state restoration
through successful scopes, constructor failures and C++/Objective-C unwinding.
Neither command opens a camera session. `scripts/validate-mono.py` prepares and
checks the broader filter/control/batch exercises; run its own `--help` for those
validation-only options.
