# Upstream licensing and distribution precedents

Reviewed 2026-11-15. These are observed upstream practices, not vendor permission or a legal opinion about this project.

## Maintainer provenance statement

On 2026-11-15 the maintainer confirmed that no implementation in this project was copied from external projects. Record this as a firsthand maintainer attestation, rather than claiming an independently certified clean-room process. Research citations do not imply copied implementation. Contributor ownership and the distinct rights in artistic mappings, vendor material and future contributions still need their own records.

## PEN-F HSL firmware project

The inspected source snapshot is [`fishcu/oly_fw_analysis` commit d565cb664d3bc37f883f844a3a0c9620efe018e4](https://github.com/fishcu/oly_fw_analysis/tree/d565cb664d3bc37f883f844a3a0c9620efe018e4), committed 2026-11-14. Its approach is more precise than a generic risk disclaimer:

- [RIGHTS-AND-PROVENANCE.md](https://github.com/fishcu/oly_fw_analysis/blob/d565cb664d3bc37f883f844a3a0c9620efe018e4/RIGHTS-AND-PROVENANCE.md) applies Apache-2.0 to contributor-held original work, separately identifies GPL simulator integration and font artwork, and excludes vendor-derived fragments and firmware from that grant. It identifies short displaced stock instructions and small byte edits rather than representing all patch source as independently owned expression. It states that source hashes do not establish redistribution permission.
- [REPRODUCING.md](https://github.com/fishcu/oly_fw_analysis/blob/d565cb664d3bc37f883f844a3a0c9620efe018e4/REPRODUCING.md) starts with input-free synthetic checks. Native analysis requires separately supplied stock firmware; generated listings, dumps, decoded firmware and private data stay local. Ignore rules are explicitly not a rights/privacy clearance.
- The [PEN-F HSL build guide](https://github.com/fishcu/oly_fw_analysis/blob/d565cb664d3bc37f883f844a3a0c9620efe018e4/patches/hsl/pen-f/README.md) takes exact stock firmware plus GNU binutils, without requiring Workspace. The builder produces install/restore files locally, verifies byte ranges and output hashes, and does not flash a camera. Those are reproducibility and operational controls, not evidence of vendor authorization.
- The [contribution policy](https://github.com/fishcu/oly_fw_analysis/blob/d565cb664d3bc37f883f844a3a0c9620efe018e4/CONTRIBUTING.md) asks for source/findings without vendor binaries or private photos/settings, requires attribution and submission rights, and separates hardware evidence from emulator checks.

**Important limit:** this is not a patch-only distribution precedent. The [17 October HSL release](https://github.com/fishcu/oly_fw_analysis/releases/tag/alpha-20261017) advertises a ZIP containing patched and stock-restore firmware BINs. Its rights notice expressly excludes these vendor-firmware release contents from Apache licensing. Do not infer a vendor redistribution grant from the existence of those downloads, or copy that release packaging policy into this project.

The reviewed rights notice, README, build/reproduction documents and keyword-screened issue/PR bodies did not provide an Olympus waiver, an EULA-specific interoperability opinion, or a claim that Apache licensing overrides vendor terms. This is a bounded inspection, not proof that no private permission or discussion exists.

### Practices worth adopting here

Keep independently authored tools and research facts distinct from vendor expression; identify component-specific licenses; require users to obtain proprietary prerequisites themselves; keep generated proprietary/private artifacts out of public source; provide vendor-input-free tests; and report exact hardware/desktop/emulator qualification scope. This project already adopts that source-candidate boundary. Its Workspace private-interface and historical instrumentation questions remain separately marked in [release blockers](../../legal/RELEASE-BLOCKERS.md). Firmware-specific safeguards do not establish that a desktop application's agreement permits the same methods.

## LRTimelapse and Adobe DNG Converter

The official [installation guide](https://lrtimelapse.com/install/) requires DNG Converter and directs users to Adobe downloads for both platforms. More directly, [LRTimelapse's EULA section 9](https://lrtimelapse.com/eula/) lists Converter among external tools called externally and says those tools retain their individual agreements. This is documented architectural precedent for invoking a separately installed executable, rather than distributing it as project code.

The maintainer accepts retaining that same local integration model here. Converter remains optional and user-installed; no Converter application, Adobe camera profiles or installer is bundled. The reviewed pages do not supply a special Adobe authorization transferable to this project. They support the external-tool design and do not establish additional rights to bundle Adobe components, modify the application, or operate an unrelated hosted service. Those are different proposed activities, not prerequisites being imposed on ordinary local use.
