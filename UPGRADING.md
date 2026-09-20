# Updating the minimal Pi image

1. Change `TALOS_VERSION` in Makefile. Review the official release notes and the
   retained sd-boot patch against that exact version. Increment `IMAGE_REVISION`
   when repairing packaging without changing the Talos version; never reuse a
   withdrawn package tag.
2. Keep `SBCOVERLAY_VERSION` pinned. Change it only after reviewing its U-Boot,
   firmware and installer behavior. Keep the overlay compatibility patch:
   U-Boot must map the kernel DTB's NVMe PCI aperture, and the legacy firmware
   D0 filename must be overwritten with the matching stock D0 DTB.
3. Run `make clean`, then `make checkouts patches test`. The patch must apply
   cleanly and its Linux tests must pass.
4. Run `make overlay installer verify`. These produce local artifacts without
   pushing intermediary images.
5. CI may publish a verified candidate as a prerelease. Verify it on a physical
   Pi before deployment or promotion; a successful build alone is insufficient.

There is no independent kernel version to bump. Makefile reads Talos's exact
`PKGS` pin and uses its stock kernel/DTBs. Do not restore the old vendor-kernel
module list or runtime fallback.

## The remaining Talos patch

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

## Release behavior

Pull-request builds never publish registry images. A version-changing merge to
main retains the existing automatic tag/release behavior; tag pushes also
release. Publishing uses the already-verified installer archive, not a rebuild.
`make image-version` prints the package tag derived from `TALOS_VERSION` and
`IMAGE_REVISION`. The Talos source/kernel version is independent of that repair
suffix. A tag build must match that package version exactly.
