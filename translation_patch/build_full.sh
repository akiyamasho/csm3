#!/usr/bin/env bash
set -euo pipefail

CALLER_DIR=$PWD
PATCH_DIR=$(cd "$(dirname "$0")" && pwd)
cd "$PATCH_DIR"
SOURCE_ROM=${1:-"$PATCH_DIR/../csm3.gba"}
case "$SOURCE_ROM" in
    /*) ;;
    *) SOURCE_ROM="$CALLER_DIR/$SOURCE_ROM" ;;
esac
ROM_SHA1=3f5253fcf57e07ce52472bd29a61d16b98a12376
INPUT_ROM="$PATCH_DIR/swordcraft3.gba"
OUTPUT_ROM="$PATCH_DIR/swordcraft3-test.gba"

if [[ ! -f "$SOURCE_ROM" ]]; then
    echo "error: source ROM not found: $SOURCE_ROM" >&2
    echo "usage: $0 [path/to/your-Japanese-ROM.gba]" >&2
    exit 2
fi
ARMIPS=$(command -v armips || true)
if [[ -z "$ARMIPS" || ! -x "$ARMIPS" ]]; then
    echo "error: armips is required on PATH" >&2
    exit 2
fi
if [[ -e "$INPUT_ROM" || -e "$OUTPUT_ROM" ]]; then
    echo "error: refusing to overwrite $INPUT_ROM or $OUTPUT_ROM" >&2
    echo "Move existing build files aside before building again." >&2
    exit 2
fi

if command -v shasum >/dev/null 2>&1; then
    actual_sha1=$(shasum -a 1 "$SOURCE_ROM" | awk '{print $1}')
else
    actual_sha1=$(sha1sum "$SOURCE_ROM" | awk '{print $1}')
fi
if [[ "$actual_sha1" != "$ROM_SHA1" ]]; then
    echo "error: source ROM SHA-1 is $actual_sha1; expected $ROM_SHA1" >&2
    exit 2
fi

cp "$SOURCE_ROM" "$INPUT_ROM"
success=0
cleanup() {
    rm -f "$INPUT_ROM"
    if [[ "$success" != 1 ]]; then
        rm -f "$OUTPUT_ROM"
    fi
}
trap cleanup EXIT

export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

python3 generate_build_manifest.py --check
python3 qa/check_translation_integrity.py --no-diff --rom "$SOURCE_ROM"
nice -n 15 make -C script_inserter -j1 all
nice -n 15 "$ARMIPS" swordcraft3.asm
nice -n 15 "$PATCH_DIR/script_inserter/swordcraft3-menu" "$OUTPUT_ROM" \
    system_messages/magic.txt system_messages/weapons.txt system_messages/link.txt \
    system_messages/effects.txt system_messages/special_attacks.txt \
    system_messages/dictionary.txt system_messages/items.txt system_messages/menu.txt \
    system_messages/bonus.txt system_messages/menu3.txt

failed=0
while read -r script position; do
    [[ -z "${script:-}" ]] && continue
    if ! nice -n 15 "$PATCH_DIR/script_inserter/swordcraft3c" "$OUTPUT_ROM" "$script" "$position" --dry-run --quiet; then
        echo "preflight failure at $position ($script)" >&2
        failed=$((failed + 1))
    fi
done < build_scripts.manifest
if [[ "$failed" != 0 ]]; then
    echo "error: preflight found $failed script allocation failure(s); no script payloads were inserted" >&2
    exit 1
fi

while read -r script position; do
    [[ -z "${script:-}" ]] && continue
    if ! nice -n 15 "$PATCH_DIR/script_inserter/swordcraft3c" "$OUTPUT_ROM" "$script" "$position" --quiet; then
        echo "error: script insertion failed at $position ($script)" >&2
        exit 1
    fi
done < build_scripts.manifest

success=1
echo "Build complete: $OUTPUT_ROM"
