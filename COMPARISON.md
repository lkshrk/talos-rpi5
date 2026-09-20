# Talos 1.14.1 comparison and reduction

Baseline: custom release v1.13.9 (`f6c12ac`), compared with Talos v1.14.1 (`2f86b9d2a29b413deddd7122a8420b8913813615`). Talos pins pkgs `v1.14.0-25-gf694e1b`, whose kernel is 6.18.51.

## Withdrawn image and boot repair

The initial `v1.14.1` package was withdrawn after k8s-99 failed to return from
its upgrade reboot. Installation completed successfully; no post-boot console
log was available, so the exact executed failure path remains unconfirmed.
Published-artifact and source inspection found two compatibility defects:

- The unchanged U-Boot only mapped NVMe MMIO at `0x1b80000000` for 2GiB. The
  stock DTBs place the non-prefetchable PCI window at `0x1b00000000`. The repair
  maps the whole 4GiB aperture, preserving coverage of the old layout.
- The firmware-facing `bcm2712d0-rpi-5-b.dtb` filename was missing from the new
  package. Copy-only upgrades could leave its old vendor tree on the ESP even
  though mainline calls the replacement `bcm2712-d-rpi-5-b.dtb`. The repair
  packages identical stock D0 bytes at both names, overwriting stale copies.

Regression checks inspect the real compiled MMU table and both packaged DTBs,
plus byte equality of the D0 aliases. These replace the previous insufficient
file-presence-only boot checks. Hardware recovery/boot verification is still a
separate gate; the repair is published under a new package tag.

## D0 device-tree selection repair (revision 3)

Revision 2 also failed to return after a Pi 5 Rev 1.1 (BCM2712 D0) upgrade.
Recovered NVMe logs contain no 6.18.51 boot from that attempt, so the kernel did
not reach machined. No console or serial capture exists from this Pi, so the
failure path below is the suspected mechanism, not observed evidence. It was
captured on identical Rev 1.1 hardware with the official mainline-DTB overlay in
siderolabs/talos#12748: the firmware loads `bcm2712-rpi-5-b.dtb` and applies
`overlays/bcm2712d0.dtbo`; the vendor overlay needs labels such as `spi10` that
the mainline tree lacks, so the overlay is skipped, the kernel runs a C0 layout
on D0 silicon and panics early with an asynchronous SError in
`brcmstb_pinconf_set`. The legacy `bcm2712d0-rpi-5-b.dtb` alias from revision 1
was present during this Pi's failed boot and did not change the outcome.

Mainline expects D0 boards to boot `bcm2712-d-rpi-5-b.dtb`. Revision 3 passes
`configTxtAppend: device_tree=bcm2712-d-rpi-5-b.dtb` as an overlay option in both
imager profiles, so installs, upgrades and the raw image write it to config.txt.
That tree carries `__symbols__` and `clk_rp1_xosc`, which the stock kernel's RP1
runtime overlay needs for Ethernet; a diagnostic boot on the vendor D0 tree
reached userspace but failed exactly there. The selection is board-specific:
C0/C1 boards need the base tree and must not use this revision. Verification
checks the installer's `overlay/extra-options` and the raw image's config.txt.

## Raw-image packaging repair (revision 2)

Inspection of the generated raw EFI partition found only the EFI loader, UKI
and loader.conf: the Pi overlay was absent. Talos 1.14.1's sd-boot image path
copies those assets, then relocates the EFI directory without invoking
`ExtraInstallStep`. Its normal installer and GRUB image paths invoke that
callback. This is independent of the corrected installer overlay in revision 1.

The bounded repair adds the callback before relocation and propagates errors.
A regression test requires a callback-created file in the final EFI source
directory and rejects a failed callback. Build the imager from patched source,
load it locally, and use it for both outputs. Verify the raw artifact itself
with a read-only Linux loop mount and the existing U-Boot/DTB checker, plus
config.txt and EFI boot files. Published as `v1.14.1-rpi5.2`.
Hardware boot remains a separate gate. No existing disks are modified by the
verification command; it attaches only the decompressed build artifact.

## September 20 hardware findings

