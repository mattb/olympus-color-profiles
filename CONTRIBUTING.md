# Contributing

Start with [installation](docs/install.md), [build/tests](docs/developers/build-and-test.md), and [compatibility](docs/compatibility.md). The current release is a candidate under [explicit gates](docs/release-readiness.md), not a claim of universal camera or platform support.

Keep native rendering, launcher contracts, scoring/search and documentation changes reviewable. Add a control through validation, native readback, fitting bounds and output contracts together. Tests must distinguish desktop rendering, physical camera behavior, actual Lightroom application and pixel parity.

Never bundle vendor applications/frameworks/kernels/profiles or personal photographs/backups to make a test pass. Use owned/cleared fixtures or document user-supplied inputs. Preserve third-party notices and disclose incorporated source/provenance. Original contributions use MIT; artistic material has separate terms in [NOTICE](NOTICE.md).

Run applicable tests and describe observed results, versions and untested scope. Export/build the candidate without untracked files before release. Do not publish, change visibility, upload packages, rewrite history, contact vendors or write a physical camera as an incidental contribution step.
