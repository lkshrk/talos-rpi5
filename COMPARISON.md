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
- Only build-name customization needed to preserve existing image publication paths; no Talos feature fork beyond boot selection.

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
