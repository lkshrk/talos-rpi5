# Raspberry Pi 5 Talos Builder

Build Talos 1.14.1 with the upstream kernel, a corrected Pi U-Boot/NVMe overlay,
and a narrow loader.conf fallback when firmware rejects EFI variable writes.
The original `v1.14.1` image was withdrawn after a failed Pi upgrade. The repair
candidate is `v1.14.1-rpi5.1`; it does not overwrite the withdrawn tag.

The vendor kernel, replacement module list, old open_tree workaround, and
image-naming source patches are no longer built or applied.
See [COMPARISON.md](COMPARISON.md) for the comparison and hardware boundaries.

## Validation status

The boot-selection regression suite runs on Linux. Installer verification checks
architecture, version and UKI, then checks the compiled U-Boot MMU map against
the NVMe PCI windows in both C0 and D0 device trees. The firmware's legacy D0
filename must contain the same stock D0 tree, so upgrades overwrite old vendor
copies instead of leaving them selectable by older EEPROM firmware.
These checks do not replace a physical Pi test: fresh boot, NVMe, Ethernet,
cooling and upgrade/rollback must be verified before production use.
The old vendor-kernel release's CM5/peripheral claims do not apply to this image.

## Build locally

Requires Docker Buildx, Git, GNU Make 4+ and Python 3. On macOS use `gmake`.
Use a Linux/arm64-capable builder.
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
Talos. The official imager combines that stock kernel with our patched Talos
initramfs and installer binary. Only the sd-boot patch changes Talos behavior.

The existing gVisor extension is retained by default. Set `EXTENSIONS=` to omit
it, or provide compatible extension image references. It is not required for
Pi boot, NVMe or Ethernet.

## Publish and install

Publishing is a separate, explicit step and requires crane plus registry access:

```sh
make release TAG=v1.14.1-rpi5.1 REGISTRY_USERNAME=lkshrk
```

After hardware validation, the upgrade command is:

```sh
talosctl upgrade --nodes <node-ip> --reboot-mode powercycle \
  --image ghcr.io/lkshrk/talos-rpi5-installer:v1.14.1-rpi5.1
```

For a fresh installation, decompress `metal-arm64.raw.zst` and flash it to the
intended boot disk. Flashing destroys that disk's existing contents.

CI builds pull requests without publishing container images, and retains the
candidate installer/raw image as workflow artifacts. The existing tagged and
main-version-bump release flows publish prereleases only after build and
verification pass. The package tag adds `-rpi5.<IMAGE_REVISION>`; the Talos
version inside the image stays `TALOS_VERSION`.

An unreachable node cannot consume a new installer over its Talos API. Recovery
of the withdrawn image may require restoring the complete known-working boot
assets: selecting the old UKI alone does not restore overwritten shared DTBs.

## Maintenance

See [UPGRADING.md](UPGRADING.md). `make clean` deletes generated checkouts and
artifacts, leaving source patches intact.

## License

See [LICENSE](LICENSE).
