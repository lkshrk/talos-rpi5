# Updating the minimal Pi image

1. Change `TALOS_VERSION` in Makefile. Review the official release notes and the
   retained sd-boot patch against that exact version.
2. Keep `SBCOVERLAY_VERSION` pinned. Change it only after reviewing its U-Boot,
   firmware and installer behavior.
3. Run `make clean`, then `make checkouts patches test`. The patch must apply
   cleanly and its Linux tests must pass.
4. Run `make overlay installer verify`. These produce local artifacts without
   pushing intermediary images.
5. Verify the candidate on a physical Pi before publishing/deploying.

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
Keep the version in the tag aligned with `TALOS_VERSION`.
