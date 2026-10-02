# GBA-StoneOfBeginnings
Translation for the GBA Japanese game Summon Night Craftsword Monogatari - Hajimari no Ishi

The tracked `build_scripts.manifest` selects one script for every ROM address.
It contains 1,052 unique addresses; the 51 files in `script/Day2_scripts/`
duplicate root addresses and are intentional overrides. Regenerate it with
`python3 generate_build_manifest.py`, or verify it is current with
`python3 generate_build_manifest.py --check`.

To build on Linux or macOS, install Python 3, make, a C++14 compiler, and
`armips`, then run `./build_full.sh /path/to/your-Japanese-ROM.gba`. The source
ROM SHA-1 must be `3f5253fcf57e07ce52472bd29a61d16b98a12376`. The build creates
`swordcraft3-test.gba` and removes its temporary local input copy on exit. The
script checks before writing and refuses to overwrite an existing build or
input copy. On Windows, run `build_full.bat` with the same optional ROM path;
Python, make, a C++ compiler, certutil, and armips on PATH are required.

Both scripts compile the native inserters serially, apply the assembly and
system-message patch, then dry-run every manifest source against its ROM gap.
They insert the scripts only after all 1,052 pass preflight, and stop at the
first write failure.
They do not create or use save files. Keep emulator saves outside the build
directory and test with a copied save when one is needed.

The static UI report is regenerated with
`python3 qa/measure_text.py`. It measures the 1,052 manifest-selected runtime
scripts, including all 51 Day 2 overrides, plus `system_messages/`. Dynamic
`[NAME n]` substitutions are reported separately because their runtime width
depends on engine-provided values. Raw Greek β–ρ encode NAME0–NAME15 in the
runtime text encoding.

`qa/source_control_manifest.json` records only original-ROM control tokens,
their script/block positions, alignment status, and ROM SHA-1; it contains no
ROM dialogue text. The integrity check compares controls against this map, not
against English `HEAD` payloads, and reports any source blocks that could not
be aligned safely. The build verifies this map against the supplied source ROM.
