# Fit a paired look

Supply RAWs and ICC-tagged edited references of the same photos. Copy `examples/datasets/held-out.json` to your dataset directory and replace the relative input paths. No sample RAWs or targets are bundled. Keep independent validation photographs out of training; different frames in one burst are not independent scenes.

```sh
./omfit /absolute/dataset/held-out.json --mode stock \
  --output /absolute/new-stock-fit --cache /absolute/render-cache
```

Choose `stock`, `mono`, or `hsl` explicitly. Stock exposes S±5; HSL exposes H/S/L±7 and is a research desktop model requiring unofficial firmware for in-camera controls. MONO uses the native PEN-F filter/tone family. A real input capability check is required; not all RAWs support every mode.

Training photo WB/exposure can be fitted independently; held-out scene settings remain declared and frozen. The optimizer fits a bounded rendered Lab objective and reports ΔE00 separately. It does not translate Lightroom sliders directly or use agent judgement inside the deterministic search.

Inspect `result.json` and ICC-tagged `comparisons/`. `profiles/*.json` and `.oes` are reusable styles without WB/exposure; `adjustments/` contains photo-only controls; `settings/` combines them for exact replay. OES is a Workspace preset, not a camera backup or USB upload. Full-resolution held-out validation and its scope should remain visible.

The renderer follows PATH or `--renderer`; provenance/cache names do not lock out renderer updates. Persistent batches reuse GPU context per batch, not across the entire adaptive search. Read the [optimizer technical guide](../../optimizer/README.md) for budgets, numerical policy, registration and experiments.
