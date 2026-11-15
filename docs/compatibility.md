# Compatibility and qualification

This page is the current support summary. Historical reports describe specific experiments and may predate current commands.

| Area | Verified scope | Limits |
|---|---|---|
| Host/runtime | Apple Silicon, OM Workspace 2.5.0.2; current development host macOS 27.2.1 | A genuine fresh-Mac install and older-OS compatibility remain release gates. Intel and arbitrary Workspace updates are not qualified. |
| RAW development | DC11 engine inputs tested from PEN-F and E-M10 II; native TIFF8/TIFF16 CPU/GPU paths | Query capabilities for the actual RAW; do not infer support for every camera Workspace accepts. |
| GPU parity | Eight matched baseline/sector comparisons had exact decoded samples and ICC against Workspace | This is desktop-render evidence for recorded inputs/settings; CPU rounding can differ. |
| Stock COLOR | Twelve saturation sectors ±5, shared tone controls | Reusable style excludes scene WB/exposure. |
| Native MONO | PEN-F creator/filter states, tone and verified controls; deterministic repeats | Distinct from generic desaturation. Fitting normally fixes grain off, neutral toning, shading/sharpness zero. |
| Research HSL | Twelve sectors each H/S/L ±7, native readbacks verified | No physical unofficial-firmware ISP equivalence established. Stock JPEG sharing does not upload full HSL and resets destination H/L. |
| Camera upload | Current-bank COLOR1/2/3 and MONO1/2/3 signatures/readbacks verified in recorded PEN-F studies | Other banks, backup restoration and power-cycle persistence are not established by those readbacks. Serializer tests alone are not physical qualification. |
| Adobe presets | Export/replay and actual Lightroom control import/application verified for recorded presets | HSL color Lightroom/Converter pixel-parity gates failed, including matched process versions; arbitrary cameras/looks/Adobe versions are not qualified. |

These summaries reflect qualification studies completed through 2026-11-15. Detailed study artifacts are retained privately because they contain personal paths, camera identifiers or uncleared content. They are not required public inputs. The [release acceptance ledger](release-readiness.md) records which fresh candidate checks have actually passed.

File-only export/inspection/planning does not access a camera. Only explicit `camera-profile-load` constructs the physical communication/upload path. It requires an identified camera and destination and preserves reports/backups; a failed call can occur after a write begins. Read [transfer instructions](users/transfer-profiles.md).
