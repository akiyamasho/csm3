#!/usr/bin/env python3
"""Generate the deterministic one-script-per-ROM-address insertion manifest.

Root scripts are the default corpus. If a Day2 script has the same ROM address,
the Day2 variant wins because that is the existing build's deliberate policy.
"""
import argparse
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE / "script"
DAY2 = ROOT / "Day2_scripts"
OUT = HERE / "build_scripts.manifest"
ADDRESS = re.compile(r"^([0-9a-fA-F]+)\.txt$")

def scripts(folder):
    result = {}
    for path in sorted(folder.glob("*.txt"), key=lambda p: p.name.lower()):
        match = ADDRESS.match(path.name)
        if not match:
            raise ValueError(f"script filename is not a hexadecimal ROM address: {path}")
        address = match.group(1).lower()
        if address in result:
            raise ValueError(f"duplicate address {address} within {folder}")
        result[address] = path
    return result

def render_manifest():
    root_scripts = scripts(ROOT)
    day2_scripts = scripts(DAY2)
    selected = dict(root_scripts)
    selected.update(day2_scripts)
    if len(root_scripts) != 1052 or len(selected) != 1052:
        raise ValueError(
            f"expected 1,052 root and unique script addresses; found "
            f"{len(root_scripts)} root and {len(selected)} unique"
        )
    if not set(day2_scripts).issubset(root_scripts):
        only_day2 = sorted(set(day2_scripts) - set(root_scripts))
        raise ValueError(
            "Day 2 must be a duplicate-only corpus whose addresses exist in "
            f"the root corpus (Day2-only={only_day2})"
        )
    lines = []
    for address in sorted(selected):
        path = selected[address]
        rel = path.relative_to(HERE).as_posix()
        lines.append(f"{rel} --pos={address}")
    return "\n".join(lines) + "\n", len(day2_scripts)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the tracked manifest is stale")
    args = parser.parse_args()
    try:
        expected, overrides = render_manifest()
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if args.check:
        actual = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if actual != expected:
            print(f"error: {OUT} is stale; run python3 {Path(__file__).name}", file=sys.stderr)
            return 1
        print(f"manifest is current ({1052} unique addresses; {overrides} Day 2 overrides)")
        return 0

    OUT.write_text(expected, encoding="utf-8")
    print(f"wrote {OUT} ({1052} unique addresses; {overrides} Day 2 overrides)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
