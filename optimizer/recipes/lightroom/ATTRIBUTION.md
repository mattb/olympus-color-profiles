# Profile attribution and provenance

These Lightroom Develop presets are measured Adobe approximations of our finalized PEN-F camera recipes. They were fitted to actual Olympus native renders of the same source ORFs. They do not claim physical film-emulsion fidelity or exact equality with a camera JPEG. Fixed WB/exposure are scene adjustments and are excluded from the reusable presets.

## COLOR recipes

The last recorded Current-bank camera upload/readback establishes this ordering:

| Slot | Recipe | Community author | Original source |
|---|---|---|---|
| COLOR1 | Kodachrome 25 | Gareth B. | [My Kodachrome / Classic Chrome PEN-F settings](https://www.mu-43.com/threads/my-kodachrome-classic-chrome-pen-f-settings-update.92950/) |
| COLOR2 | Kodachrome 64 | Gareth B. | [My Kodachrome / Classic Chrome PEN-F settings](https://www.mu-43.com/threads/my-kodachrome-classic-chrome-pen-f-settings-update.92950/) |
| COLOR3 | Velvia 50 | VideoPic | [PEN-F owners: Fuji Velvia 50 profile](https://www.dpreview.com/forums/threads/pen-f-owners-i-developed-a-fuji-velvia-50-profile-you-can-try.4375658/) |

Local provenance retains the downloaded creator records, native-reader-verified recipes and successful camera transfer readbacks. The exact profile controls also agree with the later readback captured during the Pan F MONO1 upload; the later globally selected COLOR slot was3. See `camera-color-slot-provenance.json`.

The author companion WB offsets were not part of the camera profile upload and are not added to these presets. We have not established an explicit open-content license for the color community recipes; creator credit and source links are retained without granting rights on their behalf.

## MONO film references

The underlying film-inspired LUTs come from the **RawTherapee Film Simulation Collection** by **Pat David, Pavlov Dmitry, Michael Ezra et al.**, licensed **[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)**, resampled by **NicePhoto**. The resampling preserves the pointwise artistic color/tone mapping, without spatial grain. Our bounded native PEN-F fits and subsequent Adobe fits are additional approximations. The derived MONO preset styles retain this attribution and CC BY-SA4.0 license.

Community documentation: [Pat David’s film emulation article](https://patdavid.net/2015/03/film-emulation-in-rawtherapee/), [RawPedia film simulation](https://rawpedia.pixls.us/film_simulation/), and [PIXLS community discussion](https://discuss.pixls.us/t/film-simulation/18927). These establish community use and provenance, not measured fidelity to a physical emulsion.

All three acquired LUTs are pinned to OpenSourceLuts revision `484c3c1fdc612082915e5876cd0450eb8a0d2431`.

### Ilford Pan F Plus 50 — MONO1

- Original Hald file: `Black-and-White/Ilford/Ilford Pan F Plus 50.png`.
- [Pinned LUT source](https://huggingface.co/Norton0924/OpenSourceLuts/resolve/484c3c1fdc612082915e5876cd0450eb8a0d2431/luts/bw/olut_B11_rt.lut16).
- Converted cube SHA256: `22714fc06ce19878deaeb2cda673b665bac07c97169427f6318fd9c27a1351fe`.
### Kodak Tri-X 400 — MONO2

- Original Hald file: `Black-and-White/Kodak/Kodak TRI-X 400 2.png`.
- [Pinned LUT source](https://huggingface.co/Norton0924/OpenSourceLuts/resolve/484c3c1fdc612082915e5876cd0450eb8a0d2431/luts/bw/olut_B18_rt.lut16).
- Converted cube SHA256: `833181f87b271678de8fa7818ec1f8f95f126cabb3eabbb2ce74dc2a89cdeed7`.
### Ilford HP5 Plus 400 — MONO3

- Original Hald file: `Black-and-White/Ilford/Ilford HP5 Plus 400.png`.
- [Pinned LUT source](https://huggingface.co/Norton0924/OpenSourceLuts/resolve/484c3c1fdc612082915e5876cd0450eb8a0d2431/luts/bw/olut_B09_rt.lut16).
- Converted cube SHA256: `00030dce2d817bbb8355ef9517002d50ad63d7e7593bb7c217f025644bd342df`.

Pan F Plus50 was fitted to green filter2, contrast+1, highlight+3/shadow−1; Tri-X400 to yellow filter2, contrast+1, highlight+4/shadow0; HP5Plus400 to blue filter1, contrast+1, highlight+6/shadow−1. All use midtone0, shading0, sharpness0, grainoff and neutraltoning. These native recipes, rather than the original unrestricted LUT transforms, define the Lightroom fitting targets.

On 2026-11-14, Current MONO2 Tri-X and MONO3 HP5 were uploaded through the native camera-profile loader and read back exactly. MONO1 Pan F was restored to its developed +3/−1 tone after the live camera readback showed 0/0. Final Current-bank readback matches all six stored recipe signatures. Each upload created a full native settings backup and verified every field outside its exact payload unchanged. Evidence: `camera-upload-20261114/six-profiles-confirmed.json`. USB readback does not establish power-cycle persistence. The Lightroom preset export files themselves perform no camera operation.

Kodak, Kodachrome, Tri-X, Fujifilm, Velvia and Ilford names identify the artistic references; no endorsement is implied.

## Separate HSL research preset

`penf-hsl-velvia-research.xmp` is an additional research-qualified Adobe approximation of our native desktop HSL recipe. It is separate from the six stock COLOR/MONO presets above and was not uploaded to a camera. Its actual Lightroom import/control readbacks pass, while actual TIFF export comparisons fail the fixed practical Lightroom/Converter parity gate, including the ProcessVersion11 diagnostic. See [qualification](../../../docs/compatibility.md).

The originating artistic reference is `Color/Fuji/Fuji Velvia 50.png`, acquired as `olut_S08_rt` from the RawTherapee Film Simulation Collection by Pat David, Pavlov Dmitry, Michael Ezra et al.; resampled by NicePhoto, licensed [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). This derived research style retains that attribution and license. [Pinned LUT source](https://huggingface.co/Norton0924/OpenSourceLuts/resolve/484c3c1fdc612082915e5876cd0450eb8a0d2431/luts/slide/olut_S08_rt.lut16). Converted cube SHA256: `f77f36e2ed78801f28afcdb381ae963153a2b5de1c98b2a68356d4697ad7118c`. The Lightroom fitting targets were actual finalized native HSL recipe renders, rather than the unrestricted LUT transform. No measured physical-film fidelity or physical patched-firmware equivalence is established.
