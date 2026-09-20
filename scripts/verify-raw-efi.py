#!/usr/bin/env python3
"""Verify actual files from the raw image's read-only mounted EFI partition."""
import runpy
import sys
from pathlib import Path


def verify_raw_efi(root):
    verifier = runpy.run_path(str(Path(__file__).with_name("verify-boot-assets.py")))
    files = {name: (root / Path(name).name).read_bytes() for name in verifier["REQUIRED"]}
    verifier["verify_boot_assets"](files)
    config = {line.strip() for line in (root / "config.txt").read_text().splitlines()}
    assert "kernel=u-boot.bin" in config and "arm_64bit=1" in config, "missing Pi boot configuration"
    assert "device_tree=bcm2712-d-rpi-5-b.dtb" in config, "firmware must load the stock D0 device tree"
    assert (root / "EFI/boot/BOOTAA64.efi").stat().st_size > 0, "missing ARM64 EFI loader"
    assert any(path.stat().st_size > 0 for path in (root / "EFI/Linux").glob("Talos-*.efi")), "missing Talos UKI"
    assert (root / "loader/loader.conf").stat().st_size > 0, "missing loader configuration"
    print("PASS: raw EFI contains compatible Pi firmware/U-Boot/DTBs, config, EFI loader and UKI")


if __name__ == "__main__":
    verify_raw_efi(Path(sys.argv[1]))
