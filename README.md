# Raspberry Pi 5 Talos Builder

Build Talos 1.14.1 with the upstream kernel, a corrected Pi U-Boot/NVMe overlay,
and a narrow loader.conf fallback when firmware rejects EFI variable writes.
The original `v1.14.1` package was withdrawn after a failed Pi upgrade. The
current `v1.14.1` build carries the revision 3 D0 fix; repair revisions
(`v1.14.1-rpi5.<N>`) stay published and are never overwritten.
Revisions 1 and 2 hang at the Talos splash on a D0-stepping board (Pi 5 Rev 1.1)
and leave no kernel log. The suspected mechanism, captured on identical hardware
in siderolabs/talos#12748 but not on this Pi: the firmware loads the mainline
`bcm2712-rpi-5-b.dtb`, cannot apply its vendor `bcm2712d0.dtbo`, and the kernel
panics with an SError before any console.
Revision 3 appends `device_tree=bcm2712-d-rpi-5-b.dtb` to config.txt; it targets
D0 boards only and must not be installed on C0/C1-stepping Pi 5 hardware.
Revision 1's raw disk image also omitted the Pi boot overlay; do not flash it.

**Hardware status:** revision 2 also failed to return from a Pi 5 upgrade.
It is not validated for deployment. Subsequent diagnostics paired its stock
kernel with the old vendor device tree and reached userspace without networking;
that incompatible pairing is a separate failure, not proof of the original cause.
See the [incident findings](COMPARISON.md#september-20-hardware-findings).

The vendor kernel, replacement module list, old open_tree workaround, and
image-naming source patches are no longer built or applied.
See [COMPARISON.md](COMPARISON.md) for the comparison and hardware boundaries.

## Validation status

The boot-selection regression suite runs on Linux. Installer verification checks
architecture, version and UKI, then checks the compiled U-Boot MMU map against
the NVMe PCI windows in both C0 and D0 device trees, and requires the installer's
overlay options to append the D0 `device_tree=` selection. The legacy D0 filename
is still overwritten with the stock D0 tree, but current EEPROM firmware ignores
that name and applies `bcm2712d0.dtbo` to the base tree instead.
The RP1 check also requires the stock kernel's nexus layout and an enabled,
correctly connected Ethernet/PHY node. This guards against mixing vendor boot
assets with the stock kernel; it does not prove the full image boots on hardware.
Raw-image verification decompresses the actual disk artifact, attaches it as a
read-only loop device, mounts its EFI partition read-only, and checks the same
U-Boot/DTB compatibility plus Pi boot configuration, EFI loader and UKI.
These checks do not replace a physical Pi test: fresh boot, NVMe, Ethernet,
cooling and upgrade/rollback must be verified before production use.
The old vendor-kernel release's CM5/peripheral claims do not apply to this image.

## Build locally

Requires Docker Buildx, Git, GNU Make 4+ and Python 3. On macOS use `gmake`.
Use a Linux/arm64-capable builder. `make verify` additionally needs a Linux host
with zstd, util-linux, udevadm and sudo access for read-only loop mounts.
No image is published by these commands:

```sh
make checkouts patches
make test
make overlay
make installer
make verify
```

Outputs:

- `_out/installer-arm64.tar`: upgrade installer, tagged locally as
  `talos-rpi5-installer:local`.
- `_out/metal-arm64.raw.zst`: fresh-install disk image.
- `_out/overlay/` and `_out/installer-base/`: local OCI inputs.

The overlay device trees come from the exact stock kernel package pinned by
Talos. A locally built, patched imager combines that stock kernel with our
patched Talos initramfs and installer binary. The sd-boot patches preserve boot
selection and run the overlay installer when preparing raw-image partitions.
Using the official imager bypasses the latter fix and produces an incomplete
Pi raw image. The local imager is loaded into Docker, never published.

The existing gVisor extension is retained by default. Set `EXTENSIONS=` to omit
it, or provide compatible extension image references. It is not required for
Pi boot, NVMe or Ethernet.

## Publish and install

Publishing is a separate, explicit step and requires crane plus registry access:

```sh
make release TAG=v1.14.1 REGISTRY_USERNAME=lkshrk
```

After hardware validation, the upgrade command is:

```sh
talosctl upgrade --nodes <node-ip> --reboot-mode powercycle \
  --image ghcr.io/lkshrk/talos-rpi5-installer:v1.14.1
```

For a fresh installation, decompress `metal-arm64.raw.zst` and flash it to the
intended boot disk. Flashing destroys that disk's existing contents.

CI builds pull requests without publishing container images, and retains the
candidate installer/raw image as workflow artifacts. The existing tagged and
main-version-bump release flows publish prereleases only after build and
verification pass. The package tag is `TALOS_VERSION`, which Tuppr resolves
directly. Set `IMAGE_REVISION` only for a repair rebuild of the same Talos
version; that adds `-rpi5.<IMAGE_REVISION>` and needs the runtime alias workflow.

An unreachable node cannot consume a new installer over its Talos API. Recovery
of the withdrawn image may require restoring the complete known-working boot
assets: selecting the old UKI alone does not restore overwritten shared DTBs.

## Maintenance

See [UPGRADING.md](UPGRADING.md). `make clean` deletes generated checkouts and
artifacts, leaving source patches intact.

## License

See [LICENSE](LICENSE).
