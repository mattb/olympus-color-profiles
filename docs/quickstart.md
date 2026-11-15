# First successful render

Complete [installation](install.md), choose a compatible RAW and create a fresh output directory. No USB connection or edited reference is needed.

```sh
RAW="/absolute/path/to/your-photo.ORF"
OUTPUT_DIR="/absolute/path/to/new-render-output"
mkdir -p "$OUTPUT_DIR"
./omrender build
./omrender capabilities --input "$RAW"
./omrender validate examples/settings/color-neutral.json
./omrender render "$RAW" --settings examples/settings/color-neutral.json \
  --output "$OUTPUT_DIR/neutral.tif"
```

Open the TIFF and its sidecar report. Check actual backend, dimensions, output depth/ICC and settings readback. Inputs/settings/reports are distinct files; source RAWs are not edited. Existing outputs are refused. Rotation is explicit; use `--rotate` as documented in the [reference](CLI-HELP.md) if required for your input orientation.

GPU is preferred in auto mode where available. `--backend gpu` requires GPU; `--backend cpu` selects CPU. A development failure is not silently retried with a different backend. Neutral settings inherit unexposed ORF parameters.

Next: [render/batch](users/render.md), [fit a paired look](users/fit-profiles.md), or [offline profile export and transfer](users/transfer-profiles.md).