Revision 2 was installed using the verified image digest
`sha256:8174084b26f275abd718cc98c51cc7fe1d35e2b5622c839ee75122535ea93f06`.
It still failed to return after reboot. A successful image build, corrected
MMU window, and complete EFI partition did not establish hardware bootability.
The executed cause of this full-image failure remains unconfirmed.

A later diagnostic boot preserved the working 1.13.9 firmware/device trees and
loaded the 1.14.1 kernel/initrd. Disabling the UKI splash exposed Talos userspace
at approximately 290 seconds uptime: DNS requests to `10.254.0.1:53` failed
with `network is unreachable`, time synchronization failed, and service startup
waited for apid, cri, etcd, and trustd. No kernel panic was visible. The photo
does not show a runtime version. Both original 1.13.9-only arguments were restored
for that trial (`init_on_alloc=1`, `nvme_core.io_timeout=4294967295`), along with
diagnostic options; this was not an isolated test of those two arguments.

The mixed boot assets have a concrete RP1 binding mismatch:

- The actual old D0 DTB (`a23feddcc24667d9168eff8485f7181a75f86970a3b7f6ac472d2a2f4e86bbd9`)
  enables Ethernet beneath a legacy `rp1` simple bus.
- Linux 6.18.51's RP1 PCI driver searches for `rp1_nexus`. Without it, its dynamic
  mainline overlay uses a different bus/interrupt topology, with Ethernet disabled
  unless the board tree enables it. The legacy node cannot supply those overrides.
- The repaired full image's D0 DTB (`ff59a8084cf00a677e6483a4461bb9de2ae0200c01948b78486716c38c5d026e`)
  already has `rp1_nexus` and enabled Ethernet. Therefore the mixed-tree failure
  cannot establish the cause of the earlier full-image failure.

Persistent logs subsequently confirmed the executed mixed-tree failure. The
EPHEMERAL filesystem was inspected read-only; its dirty XFS journal was replayed
only into a USB-backed device-mapper snapshot, with the original partition
write-protected and its write counters verified unchanged. The recovered archive
SHA256 is `7781e9e87cf2006f3f9d248a8e0c113d814c3e5663b5db9b6f6e9248c5c12eea`.
In `kernel.log.1`, lines 32991–32992 and 42943–42944 report:

```text
OF: resolver: node label 'clk_rp1_xosc' not found in live devicetree symbols table
rp1_pci 0002:01:00.0: probe with driver rp1_pci failed with error -22
```

The driver returns before populating RP1 child devices. In the corresponding
controller startup, only loopback is brought up, desired link aliases are empty,
and VLAN `net0.69` is absent. META, STATE, and EPHEMERAL mounts succeed. This is
an RP1 device-tree initialization failure, not a DNS-server or NVMe-mount fault.
Adding just a missing clock-symbol alias is insufficient: the legacy bus and
interrupt topology also differs, and the dynamic overlay leaves Ethernet disabled.
These instrumented records confirm the mixed-tree failure; they do not establish
the cause of the earlier complete repaired-image attempt. Log rotation, multiple
boots, and unsynchronized 1970 timestamps require explicit segment attribution.

Talos's permanent-MAC selector logic is unchanged between these versions;
1.14 improves alias-change notification. The pinned U-Boot already supplies the
Ethernet MAC through DT aliases. A missing/different runtime permanent MAC remains
possible, but was not observed; do not broaden the selector speculatively.

Upstream overlay 0.2.2 includes vendor-derived DTs adapted to mainline RP1/PHY
bindings. It is not a proven drop-in replacement for this NVMe boot chain:
the full Pi 5 U-Boot/NVMe integration in upstream PR 88 is still open at this
inspection. No whole-overlay replacement was retained or published.

Boot counting was also tested using the known-working 1.13.9 payload. The test
entry booted, but its `+1.conf` filename remained unchanged, so automatic fallback
cannot be trusted here. The original boot files and selection were restored.
`panic=0` is not evidence of a kernel panic: Talos userspace also honors it after
fatal startup failures. Further RCA needs boot/interface evidence from the
matching full image, rather than another mixed-kernel/device-tree experiment.

