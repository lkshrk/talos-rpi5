#!/usr/bin/env python3
"""Validate the pinned Pi 5 U-Boot mapping and stock-kernel DT contracts."""
import struct
import sys
from pathlib import Path

BOOT = "overlay/artifacts/arm64/firmware/boot/"
UBOOT = "overlay/artifacts/arm64/u-boot/rpi5/u-boot.bin"
C0 = BOOT + "bcm2712-rpi-5-b.dtb"
D0 = BOOT + "bcm2712-d-rpi-5-b.dtb"
LEGACY_D0 = BOOT + "bcm2712d0-rpi-5-b.dtb"
REQUIRED = {UBOOT, C0, D0, LEGACY_D0}
DEVICE = (1 << 53) | (1 << 54)  # NGNRNE, non-shareable, PXN, UXN


def nvme_mapping(binary):
    """Find the complete pinned bcm2712_mem_map, not an unrelated byte tuple."""
    record = lambda *values: struct.pack("<4Q", *values)
    prefix = record(0, 0, 0x40000000, 0x310) + record(
        0x1000000000, 0x1000000000, 0x2000000, DEVICE
    )
    suffix = record(0x1F00000000, 0x1F00000000, 0x2000000, DEVICE) + record(
        0x107C000000, 0x107C000000, 0x4000000, DEVICE
    ) + bytes(32)
    offsets = []
    offset = binary.find(prefix)
    while offset != -1:
        if offset % 8 == 0 and binary[offset + 96:offset + 192] == suffix:
            offsets.append(offset)
        offset = binary.find(prefix, offset + 1)
    assert len(offsets) == 1, "expected exactly one recognizable BCM2712 MMU table"
    virt, phys, size, attrs = struct.unpack_from("<4Q", binary, offsets[0] + 64)
    assert virt == phys and size > 0 and attrs == DEVICE, "invalid NVMe device mapping"
    return phys, size


def dtb_nodes(blob):
    """Read flattened-device-tree nodes and properties using its v17 wire format."""
    assert len(blob) >= 40, "truncated DTB header"
    magic, total, start, strings, _, version, _, _, string_size, tree_size = struct.unpack_from(
        ">10I", blob
    )
    assert magic == 0xD00DFEED and version >= 17 and total <= len(blob), "invalid DTB header"
    assert start + tree_size <= total and strings + string_size <= total, "invalid DTB bounds"
    tree, names = blob[start:start + tree_size], blob[strings:strings + string_size]
    stack, nodes, cursor = [], {}, 0
    while cursor < len(tree):
        token, = struct.unpack_from(">I", tree, cursor)
        cursor += 4
        if token == 1:
            end = tree.index(b"\0", cursor)
            stack.append(tree[cursor:end].decode())
            nodes["/".join(stack) or "/"] = {}
            cursor = (end + 4) & ~3
        elif token == 2:
            stack.pop()
        elif token == 3:
            size, name_offset = struct.unpack_from(">2I", tree, cursor)
            cursor += 8
            assert cursor + size <= len(tree) and name_offset < len(names), "invalid DTB property"
            name = names[name_offset:names.index(b"\0", name_offset)].decode()
            nodes["/".join(stack) or "/"][name] = tree[cursor:cursor + size]
            cursor = (cursor + size + 3) & ~3
        elif token == 9:
            assert not stack, "unclosed DTB nodes"
            return nodes
        else:
            assert token == 4, f"unknown DTB token {token}"
    raise AssertionError("missing DTB end token")


