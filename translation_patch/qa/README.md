# UI overflow QA

Run from the repository root after translation changes:

```sh
python3 translation_patch/qa/check_translation_integrity.py --base-ref HEAD --rom /path/to/original.gba
python3 translation_patch/qa/measure_text.py --fail-on-static-overflow
```

The integrity checker requires exactly one manifest source per address,
valid quoted payloads, no unintended Japanese runtime strings, and the same
ordered commands, labels, opcodes, operands, and branch targets as the selected
Git baseline. It ignores changes within quoted text payloads, so fit reflow is
allowed while page commands and code remain protected. Dynamic NAME
substitutions are compared with `source_control_manifest.json`, generated from
the original ROM, using verified contiguous dialogue blocks and uniquely
anchored runtime strings. English `HEAD` text is not treated as proof that a
NAME control existed in the original. Non-NAME bracket controls (including
WIDTH, OUT, and ERROR) are compared per payload block against the selected Git
baseline. Pass `--rom path/to/original.gba` for release
checks; it verifies the ROM SHA-1 recorded in the manifest. Any source blocks
without a safe alignment are reported explicitly, and
`--require-source-alignment` makes those cases fail. In CI, run with `--no-diff`
for corpus-level checks. Rebuild the token-only sidecar with
`python3 translation_patch/qa/extract_original_text.py --rom /path/to/original.gba --output translation_patch/qa/source_control_manifest.json`.
The checker scans only the 1,052 manifest-selected scripts (including the 51
Day 2 overrides) and all system-message files.

The width parser measures the first quoted runtime field before any semicolon
comment. This is important for system-message rows, which retain the original
Japanese text as a second quoted field after the translated payload; escaped
quotes inside the runtime field remain part of that payload. Run the focused
regression tests with:

```sh
python3 -m unittest discover -s translation_patch/qa -p 'test_*.py'
```

For machine-readable release manifests, add `--tsv /tmp/csm3_overflow_release.tsv`.

The checker parses the shipped VWF ASCII advance table and mirrors the patched
renderer’s 12px ordinary JIS advance. Raw Greek beta through rho are runtime
NAME0 through NAME15 controls, so they are measured dynamically along with
explicit name tokens. Static failures are fixed-text lines above the safe
width; dynamic worst-case findings remain separate because player and partner
names can vary. It measures all 1,052 selected script sources, including the
51 Day 2 overrides, plus system-message files.

These static checks validate layout syntax, source-backed NAME controls, and
estimated width. They do not establish semantic correctness for every scene.

The integrity checker permits Japanese runtime payload only in the actual name
keyboard grid at `system_messages/menu.txt` addresses `0x08bd5618` through
`0x08bd5668` (21 active rows, 16 with Japanese glyphs). These glyphs are the
player’s kana/character selection choices. The generated
`ui_overflow_report.md` is a review artifact and should be regenerated after
translation edits or parser changes.

Static results cannot prove caller-specific placement, sprite composition, or
the actual runtime width of a player-entered name. Those cases are explicitly
marked and require emulator screenshot QA with representative save states.

## Final release validation

The final source integrity check passed for 1,052 selected scripts (including
51 Day 2 overrides) and 10 system-message files. It found zero unintended
Japanese runtime strings: the 16 Japanese hits are functional keyboard rows.
All 76 of 76 current NAME-bearing runtime strings are mapped to original-ROM
proof, and no current NAME-bearing field is unmapped. The source map verifies
18,766 of 19,246 dialogue blocks. The 480 unaligned blocks are original-only
dialogue blocks across 61 files; the checker reports 64 scripts with
inconclusive areas overall because three additional cases concern non-dialogue
structure rather than unaligned dialogue blocks.

The VWF width pass checked 43,608 fields and found zero static overflows or
safe-margin overflows. It reports 226 dynamic worst-case overflows and 1,592
dynamic reviews separately because player-entered names vary. The previously
completed focused suite passed 18 tests; code was unchanged for this final
source-only adjustment, so that suite was not rerun.

The final native build completed in 16.48 seconds with 115,441,664 bytes peak
RSS and no swap use. Its 58,686-byte insertion count is for menu/system-message
strings, not the total script payload. Assembly emitted the inherited overlap
warning between `0x080A87CC` and `0x080A880E`; no assembly source was changed.
Emulator UI inspection was not performed in this final pass. The pinned source
ROM SHA-1 was `3f5253fcf57e07ce52472bd29a61d16b98a12376`; the original user ROM,
saves, and emulator state were left untouched.