Evidence sources:

- [Exact RP1 PCI driver](https://github.com/gregkh/linux/blob/v6.18.51/drivers/misc/rp1/rp1_pci.c).
- [Mainline RP1 peripheral defaults](https://github.com/gregkh/linux/blob/v6.18.51/arch/arm64/boot/dts/broadcom/rp1-common.dtsi).
- [Talos host DNS cache](https://github.com/siderolabs/talos/blob/v1.14.1/internal/pkg/dns/cache.go).
- [Talos userspace panic handling](https://github.com/siderolabs/talos/blob/v1.13.9/internal/app/machined/main.go).
- [Upstream RP1/PHY adaptations](https://github.com/siderolabs/sbc-raspberrypi/tree/v0.2.2/artifacts/dtb/raspberrypi/patches).
- [Unmerged Pi 5 U-Boot/NVMe integration](https://github.com/siderolabs/sbc-raspberrypi/pull/88).

## Preserve before changing the pipeline

- Existing public installer repository and raw-image release artifact.
- Pinned Pi 5 U-Boot/NVMe overlay, with its MMU layout adapted to stock DTBs.
- NVRAM-less upgrade boot selection. Add regression tests for the new upstream pre-cleanup selection and rollback paths before rebasing the fix.
- Existing extension selection remains configurable; do not silently remove runtime support in the same refactor.

## Remove after verification

- Vendor `raspberrypi/linux stable_20250916` kernel source/config replacement and kernel compilation.
- The replacement module allowlist tied to that old kernel.
- The old pre-6.15 `open_tree` compatibility change; 1.14 has a different runtime implementation and the stock kernel supports the required operation.
- Overlay dependency on custom-prefixed kernel images. Its DTBs must come from the exact stock kernel package used by Talos.

## Keep and narrow

- Firmware/U-Boot overlay for the existing NVMe boot chain. The generic upstream Pi 5 U-Boot integration remains unmerged.
- Focused sd-boot `EINVAL` fallback to loader.conf, preserving EFI precedence and errors unrelated to unavailable firmware variables.
- Only build-name customization needed to preserve existing image publication paths; Talos patches are limited to boot selection and raw-image overlay installation.

## Validation gates

1. Run focused boot-selection regression tests on Linux, including failure cases and rollback/probe behavior.
2. Apply the reduced patches cleanly to pinned upstream sources; validate build commands and workflow syntax.
3. Build overlay, patched Talos userland/installer, and raw image using the official kernel.
4. Inspect artifact architecture/version and boot assets. Hardware boot, NVMe, Ethernet stability, cooling and upgrade/rollback still require a separate physical Pi test before deployment.

## Hardware boundary

Stock 6.18.51's plain `bcm2712-rpi-5-b.dtb` embeds RP1, enables Ethernet and both PCIe ports; retain that filename. The `-ovl-rp1` variant instead expects a runtime overlay and must not replace it.

This reduction targets k8s-99's Pi 5 NVMe/Ethernet use. Stock-kernel peripheral parity is not established. The running node exposes voltage, CPU thermal and NVMe hwmon devices, but no fan hwmon device; that does not prove the physical absence of a fan. Active-cooler/PoE/Wi-Fi/CM5 claims from old releases must not be carried forward without validation.

## Sources

- [Talos 1.14.1 source and package pin](https://github.com/siderolabs/talos/tree/v1.14.1).
- [Matching stock ARM64 kernel configuration](https://github.com/siderolabs/pkgs/blob/f694e1b/kernel/build/config-arm64).
- [Linux 6.18.51 Pi 5 device tree](https://github.com/gregkh/linux/blob/v6.18.51/arch/arm64/boot/dts/broadcom/bcm2712-rpi-5-b.dts).
- [Upstream Pi 5 U-Boot integration](https://github.com/siderolabs/sbc-raspberrypi/pull/88), still open at comparison time.
- [Upstream MACB fixes](https://github.com/siderolabs/pkgs/pull/1526) and [Talos 1.14 release notes](https://github.com/siderolabs/talos/releases/tag/v1.14.0).
