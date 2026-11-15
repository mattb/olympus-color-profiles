# Build and test

Production native entry point is `src/omrender.mm`; its included MONO/RNG/bootstrap modules are required source, not disposable probes. `optimizer/src/omfit` holds scoring/search/Adobe logic. Root launchers remain stable. Research/probe relocation must update include paths and scripts atomically and preserve source attribution.

```sh
./omrender build
python3 -m unittest discover -s tests -v
uv run --locked --project optimizer python -m unittest discover -s optimizer/tests -v
python3 scripts/test-profile-readback.py
```

Native compilation needs Apple Silicon, an Apple compiler/SDK, Foundation/AppKit and the installed vendor runtime for integration. Python fitting pins 3.12 and its dependencies in `optimizer/uv.lock`. ExifTool is external; Adobe additionally needs a system LittleCMS2 library and Converter. Read [installation](../install.md) and [dependency licenses](../../legal/THIRD-PARTY-NOTICES.md).

Vendor-independent numerical/contract checks must not need private photographs, a connected camera or copied vendor software. Native mocks/readback tests and installed-engine integration have separate requirements. Never run a physical camera write as an automatic test.

When adding a control, update schema/range validation, capability declaration, native setter/readback assertion, fitting bounds/export representation, meaningful regression checks and current compatibility documentation. Preserve frozen held-out selection, actual-render acceptance, ICC-managed comparisons and separate style/photo adjustments.

Validate the exact candidate using `git archive` in a path containing spaces, a fresh Python environment/cache and wheel installation outside the checkout. Required untracked includes invalidate a release claim. Record actual deployment target, versions, checks/skips and limitations; source build success is not fresh-Mac qualification.
