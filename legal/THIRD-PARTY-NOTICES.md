# Third-party notices and distribution boundaries

Reviewed 2026-11-15. This is an inventory of identified components and rights, not a complete software bill of materials or a grant of rights by their owners. Versions below come from `optimizer/pyproject.toml` and installed package metadata. Detailed current-host inventories and research records remain in the private development archive. The source links and component terms below are the public summary; they are not a final distribution SBOM. Dependencies are installed separately; vendoring a wheel, executable or bundled release requires its complete notices, including its bundled subcomponents.

## Artistic profiles

The RawTherapee Film Simulation Collection is credited to **Pat David, Pavlov Dmitry, Michael Ezra et al.** Its locally acquired collection README identifies **CC BY-SA 4.0**. The acquired OpenSourceLuts forms were resampled by **NicePhoto**. Project work converted LUT node formats, rendered synthetic photo targets, fitted bounded Olympus wheel/filter/tone settings, and in some cases fitted additional Adobe Develop approximations. These transformations are approximations, not measured film-emulsion fidelity. Previous author credit and modification history must remain attached when assets are redistributed.

Sources: [RawPedia collection and credits](https://rawpedia.pixls.us/film_simulation/), [Pat David's film-emulation article](https://patdavid.net/2015/03/film-emulation-in-rawtherapee/), [pinned OpenSourceLuts tree](https://huggingface.co/Norton0924/OpenSourceLuts/tree/484c3c1fdc612082915e5876cd0450eb8a0d2431), and the [CC BY-SA 4.0 license](licenses/CC-BY-SA-4.0.txt).

The following identified, project-derived artistic assets retain that attribution and CC BY-SA 4.0, to the extent copyright or similar rights apply. No additional restrictions are imposed on rights granted by that license:

| Tracked asset | Underlying reference / acquired identifier |
|---|---|
| `optimizer/recipes/ilford-hp5plus400.json`, `.oes`; `optimizer/recipes/lightroom/hp5.xmp` | Ilford HP5 Plus 400 / `olut_B09_rt` |
| `optimizer/recipes/kodak-trix400.json`, `.oes`; `optimizer/recipes/lightroom/trix.xmp` | Kodak TRI-X 400 2 / `olut_B18_rt` |
| `optimizer/recipes/lightroom/panf.xmp`; `optimizer/recipes/penf-panf-adobe-experimental.xmp` | Ilford Pan F Plus 50 / `olut_B11_rt` |
| `optimizer/recipes/lightroom/penf-hsl-velvia-research.xmp` | Fuji Velvia 50 / `olut_S08_rt` |
| Artistic profile mappings embedded in `optimizer/experiments/kodachrome-equal-budget-results.json` | Kodak Kodachrome 25 / `olut_S15_rt`; Kodak Kodachrome 64 / `olut_S16_rt` |

The independently fitted Kodachrome 25/64 LUT-study profiles documented by `optimizer/experiments/KODACHROME-EQUAL-BUDGET.md` come from `olut_S15_rt` / `olut_S16_rt` in the same collection. Their mappings are already embedded in the tracked results JSON above. If standalone profile files or derivative comparison media are added to a release, retain the same attribution, license and modification notices. They are different from the community camera recipes below. Each source manifest must preserve its specific source identifier, revision and hash. The attribution applies to artistic mappings, not a claim of exclusive rights over measured error numbers or other facts.

For conservative distribution, treat the artistic profile mappings as adaptations under CC BY-SA 4.0. Whether a particular short numerical recipe or fitted mapping is copyrightable is a legal question; this notice does not decide it or purport to relicense independent photographs merely because a look was applied. CC BY-SA does not automatically relicense the independent optimizer code.

## Community COLOR recipes: permission unresolved

| Asset | Identified source | Release treatment |
|---|---|---|
| `optimizer/recipes/lightroom/kodachrome25.xmp`, `kodachrome64.xmp` | Gareth B., [community recipe thread](https://www.mu-43.com/threads/my-kodachrome-classic-chrome-pen-f-settings-update.92950/) | Existing provenance explicitly records no established open-content license. Obtain permission/document rights or omit these files. |
| `optimizer/recipes/lightroom/velvia50.xmp` | VideoPic, [community recipe thread](https://www.dpreview.com/forums/threads/pen-f-owners-i-developed-a-fuji-velvia-50-profile-you-can-try.4375658/) | Same unresolved status; the RawTherapee CC license does not cover this different source. |

Credit is preserved in [the existing profile attribution](../optimizer/recipes/lightroom/ATTRIBUTION.md); credit is not itself a permission grant. Do not fold these files into a blanket code license. Review embedded recipe signatures in evidence such as `optimizer/experiments/camera-six-profiles-confirmed.json` and copies in Git history too: removing three visible XMPs is not an exhaustive provenance audit. A source name or measured factual metric alone is not proof of an infringing copy.

## Runtime and build dependencies

| Component | Reviewed version / role | Identified license and release duty |
|---|---|---|
| NumPy | 2.2.6 | BSD-3-Clause primary code; installed `numpy-2.2.6.dist-info/LICENSE.txt` includes additional notices. Preserve complete applicable notices if distributing it. |
| SciPy | 1.15.3 | BSD-3-Clause primary code; installed `scipy-1.15.3.dist-info/LICENSE.txt` and bundled components have additional notices. |
| Pillow | 11.2.1 | Installed metadata identifies **MIT-CMU**. Preserve `pillow-11.2.1.dist-info/licenses/LICENSE` and any bundled library notices. Do not substitute an older Pillow license label. |
| scikit-image | 0.25.2 | BSD-3-Clause primary code plus file-specific licenses listed in its installed `LICENSE.txt`. |
| opencv-python-headless / OpenCV | 4.11.0.86 | Apache-2.0 main package; preserve both `LICENSE.txt` and **`LICENSE-3RD-PARTY.txt`** if redistributing wheels. That notice must be reviewed for bundled codecs/libraries. |
| LittleCMS2 | External dynamic library resolved by `ctypes.util.find_library` for Adobe color normalization | MIT; [upstream license](https://github.com/mm2/Little-CMS). The repository does not vendor this library; do not assume a fresh macOS installation supplies it. |
| ExifTool | External executable | Same terms as Perl: Artistic or GPL; [upstream distribution license](https://github.com/exiftool/exiftool/blob/master/README). Preserve the selected applicable license/notices if bundling rather than merely documenting installation. |
| Python | Python 3.12 runtime | PSF/Python license; [official license](https://docs.python.org/3/license.html). Separately installed. |
| uv | Dependency/bootstrap tool | MIT or Apache-2.0; [official repository](https://github.com/astral-sh/uv). Separately installed. |
| Hatchling | Declared build backend, not present in the inspected runtime environment | MIT; [official project](https://github.com/pypa/hatch). Build dependency; its absence from the runtime environment is not evidence that packaging works. |
| Apple SDKs/frameworks, compiler and platform tools | Native build/system interfaces | Apple terms apply to installed tools/SDKs. A code license does not authorize copying SDKs into a release. |
| OM Workspace and Adobe DNG Converter | Proprietary external applications | Users install from vendor. No vendor executable, framework, shader, DCP/ICC profile or installer redistribution is authorized by this project. |

No third-party source-file header was identified in the sampled native or optimizer implementation. That is **not** proof of independent authorship. Before publishing code under the selected MIT license, review incorporation from referenced projects such as `fishcu/color_chart` and `androidfanman/caduceus-om3`; research citations alone are not proof of copying. The reviewed `fishcu/color_chart` root showed no license file. If code was copied from a source without a usable license, exclude it, obtain permission or independently replace it. If Apache-2.0 code was incorporated from Caduceus, retain the relevant license, notices and modification history.

Do not copy vendor or upstream source wholesale merely to make an installation self-contained. The exact built distribution, rather than this source-only inventory, needs its own final license/SBOM audit.
