# Updating the minimal Pi image

1. Change `TALOS_VERSION` in Makefile. Review the official release notes and the
   retained sd-boot patch against that exact version. Increment `IMAGE_REVISION`
   when repairing packaging without changing the Talos version; never reuse a
   withdrawn package tag.
2. Keep `SBCOVERLAY_VERSION` pinned. Change it only after reviewing its U-Boot,
   firmware and installer behavior. Keep the overlay compatibility patch:
   U-Boot must map the kernel DTB's NVMe PCI aperture, and the legacy firmware
   D0 filename must be overwritten with the matching stock D0 DTB. Keep the
   `configTxtAppend` overlay option in `profiles/*.json`; D0 boards only boot the
   stock `bcm2712-d-rpi-5-b.dtb`, and the firmware will not pick it by itself.
3. Run `make clean`, then `make checkouts patches test`. The patch must apply
   cleanly and its Linux tests must pass.
4. Run `make overlay installer verify`. These produce local artifacts without
   pushing intermediary images.
5. CI may publish a verified candidate as a prerelease. Verify it on a physical
   Pi before deployment or promotion; a successful build alone is insufficient.

There is no independent kernel version to bump. Makefile reads Talos's exact
`PKGS` pin and uses its stock kernel/DTBs. Do not restore the old vendor-kernel
module list or runtime fallback.

## The remaining Talos patches

`patches/siderolabs/talos/0001-rpi5-loader-conf-fallback.patch` preserves boot
selection on the existing firmware when EFI writes fail with `EINVAL`.
Installation still fails on that error; upgrade and rollback may use
`loader.conf`. Unrelated errors must propagate.

When rebasing, examine all default-entry writers, pre-upgrade UKI cleanup,
probing and rollback. EFI values retain precedence. Tests cover the fallback,
strict installation, error propagation and old/new/old selection sequence.
Normal firmware reboot is required; do not assume NVRAM-less kexec behavior.

Remove the patch only when upstream covers these behaviors and the same
regression checks pass without it. Update COMPARISON.md with the evidence.

`0002-image-overlay-assets.patch` invokes the overlay callback in sd-boot's
image preparation path before moving the EFI source directory. Without it,
the raw image has a UKI but lacks Pi firmware, U-Boot, DTBs and config.txt.
The regression checks successful placement and propagation of callback errors.
The imager must be compiled from these patched sources; overriding only its
initramfs does not fix the host-side image assembly code.

`make verify` checks the actual raw EFI partition using a read-only Linux loop
mount. Do not replace this with installer-container checks or a Zstd magic
check: neither proves the flashable image contains the overlay.

## Release behavior

Pull-request builds never publish registry images. A version-changing merge to
main retains the existing automatic tag/release behavior; tag pushes also
release. Publishing uses the already-verified installer archive, not a rebuild.
`make image-version` prints the package tag derived from `TALOS_VERSION` and
`IMAGE_REVISION`. The Talos source/kernel version is independent of that repair
suffix. A tag build must match that package version exactly.

Tuppr 0.5.4 uses the Talos runtime version as the installer tag. After verifying
a repair revision, the manual `Publish verified runtime alias` workflow can
point that canonical registry tag at the verified digest. It checks both the
revision digest and image version label; it does not recreate a GitHub release.
Talos may reuse an already-pulled image: remove only a stale installer tag from
its containerd store and verify the newly pulled digest before resuming Tuppr.
