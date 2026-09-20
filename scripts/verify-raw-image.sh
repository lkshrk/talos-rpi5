#!/usr/bin/env bash
# Inspect the generated disk image, never a host disk. Linux + sudo required.
set -euo pipefail
image=$(realpath "$1")
scripts=$(cd -- "$(dirname -- "$0")" && pwd)
scratch=$(mktemp -d)
loop=
mounted=false
cleanup() {
    if "$mounted"; then sudo umount "$scratch/efi" || return; fi
    if [[ -n "$loop" ]]; then sudo losetup --detach "$loop" || return; fi
    rm -rf -- "$scratch"
}
trap cleanup EXIT
zstd --decompress --quiet --stdout "$image" > "$scratch/image.raw"
loop=$(sudo losetup --find --show --partscan --read-only "$scratch/image.raw")
sudo udevadm settle
mapfile -t partitions < <(lsblk --list --noheadings --output PATH,PARTTYPE "$loop" |
    awk 'tolower($2) == "c12a7328-f81f-11d2-ba4b-00a0c93ec93b" { print $1 }')
[[ ${#partitions[@]} -eq 1 ]] || { echo "Expected exactly one EFI partition" >&2; exit 1; }
mkdir "$scratch/efi"
sudo mount -o ro "${partitions[0]}" "$scratch/efi"
mounted=true
python3 "$scripts/verify-raw-efi.py" "$scratch/efi"
