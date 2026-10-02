#!/usr/bin/env python3
"""Check selected script coverage, runtime payload language, and protected structure."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

from measure_text import manifest_script_paths, runtime_quoted_matches, unescape

TEXT_COMMANDS = {
    "dialogtxt", "dialogbig", "choicetxt", "placetxt", "popuptxt",
    "menutxt", "menutxtp", "tabletxt", "asciiz", "ascii", "sjis",
    "sjisn", "dictionarytxt", "setname",
}
COMMAND = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\b(.*)$")
LABEL = re.compile(r"^\s*(@[A-Za-z0-9_]+:)\s*$")
SOURCE_LABEL_BOUNDARY = re.compile(r"^@[A-Za-z][A-Za-z0-9]*_[0-9A-Fa-f]+:$")
JAPANESE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uff66-\uff9f]")
NAME_CONTROL_GLYPHS = "βγδεζηθικλμνξοπρ"
CONTROL_TOKEN = re.compile(r"\[[^\]\r\n]+\]|[βγδεζηθικλμνξοπρ]")
DIALOGUE_BLOCK_COMMANDS = {"dialogtxt", "dialogbig", "choicetxt", "placetxt", "popuptxt"}
JAPANESE_KEYBOARD_ROWS = {
    ("system_messages/menu.txt", f"{address:08x}")
    for address in range(0x08BD5618, 0x08BD566C, 4)
}


def strip_comment(line: str) -> str:
    in_quote = False
    escaped = False
    for index, char in enumerate(line):
        if escaped:
            escaped = False
        elif in_quote and char == "\\":
            escaped = True
        elif char == '"':
            in_quote = not in_quote
        elif char == ";" and not in_quote:
            return line[:index]
    return line


def valid_quotes(line: str) -> bool:
    in_quote = False
    escaped = False
    for char in line:
        if escaped:
            escaped = False
        elif in_quote and char == "\\":
            escaped = True
        elif char == '"':
            in_quote = not in_quote
    return not in_quote


def structure(lines: list[str]) -> list[tuple[str, int]]:
    result = []
    for lineno, raw in enumerate(lines, 1):
        line = strip_comment(raw).strip()
        if not line:
            continue
        label = LABEL.match(line)
        if label:
            result.append((label.group(1), lineno))
            continue
        match = COMMAND.match(line)
        if not match:
            result.append((re.sub(r"\s+", " ", line), lineno))
            continue
        command, tail = match.groups()
        if command in TEXT_COMMANDS:
            # Payload wording may change, but the quoted fields, command,
            # operands, opcodes, and branch targets around it must remain.
            tail = re.sub(r'"(?:\\.|[^"\\])*"', '"<TEXT>"', tail)
        result.append((command + " " + re.sub(r"\s+", " ", tail).strip(), lineno))
    return result


def protected_text_tokens(lines: list[str]) -> list[tuple[str, tuple[str, ...]]]:
    """Keep inline control tokens in their text block and exact order."""
    blocks: list[tuple[str, tuple[str, ...]]] = []
    dialogue_tokens: list[str] = []
    dialogue_start = 0
    command_ordinal = 0

    def flush_dialogue() -> None:
        nonlocal dialogue_start
        if dialogue_start:
            blocks.append((f"dialogue-block:{dialogue_start}", tuple(dialogue_tokens)))
            dialogue_start = 0
            dialogue_tokens.clear()

    for raw in lines:
        line = strip_comment(raw).strip()
        if not line:
            continue
        if LABEL.match(line):
            flush_dialogue()
            continue
        match = COMMAND.match(line)
        if not match:
            flush_dialogue()
            continue
        command_ordinal += 1
        command = match.group(1)
        if command not in TEXT_COMMANDS:
            flush_dialogue()
            continue
        tokens_list = []
        for quote in runtime_quoted_matches(raw):
            for token in CONTROL_TOKEN.finditer(unescape(quote.group(0))):
                glyph = token.group(0).lower()
                tokens_list.append(
                    f"[NAME {NAME_CONTROL_GLYPHS.index(glyph)}]" if glyph in NAME_CONTROL_GLYPHS
                    else token.group(0)
                )
        tokens = tuple(tokens_list)
        if command in DIALOGUE_BLOCK_COMMANDS:
            if not dialogue_start:
                dialogue_start = command_ordinal
            dialogue_tokens.extend(tokens)
        else:
            flush_dialogue()
            blocks.append((f"{command}-payload:{command_ordinal}", tokens))
    flush_dialogue()
    return blocks


def protected_non_name_tokens(lines: list[str]) -> list[tuple[str, tuple[str, ...]]]:
    """Return controls enforced against HEAD; NAME tokens use original-ROM proof."""
    explicit_name = re.compile(r"\[\s*NAME\s+\d+\s*\]", re.IGNORECASE)
    return [
        (block, tuple(token for token in tokens if not explicit_name.fullmatch(token)))
        for block, tokens in protected_text_tokens(lines)
    ]


def source_payloads(path: Path):
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        cm = COMMAND.match(strip_comment(raw))
        if not cm or cm.group(1) not in TEXT_COMMANDS:
            continue
        for quoted in runtime_quoted_matches(raw):
            yield lineno, unescape(quoted.group(0))


def base_text(ref: str, relative: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f"{ref}:{relative}"], text=True, capture_output=True, check=False
    )
    return result.stdout if result.returncode == 0 else None


def dialogue_token_blocks(lines: list[str]) -> list[tuple[str, ...]]:
    """Return controls grouped by contiguous dialogtxt blocks."""
    result: list[tuple[str, ...]] = []
    block: list[str] = []
    block_started = False

    def flush() -> None:
        nonlocal block_started
        if block_started:
            result.append(tuple(block))
            block_started = False
            block.clear()

    for raw in lines:
        line = strip_comment(raw).strip()
        if not line:
            continue
        if LABEL.match(line):
            if SOURCE_LABEL_BOUNDARY.fullmatch(line):
                flush()
            continue
        match = COMMAND.match(line)
        if not match or match.group(1) != "dialogtxt":
            flush()
            continue
        block_started = True
        for quote in runtime_quoted_matches(raw):
            for token in CONTROL_TOKEN.finditer(unescape(quote.group(0))):
                value = token.group(0)
                glyph = value.lower()
                if glyph in NAME_CONTROL_GLYPHS:
                    block.append(f"[NAME {NAME_CONTROL_GLYPHS.index(glyph)}]")
                else:
                    name = re.fullmatch(r"\[\s*NAME\s+(\d+)\s*\]", value, re.IGNORECASE)
                    block.append(f"[NAME {int(name.group(1))}]" if name else value)
    flush()
    return result


def normalize_source_tokens(tokens: list[str]) -> tuple[str, ...]:
    return tuple(
        f"[NAME {int(token[6:-1])}]" if token.startswith("{NAME_") else token
        for token in tokens
    )


def comparison_group_expectations(group: dict) -> list[tuple[str, ...]]:
    # Some approved groups (including common-prefix mappings) store the
    # original token sequence per source path, even when their mapping kind
    # is not the simple alternative_branch label.
    if "original_alternative_tokens" in group:
        return [
            normalize_source_tokens(tokens)
            for tokens in group.get("original_alternative_tokens", [])
        ]
    return [normalize_source_tokens(group.get("original_tokens", []))]


def current_line_tokens(raw: str) -> tuple[str, ...]:
    result: list[str] = []
    for quote in runtime_quoted_matches(raw):
        for token in CONTROL_TOKEN.finditer(unescape(quote.group(0))):
            value = token.group(0)
            glyph = value.lower()
            if glyph in NAME_CONTROL_GLYPHS:
                result.append(f"[NAME {NAME_CONTROL_GLYPHS.index(glyph)}]")
            else:
                name = re.fullmatch(r"\[\s*NAME\s+(\d+)\s*\]", value, re.IGNORECASE)
                result.append(f"[NAME {int(name.group(1))}]" if name else value)
    return tuple(result)


def unmapped_dialogue_name_blocks(lines: list[str], covered_blocks: set[int]) -> list[tuple[int, tuple[str, ...]]]:
    return [
        (index, tokens)
        for index, tokens in enumerate(dialogue_token_blocks(lines))
        if index not in covered_blocks and tokens
    ]


def unmapped_runtime_name_fields(lines: list[str], mapped_lines: set[int]) -> list[tuple[int, tuple[str, ...]]]:
    findings = []
    for lineno, raw in enumerate(lines, 1):
        command = COMMAND.match(strip_comment(raw))
        if not command or command.group(1) not in TEXT_COMMANDS - {"dialogtxt"}:
            continue
        if lineno in mapped_lines:
            continue
        tokens = current_line_tokens(raw)
        if tokens:
            findings.append((lineno, tokens))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--manifest", type=Path, help="default: <root>/build_scripts.manifest")
    parser.add_argument(
        "--script", action="append", type=Path, default=[],
        help="limit checks to a manifest-selected script (repeat for a worker-owned scope)",
    )
    parser.add_argument(
        "--source-control-manifest", type=Path,
        help="default: <root>/qa/source_control_manifest.json (controls decoded from the original ROM)",
    )
    parser.add_argument("--rom", type=Path, help="optional original ROM; verify its SHA-1 against the source control manifest")
    parser.add_argument("--require-source-alignment", action="store_true", help="fail if any original/current dialogue or runtime string lacks a verified source mapping")
    parser.add_argument("--base-ref", default="HEAD", help="git ref for protected-structure comparisons")
    parser.add_argument("--no-diff", action="store_true", help="run corpus checks without a Git baseline")
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = (args.manifest or root / "build_scripts.manifest").resolve()
    source_control_manifest = (args.source_control_manifest or root / "qa/source_control_manifest.json").resolve()
    try:
        scripts = manifest_script_paths(root, manifest)
        control_data = json.loads(source_control_manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    expected_rom_sha1 = str(control_data.get("expected_rom_sha1", "")).lower()
    recorded_rom_sha1 = str(control_data.get("rom_sha1", "")).lower()
    records = control_data.get("records")
    if not expected_rom_sha1 or expected_rom_sha1 != recorded_rom_sha1 or not isinstance(records, dict):
        print("error: invalid original-ROM control manifest provenance", file=sys.stderr)
        return 1
    if len(records) != 1052:
        print(f"error: original-ROM control manifest has {len(records)} addresses, expected 1052", file=sys.stderr)
        return 1
    if args.rom:
        try:
            digest = hashlib.sha1(args.rom.read_bytes()).hexdigest()
        except OSError as error:
            print(f"error: cannot read original ROM {args.rom}: {error}", file=sys.stderr)
            return 1
        if digest != recorded_rom_sha1:
            print(f"error: source control manifest ROM SHA-1 {recorded_rom_sha1} does not match {args.rom} ({digest})", file=sys.stderr)
            return 1

    manifest_script_set = {path.resolve() for path in scripts}
    scoped_scripts: list[Path] = []
    if args.script:
        for requested in args.script:
            if requested.is_absolute():
                candidate = requested.resolve()
            elif requested.parts and requested.parts[0] == root.name:
                candidate = (root.parent / requested).resolve()
            elif requested.parts and requested.parts[0] == root.parent.name:
                candidate = (root.parent.parent / requested).resolve()
            else:
                candidate = (root / requested).resolve()
            if candidate not in manifest_script_set:
                print(f"error: {requested} is not selected by the build manifest", file=sys.stderr)
                return 1
            if candidate not in scoped_scripts:
                scoped_scripts.append(candidate)
    else:
        scoped_scripts = scripts
    scope_addresses = {path.stem.lower() for path in scoped_scripts}
    scope_records = [records[address] for address in scope_addresses if address in records]
    source_dialog_blocks = [
        block for record in scope_records for block in record.get("dialog_blocks", [])
    ]
    source_runtime_strings = [
        item for record in scope_records for item in record.get("runtime_strings", [])
    ]
    source_runtime_name_strings = [item for item in source_runtime_strings if item.get("tokens")]
    source_runtime_verified_count = sum(bool(item.get("verified")) for item in source_runtime_strings)
    source_runtime_name_verified_count = sum(
        bool(item.get("tokens")) and bool(item.get("verified")) for item in source_runtime_strings
    )
    source_runtime_unverified_count = len(source_runtime_strings) - source_runtime_verified_count
    source_runtime_name_unverified_count = len(source_runtime_name_strings) - source_runtime_name_verified_count
    current_runtime_field_count = 0
    current_runtime_unmapped_count = 0
    current_runtime_unmapped_name_lines: list[str] = []

    errors: list[str] = []
    source_files = scoped_scripts if args.script else scripts + sorted((root / "system_messages").glob("*.txt"))
    selected_script_set = set(scoped_scripts)
    japanese_hits = 0
    keyboard_exemptions: set[tuple[str, str]] = set()
    changed_paths: set[str] = set()
    alignment_unverified: dict[str, list[str]] = {}

    def note_unverified(path: str, detail: str) -> None:
        alignment_unverified.setdefault(path, []).append(detail)
    if not args.no_diff:
        changed = subprocess.run(
            ["git", "diff", "--name-only", args.base_ref, "--", "translation_patch/script", "translation_patch/system_messages"],
            cwd=root.parent, text=True, capture_output=True, check=False,
        )
        if changed.returncode != 0:
            print(f"error: could not list changed corpus paths against {args.base_ref}: {changed.stderr.strip()}", file=sys.stderr)
            return 2
        changed_paths = set(changed.stdout.splitlines())
    for path in source_files:
        relative = path.relative_to(root.parent).as_posix()
        for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            content = strip_comment(raw)
            if not valid_quotes(content):
                errors.append(f"{relative}:{lineno}: unclosed quoted field")
        for lineno, payload in source_payloads(path):
            if JAPANESE.search(payload):
                japanese_hits += 1
                raw = path.read_text(encoding="utf-8").splitlines()[lineno - 1]
                address_match = re.search(r"\b0x([0-9a-fA-F]+)", raw)
                address = address_match.group(1).lower() if address_match else ""
                exception = (path.relative_to(root).as_posix(), address)
                if exception in JAPANESE_KEYBOARD_ROWS:
                    keyboard_exemptions.add(exception)
                else:
                    excerpt = JAPANESE.sub("□", payload)[:100]
                    errors.append(f"{relative}:{lineno}: Japanese runtime payload: {excerpt}")

        if args.no_diff or relative not in changed_paths:
            pass
        else:
            baseline = base_text(args.base_ref, relative)
            if baseline is not None:
                before = structure(baseline.splitlines())
                after = structure(path.read_text(encoding="utf-8").splitlines())
                old = [signature for signature, _ in before]
                new = [signature for signature, _ in after]
                if old != new:
                    mismatch = next((i for i, pair in enumerate(zip(old, new)) if pair[0] != pair[1]), min(len(old), len(new)))
                    old_item = before[mismatch] if mismatch < len(before) else ("<end>", "-")
                    new_item = after[mismatch] if mismatch < len(after) else ("<end>", "-")
                    errors.append(
                        f"{relative}: protected command/operand sequence differs at item {mismatch + 1}; "
                        f"base line {old_item[1]} {old_item[0]!r}, current line {new_item[1]} {new_item[0]!r}"
                    )
                old_controls = protected_non_name_tokens(baseline.splitlines())
                new_controls = protected_non_name_tokens(path.read_text(encoding="utf-8").splitlines())
                if old_controls != new_controls:
                    mismatch = next(
                        (i for i, pair in enumerate(zip(old_controls, new_controls)) if pair[0] != pair[1]),
                        min(len(old_controls), len(new_controls)),
                    )
                    old_item = old_controls[mismatch] if mismatch < len(old_controls) else ("<end>", ())
                    new_item = new_controls[mismatch] if mismatch < len(new_controls) else ("<end>", ())
                    errors.append(
                        f"{relative}: protected non-NAME inline controls differ at block {mismatch + 1}; "
                        f"base {old_item!r}, current {new_item!r}"
                    )

        if path not in selected_script_set:
            continue
        address = path.stem.lower()
        record = records.get(address)
        if record is None:
            errors.append(f"{relative}: no original-ROM control record for address {address}")
            continue
        if record.get("alignment") not in {"verified_full_structure", "verified_anchored_blocks"}:
            note_unverified(
                relative,
                f"{record.get('alignment')} source dialogtxt={record.get('source_dialogtxt_count')} "
                f"original dialogtxt={record.get('original_dialogtxt_count')}",
            )
            current_blocks = dialogue_token_blocks(path.read_text(encoding="utf-8").splitlines())
            if current_blocks:
                note_unverified(
                    relative,
                    f"{len(current_blocks)} current dialogue block(s) without original mapping indices={list(range(len(current_blocks)))}",
                )
            current_lines = path.read_text(encoding="utf-8").splitlines()
            for index, tokens in unmapped_dialogue_name_blocks(current_lines, set()):
                errors.append(
                    f"{relative}: current dialogue NAME controls lack verified original-source mapping "
                    f"in block {index}: {tokens!r}"
                )
            uncovered_fields = []
            for lineno, raw in enumerate(current_lines, 1):
                command = COMMAND.match(strip_comment(raw))
                if command and command.group(1) in TEXT_COMMANDS - {"dialogtxt"} and runtime_quoted_matches(raw):
                    current_runtime_field_count += 1
                    current_runtime_unmapped_count += 1
                    tokens = current_line_tokens(raw)
                    if tokens:
                        current_runtime_unmapped_name_lines.append(f"{relative}:{lineno} {tokens!r}")
                        uncovered_fields.append(str(lineno))
            if uncovered_fields:
                note_unverified(relative, f"current non-dialog runtime fields with NAME controls lack source mapping at lines={uncovered_fields}")
                errors.extend(
                    f"{relative}:{lineno}: current runtime NAME controls lack verified original-source mapping: {tokens!r}"
                    for lineno, tokens in unmapped_runtime_name_fields(current_lines, set())
                )
            continue
        current_lines = path.read_text(encoding="utf-8").splitlines()
        actual_tokens = dialogue_token_blocks(current_lines)
        covered_source_blocks: set[int] = set()
        if "comparison_groups" in record:
            for group in record.get("comparison_groups", []):
                source_indices = [int(index) for index in group.get("source_block_indices", [])]
                if not group.get("verified", False):
                    continue
                if not source_indices or any(index < 0 or index >= len(actual_tokens) for index in source_indices):
                    errors.append(f"{relative}: verified comparison group maps to absent source block(s) {source_indices}")
                    continue
                covered_source_blocks.update(source_indices)
                actual = tuple(token for index in source_indices for token in actual_tokens[index])
                expected_groups = comparison_group_expectations(group)
                if not expected_groups:
                    errors.append(f"{relative}: verified comparison group has no original token data for {source_indices}")
                    continue
                mismatched = [tokens for tokens in expected_groups if tokens != actual]
                expected_detail = f"alternatives={expected_groups!r}" if len(expected_groups) > 1 else f"expected {expected_groups[0]!r}"
                if mismatched:
                    errors.append(
                        f"{relative}: original-ROM control tokens differ in {group.get('mapping_kind')} "
                        f"group original={group.get('original_block_indices')} source={source_indices}: "
                        f"{expected_detail}, found {actual!r}"
                    )
        else:
            for block in record.get("dialog_blocks", []):
                if not block.get("verified", False):
                    continue
                source_indices = block.get("source_block_indices")
                if source_indices is None:
                    source_indices = [block.get("source_block_index", block.get("block_index", -1))]
                source_indices = [int(index) for index in source_indices]
                if not source_indices or any(index < 0 or index >= len(actual_tokens) for index in source_indices):
                    errors.append(f"{relative}: verified original-ROM block maps to absent source block(s) {source_indices}")
                    continue
                covered_source_blocks.update(source_indices)
                expected = normalize_source_tokens(block.get("tokens", []))
                actual = tuple(token for index in source_indices for token in actual_tokens[index])
                if expected != actual:
                    errors.append(
                        f"{relative}: original-ROM control tokens differ in contiguous dialogtxt block(s) {source_indices}: "
                        f"expected {expected!r}, found {actual!r}"
                    )
        unaligned_source_blocks = [block for block in record.get("dialog_blocks", []) if not block.get("verified", False)]
        if unaligned_source_blocks:
            source_indices = [int(block.get("block_index", -1)) for block in unaligned_source_blocks]
            note_unverified(
                relative,
                f"{len(unaligned_source_blocks)} unaligned original dialogue block(s) indices={source_indices}",
            )
        unmatched_current_blocks = set(range(len(actual_tokens))) - covered_source_blocks
        if unmatched_current_blocks:
            note_unverified(
                relative,
                f"{len(unmatched_current_blocks)} current dialogue block(s) without original mapping indices={sorted(unmatched_current_blocks)}",
            )
            for index, tokens in unmapped_dialogue_name_blocks(current_lines, covered_source_blocks):
                errors.append(
                    f"{relative}: current dialogue NAME controls lack verified original-source mapping "
                    f"in block {index}: {tokens!r}"
                )
        mapped_runtime_lines: set[int] = set()
        for runtime in record.get("runtime_strings", []):
            expected = normalize_source_tokens(runtime.get("tokens", []))
            if not runtime.get("verified", False) or not runtime.get("source_line"):
                if expected:
                    note_unverified(relative, f"unaligned NAME-bearing runtime string {runtime.get('ordinal')}")
                continue
            source_line = int(runtime["source_line"])
            mapped_runtime_lines.add(source_line)
            if source_line < 1 or source_line > len(current_lines):
                errors.append(f"{relative}: verified runtime-string line {source_line} is absent from current source")
                continue
            actual = current_line_tokens(current_lines[source_line - 1])
            if expected != actual:
                errors.append(
                    f"{relative}: original-ROM control tokens differ in runtime-string ordinal {runtime.get('ordinal')} "
                    f"at line {source_line}: expected {expected!r}, found {actual!r}"
                )
        uncovered_fields: list[int] = []
        for lineno, raw in enumerate(current_lines, 1):
            command = COMMAND.match(strip_comment(raw))
            if not command or command.group(1) not in TEXT_COMMANDS - {"dialogtxt"} or not runtime_quoted_matches(raw):
                continue
            current_runtime_field_count += 1
            if lineno not in mapped_runtime_lines:
                current_runtime_unmapped_count += 1
                if current_line_tokens(raw):
                    current_runtime_unmapped_name_lines.append(f"{relative}:{lineno} {current_line_tokens(raw)!r}")
                    uncovered_fields.append(lineno)
        if uncovered_fields:
            note_unverified(relative, f"current non-dialog runtime fields with NAME controls lack source mapping at lines={uncovered_fields}")
            errors.extend(
                f"{relative}:{lineno}: current runtime NAME controls lack verified original-source mapping: {tokens!r}"
                for lineno, tokens in unmapped_runtime_name_fields(current_lines, mapped_runtime_lines)
            )

    if args.require_source_alignment and alignment_unverified:
        errors.extend(
            f"source alignment inconclusive: {relative}: {', '.join(details)}"
            for relative, details in alignment_unverified.items()
        )
    coverage = (
        f"source dialogue blocks verified={sum(bool(b.get('verified')) for b in source_dialog_blocks)}/{len(source_dialog_blocks)}, "
        f"source runtime strings verified={source_runtime_verified_count}/{len(source_runtime_strings)} "
        f"({source_runtime_unverified_count} unverified; NAME-bearing {source_runtime_name_verified_count}/{len(source_runtime_name_strings)}, "
        f"{source_runtime_name_unverified_count} unverified), "
        f"current non-dialog fields mapped={current_runtime_field_count-current_runtime_unmapped_count}/{current_runtime_field_count}, "
        f"unmapped current NAME-bearing fields={len(current_runtime_unmapped_name_lines)}, "
        f"alignment inconclusive={len(alignment_unverified)} script(s)"
    )
    if errors:
        print(coverage, file=sys.stderr)
        for relative, details in alignment_unverified.items():
            print(f"source alignment inconclusive {relative}: {', '.join(details)}", file=sys.stderr)
        print("\n".join(errors), file=sys.stderr)
        print(f"integrity failed: {len(errors)} findings; Japanese payloads={japanese_hits}", file=sys.stderr)
        return 1
    print(
        f"integrity passed: {len(scoped_scripts)} selected scripts, "
        f"{sum('Day2_scripts' in p.parts for p in scoped_scripts)} Day2 overrides, "
        f"{0 if args.script else len(list((root / 'system_messages').glob('*.txt')))} system message files, "
        f"Japanese payloads={japanese_hits}, functional keyboard rows={len(keyboard_exemptions)}, {coverage}"
    )
    if alignment_unverified:
        for relative, details in alignment_unverified.items():
            print(f"  {relative}: {', '.join(details)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
