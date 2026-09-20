#!/usr/bin/env python3
"""Regression check using real extracted assets: python3 tests/boot-assets.py ROOT."""
import runpy
import struct
import sys
from pathlib import Path

check = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/verify-boot-assets.py"))
verify = check["verify_boot_assets"]
uboot = check["UBOOT"]
old = struct.pack("<3Q", 0x1B80000000, 0x1B80000000, 0x80000000)
fixed = struct.pack("<3Q", 0x1B00000000, 0x1B00000000, 0x100000000)


def rejects(candidate, reason, verifier=verify):
    try:
        verifier(candidate)
    except AssertionError as error:
        assert reason in str(error), str(error)
    else:
        raise AssertionError(f"accepted regression: {reason}")


def test_boot_assets(files):
    verify(files)
    assert files[uboot].count(fixed) == 1, "expected one corrected NVMe map"
    rejects(files | {uboot: files[uboot].replace(fixed, old)}, "outside U-Boot mapping")
    rejects(files | {check["LEGACY_D0"]: b"stale vendor DTB"}, "alias differs")
    rejects(files | {uboot: fixed}, "MMU table")
    blob = files[check["C0"]]
    rejects(files | {check["C0"]: blob.replace(b"rp1_nexus", b"rp1_wrong")}, "RP1 nexus")
    nodes = check["dtb_nodes"](blob)
    ethernet = nodes["/aliases"]["ethernet0"].rstrip(b"\0").decode()
    rejects(nodes | {ethernet: nodes[ethernet] | {"status": b"disabled\0"}}, "disabled", check["verify_rp1"])
    rejects(nodes | {ethernet: nodes[ethernet] | {"phy-handle": b"\xff" * 4}}, "MDIO child", check["verify_rp1"])
    print("PASS: old mapping, stale alias, unrelated MMU tuple and broken RP1/PHY bindings rejected")


if __name__ == "__main__":
    root = Path(sys.argv[1])
    files = {name: (root / name).read_bytes() for name in check["REQUIRED"] if (root / name).exists()}
    if "--repair-fixture" in sys.argv[2:]:
        # Detector regression only: mutating old bytes does not validate a fixed build.
        check["nvme_mapping"](files[uboot])
        files[uboot] = files[uboot].replace(old, fixed)
        files[check["LEGACY_D0"]] = files[check["D0"]]
        print("Fixture repair enabled: this does not validate a corrected build")
    test_boot_assets(files)
