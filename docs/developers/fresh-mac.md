# Fresh-Mac acceptance

This checklist remains an explicit release gate until completed on a genuinely fresh supported Apple Silicon Mac. Current-host exports and fresh virtual environments establish narrower facts. A fresh home/account does not remove installed native libraries; a VM does not establish GPU support unless that path actually works.

1. Export the exact candidate commit with no untracked files, generated binaries or author caches. Record commit, hardware/OS and official app/engine versions.
2. Start without the project's prerequisites. Follow only [installation](../install.md); verify missing compiler/Workspace/renderer/ExifTool/LCMS/Converter diagnostics before installing each required component through official flows.
3. Build from a path containing spaces, test default/overridden build locations, and inspect architecture/deployment target. Test the optimizer wheel outside the checkout with and without a companion renderer.
4. Run [baseline tests](build-and-test.md), portable-example validation and no-overwrite/invalid-input checks without USB.
5. With owned or cleared RAWs, render stock/MONO/nonneutral HSL, verify native controls/backend/dimensions/ICC, deterministic repeats and bounded persistent batches; test CPU separately.
6. Run one small paired fit with fixed training/validation roles; inspect separate style/photo outputs and managed full-resolution comparisons.
7. Qualify optional Adobe fitting/replay separately. Actual Lightroom export is a distinct test; retain known failed parity gates.
8. Export/inspect/plan a stock profile offline. Any real camera upload is a separate explicitly authorized qualification, never a default smoke test.
9. Record commands, exit statuses, dependency versions and skipped/unverified features in the release ledger. Do not mark “fresh Mac verified” while these steps remain incomplete.
