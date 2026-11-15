# Installation

## Supported starting point

Use an Apple Silicon Mac and install OM Workspace **2.5.0.2** from the [official vendor download](https://download.omsystem.com/pages/owdownload/en/), under its applicable terms. The current implementation expects `/Applications/OM Workspace.app`. Other versions, locations and Intel/Rosetta execution are not qualified. Check [compatibility](compatibility.md) and [release status](release-readiness.md) before relying on a feature.

Install Apple's Xcode Command Line Tools with `xcode-select --install`, or use an installed Xcode SDK. A command-line Python 3 is required for the renderer launcher. A compiler/SDK alone does not install Workspace's proprietary runtime. No app files should be copied into this repository.

For fitting, install [uv](https://docs.astral.sh/uv/getting-started/installation/), Python 3.12 and ExifTool. For example, with an independently installed [Homebrew](https://brew.sh/):

```sh
brew install python@3.12 uv exiftool
uv python install 3.12
uv sync --locked --project optimizer --python 3.12
```

The locked Python dependencies are NumPy, SciPy, Pillow, scikit-image, OpenCV-headless and their transitives. See [dependency and build notes](developers/build-and-test.md) and [licenses](../legal/THIRD-PARTY-NOTICES.md).

## Build from the checkout

```sh
python3 scripts/doctor.py
./omrender build
./omrender inspect
./omrender capabilities
./omfit --help
```

The build default deployment target is macOS 27.2, matching the tested host generation. `MACOSX_DEPLOYMENT_TARGET` can override compilation, but an older target is not evidence of older-system qualification.

Builds go to ignored `.build/native` and replace only the project's own binaries atomically. `--build-dir "/absolute/alternate build"` overrides the location; use it consistently when invoking that build. The installed app remains a dynamic runtime dependency. Do not bundle its frameworks/helpers/resources with a release.

Run the [quickstart](quickstart.md) with an owned or rights-cleared RAW. A fresh user home or source export on an already provisioned Mac is not proof of fresh-Mac installation; the [acceptance checklist](developers/fresh-mac.md) remains explicit.

## Installing the optimizer wheel

A Python wheel does not contain the native renderer. Install/build the companion `omrender` checkout and put its directory on PATH, or supply `--renderer "/absolute/path/to/omrender"`. Invoke the installed optimizer outside the source tree to verify discovery. A source checkout can use `./omfit`, which provisions its locked environment through uv.

## Optional Adobe support

Install [Adobe DNG Converter](https://helpx.adobe.com/camera-raw/desktop/dng-and-file-formats/adobe-dng-converter.html) separately from Adobe. Adobe fitting needs ExifTool and a discoverable LittleCMS2 shared library in addition to Pillow:

```sh
brew install exiftool little-cms2
./omfit adobe --help
```

The standard Converter location is `/Applications/Adobe DNG Converter.app/Contents/MacOS/Adobe DNG Converter`; `--converter` overrides it. Lightroom Classic is optional for importing presets or performing actual Lightroom qualification, not required for Converter fitting. SDK/DNG format licenses are not permission to redistribute the Converter application.
