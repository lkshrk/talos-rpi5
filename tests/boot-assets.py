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


def rejects(candidate, reason):
    try:
        verify(candidate)
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
    print("PASS: old mapping, stale D0 alias and unrelated tuple are rejected")


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
