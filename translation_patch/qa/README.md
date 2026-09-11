# UI overflow QA

Run from the repository root:

```sh
python3 translation_patch/qa/measure_text.py
```

The parser measures the first quoted runtime field before any semicolon
comment. This is important for system-message rows, which retain the original
Japanese text as a second quoted field after the translated payload; escaped
quotes inside the runtime field remain part of that payload. Run the focused
regression tests with:

```sh
python3 -m unittest discover -s translation_patch/qa -p 'test_*.py'
```

For machine-readable release manifests, add `--tsv /tmp/csm3_overflow_release.tsv`.

The checker parses the shipped VWF ASCII advance table and mirrors the patched
renderer’s 12px JIS advance. It reports hard screen overflows, conservative
safe-margin risks, and dynamic `[NAME n]` substitutions separately. It skips
`script/Day2_scripts/`, which is a duplicate corpus. The generated
`ui_overflow_report.md` is a review artifact and should be regenerated after
translation edits or parser changes. Its static hard/safe counts cover the
translated runtime payloads; dynamic counts remain review findings for
runtime substitutions such as player-entered names.

Static results cannot prove caller-specific placement, sprite composition, or
the actual runtime width of a player-entered name. Those cases are explicitly
marked and require emulator screenshot QA with representative save states.