def nvme_window(blob):
    nodes = dtb_nodes(blob)
    path = "/axi/pcie@1000110000"
    node = nodes[path]
    assert node.get("status", b"okay\0") in (b"okay\0", b"ok\0"), "NVMe PCIe host disabled"
    assert b"brcm,bcm2712-pcie" in node["compatible"].split(b"\0"), "unexpected NVMe controller"
    cells = lambda value: int.from_bytes(value, "big")
    assert cells(node["#address-cells"]) == 3 and cells(node["#size-cells"]) == 2
    assert cells(nodes["/axi"]["#address-cells"]) == 2
    ranges = node["ranges"]
    assert len(ranges) % 28 == 0, "invalid PCI ranges"
    windows = []
    for offset in range(0, len(ranges), 28):
        flags, _, _, hi, lo, size_hi, size_lo = struct.unpack_from(">7I", ranges, offset)
        if flags == 0x02000000:  # U-Boot NVMe uses the non-prefetchable 32-bit BAR window.
            windows.append(((hi << 32) | lo, (size_hi << 32) | size_lo))
    assert len(windows) == 1 and windows[0][1] > 0, "expected one NVMe memory window"
    return windows[0]


def verify_rp1(nodes):
    """Reject the legacy vendor bus, which stock Linux cannot use for RP1 IRQs."""
    nexus = [path for path in nodes if path.rsplit("/", 1)[-1] == "rp1_nexus"]
    assert len(nexus) == 1, "expected one mainline RP1 nexus"
    nexus = nexus[0]
    assert b"pci1de4,1" in nodes[nexus].get("compatible", b"").split(b"\0"), "invalid RP1 nexus compatible"
    ethernet = nodes.get("/aliases", {}).get("ethernet0", b"").rstrip(b"\0").decode()
    assert ethernet.startswith(nexus + "/") and ethernet in nodes, "Ethernet alias must point inside RP1 nexus"
    eth = nodes[ethernet]
    assert b"raspberrypi,rp1-gem" in eth.get("compatible", b"").split(b"\0"), "invalid RP1 Ethernet compatible"
    path = ethernet
    while path != "/":
        assert nodes[path].get("status", b"okay\0") in (b"okay\0", b"ok\0"), "RP1 Ethernet or ancestor disabled"
        path = path.rsplit("/", 1)[0] or "/"
    mdio = ethernet + "/mdio"
    assert mdio in nodes, "missing mainline Ethernet MDIO bus"
    assert nodes[mdio].get("status", b"okay\0") in (b"okay\0", b"ok\0"), "Ethernet MDIO bus disabled"
    handle = eth.get("phy-handle", b"")
    assert len(handle) == 4 and int.from_bytes(handle, "big") > 0, "invalid Ethernet PHY handle"
    phys = [path for path, props in nodes.items() if props.get("phandle") == handle]
    assert len(phys) == 1 and phys[0].rsplit("/", 1)[0] == mdio, "Ethernet PHY handle must reference MDIO child"
    phy = nodes[phys[0]]
    assert phy.get("status", b"okay\0") in (b"okay\0", b"ok\0"), "Ethernet PHY disabled"
    assert len(phy.get("reg", b"")) == 4 and int.from_bytes(phy["reg"], "big") < 32, "invalid MDIO PHY address"


def verify_boot_assets(files):
    """files maps REQUIRED full installer paths to their effective layer bytes."""
    assert REQUIRED <= files.keys(), f"missing boot assets: {sorted(REQUIRED - files.keys())}"
    base, size = nvme_mapping(files[UBOOT])
    for name in (C0, D0):
        address, length = nvme_window(files[name])
        assert base <= address and address + length <= base + size, (
            f"{name}: NVMe PCI window {address:#x}..{address + length:#x} "
            f"outside U-Boot mapping {base:#x}..{base + size:#x}"
        )
        verify_rp1(dtb_nodes(files[name]))
    assert files[LEGACY_D0] == files[D0], "legacy D0 firmware alias differs from stock D0 DTB"
    print("PASS: NVMe mappings, mainline RP1 Ethernet/MDIO contracts and D0 alias")


if __name__ == "__main__":
    root = Path(sys.argv[1])
    verify_boot_assets({name: (root / name).read_bytes() for name in REQUIRED})
