# Experimental Adobe/Lightroom presets

Install the optional dependencies in [installation](../install.md). `./omfit adobe --help` describes color/mono fitting through the installed Adobe DNG Converter. Inputs are matched RAW/reference pairs; outputs include an importable XMP preset and separate per-photo settings.

Converter generates developed previews; it is not a Lightroom automation API. Preset import/application and pixel parity are separate qualifications. The recorded HSL color study passed all 47 requested persistent-control readbacks but failed its original full-resolution Lightroom/Converter gates, including after matching process versions (mean ΔE00 approximately 1.88/1.96). The [compatibility summary](../compatibility.md) preserves the failed qualification; detailed private study artifacts are not public fixtures.

Reusable presets exclude scene WB/exposure but can reset detail, noise, lens and other fixed controls listed in their XMP. Inspect those controls before applying to existing edits. Import through Lightroom's Import Develop Profiles and Presets command; this does not send anything to a camera. Adobe software/profile rights remain separate from the project's MIT license.
