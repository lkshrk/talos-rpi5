#!/usr/bin/env python3
"""Check the published installer contract without running or installing it."""
import json
import runpy
import sys
import tarfile
from pathlib import Path

directory = Path(sys.argv[1])
version = sys.argv[2]
with tarfile.open(directory / "installer-arm64.tar") as archive:
    manifest = json.load(archive.extractfile("manifest.json"))
    assert len(manifest) == 1, "expected one installer image"
    config = json.load(archive.extractfile(manifest[0]["Config"]))
    assert config["architecture"] == "arm64" and config["os"] == "linux"
    assert config["config"]["Labels"]["alpha.talos.dev/version"] == version
    assert config["config"]["Entrypoint"] == ["/bin/installer"]
    files = set()
    boot_files = {}
    for layer in manifest[0]["Layers"]:
        with tarfile.open(fileobj=archive.extractfile(layer), mode="r|*") as contents:
            for member in contents:
                if not member.isfile():
                    continue
                name = member.name.removeprefix("./").lstrip("/")
                files.add(name)
                if name.startswith("overlay/artifacts/arm64/") and name.endswith((".dtb", "u-boot.bin")):
                    boot_files[name] = contents.extractfile(member).read()
    required = {
        "usr/install/arm64/vmlinuz.efi",
        "usr/install/arm64/systemd-boot.efi",
        "overlay/installers/default",
        "overlay/artifacts/arm64/u-boot/rpi5/u-boot.bin",
        "overlay/artifacts/arm64/firmware/boot/bcm2712-rpi-5-b.dtb",
    }
    assert required <= files, f"missing boot artifacts: {sorted(required - files)}"
runpy.run_path(str(Path(__file__).with_name("verify-boot-assets.py")))["verify_boot_assets"](boot_files)
runpy.run_path(str(Path(__file__).resolve().parents[1] / "tests/boot-assets.py"))["test_boot_assets"](boot_files)
raw = directory / "metal-arm64.raw.zst"
assert raw.stat().st_size > 1024, "empty raw image"
with raw.open("rb") as stream:
    assert stream.read(4) == bytes.fromhex("28b52ffd"), "raw image is not Zstandard"
print(f"PASS: Linux/arm64 {version}, UKI, bootloader, matching Pi DTB and raw image")
