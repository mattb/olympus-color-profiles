# Source-candidate validation

Validated 2026-11-15 on the existing Apple Silicon development Mac, against a committed, allowlisted source export in a directory containing spaces. This is **not** a genuine fresh-Mac installation result or public-release clearance.

- Source baseline: `94e1c54` with candidate-policy/packaged-notice refinements in `22380ce`; subsequent upstream-precedent documentation does not change rendering code.
- Native build from exported sources: passed, with no developer native binary or untracked include fallback. Explicit default deployment target: macOS 27.2; older systems are not qualified.
- Exported-tree root contracts: **13 passed**.
- Fresh exported-tree optimizer environment: **105 tests run: 104 passed and one optional external-LUT test skipped**. This uses a preinstalled Python interpreter and system prerequisites, not fresh-machine provisioning.
- File-only profile preservation: **seven checks passed**, no hardware operations.
- Installed wheel: build/install/help, packaged natural settings and MIT LICENSE/NOTICE verified. Missing renderer is actionable; Adobe help remains available when LittleCMS discovery is absent.

## Actual RAW rendering

One owned PEN-F RAW was developed in a nine-job persistent native batch: stock COLOR, nonneutral HSL and red-filter MONO, each with two GPU runs and one CPU run. Outputs were 800×600 RGB8 with embedded ICC profiles. All nine jobs completed in one native process, reporting their requested actual backends. The batch took 39.283 seconds and peaked at approximately 1.86 GB RSS on this host.

| Mode | GPU repeat pixels and ICC | CPU/GPU mean absolute channel difference, 8-bit units | Maximum difference |
|---|---|---:|---:|
| Stock COLOR | Exact | 0.0001083 | 1 |
| Nonneutral HSL | Exact | 0.0001118 | 1 |
| Native MONO | Exact | 0.0008444 | 1 |

CPU/GPU outputs are extremely close in this test but **not pixel-identical**. This is a bounded release smoke test, not a new full-resolution Workspace parity study, fitting-quality benchmark, physical firmware qualification or camera-upload test. Source RAWs, generated media, full native reports and local paths stay outside the candidate.

## Outstanding qualification

A genuinely fresh Mac, oldest-supported-OS coverage, optional actual Lightroom output and any physical USB test remain separate gates. Existing HSL Lightroom pixel-parity failures remain documented in [compatibility](../compatibility.md). Follow [release readiness](../release-readiness.md) and [legal release blockers](../../legal/RELEASE-BLOCKERS.md); an audited source candidate is not permission to publish.
