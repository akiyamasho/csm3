#!/usr/bin/env python3
"""Static UI text-fit checker for the Swordcraft 3 translation patch.

The checker mirrors the patched VWF's important sizing rules: printable ASCII
uses AsciiWidths from asm/vwf_font.asm, JIS glyphs are 12 pixels, 0x7f width
controls replace the advance, 0x877x control words do not draw, and 0x83cx
name substitutions are conservatively charged as a nine-glyph name.
It deliberately reports uncertainty instead of pretending dynamic names or
caller-specific boxes are exact.
"""
from __future__ import annotations
import argparse, ast, re
from collections import Counter
from pathlib import Path

QUOTED = re.compile(r'"(?:\\.|[^"\\])*"')
COMMAND = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\b')
ASCII_DB = re.compile(r'^\s*\.db\s+([^;]+)')
TOKENS = re.compile(r'\[([^\]]+)\]')
NAME_GLYPHS = {glyph: index for index, glyph in enumerate("βγδεζηθικλμνξοπρ")}

DRAW_COMMANDS = {
    "dialogtxt": (224, 240, "dialogue line (28-tile safe interior; 30-tile hard screen)"),
    "dialogbig": (224, 240, "large dialogue line (caller box is not encoded in script)"),
    "choicetxt": (160, 192, "choice text (caller-specific; conservative 20-tile safe limit)"),
    "placetxt": (224, 240, "location banner (caller-specific; screen hard limit)"),
    "popuptxt": (224, 240, "popup text (caller-specific; screen hard limit)"),
    "menutxt": (160, 192, "script menu text (caller-specific; conservative 20-tile safe limit)"),
    "menutxtp": (160, 192, "pointer menu text (declared width is checked separately)"),
    "tabletxt": (224, 240, "table text (caller-specific; screen hard limit)"),
}

def load_ascii_widths(path: Path) -> list[int]:
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == "AsciiWidths:") + 1
    result: list[int] = []
    for line in lines[start:]:
        if ".endautoregion" in line:
            break
        m = ASCII_DB.match(line)
        if m:
            # Width rows are scalar .db entries; comments are intentionally
            # ignored so this remains tied to the actual assembled table.
            value = m.group(1).strip().split(",", 1)[0]
            try:
                result.append(int(value, 0))
            except ValueError:
                pass
    if len(result) < 95:
        raise RuntimeError(f"AsciiWidths has only {len(result)} entries")
    return result

def unescape(raw: str) -> str:
    try:
        return ast.literal_eval(raw)
    except (SyntaxError, ValueError):
        return raw[1:-1]

def runtime_quoted_matches(raw: str) -> list[re.Match[str]]:
    """Return quoted fields belonging to the command, excluding `;` comments.

    System-message sources keep the original Japanese text in a semicolon-
    delimited comment, often as another quoted field.  Selecting the final
    quote therefore measures the annotation instead of the translated runtime
    payload.  Find the first semicolon outside a quoted string (with escaped
    quotes honored), then retain only quote matches before that boundary.
    """
    in_quote = False
    escaped = False
    comment_start = len(raw)
    for index, char in enumerate(raw):
        if escaped:
            escaped = False
        elif in_quote and char == "\\":
            escaped = True
        elif char == '"':
            in_quote = not in_quote
        elif char == ";" and not in_quote:
            comment_start = index
            break
    return [match for match in QUOTED.finditer(raw) if match.start() < comment_start]

def manifest_script_paths(root: Path, manifest: Path, expected_count: int = 1052) -> list[Path]:
    """Read exactly the selected runtime scripts, including explicit overrides."""
    result: list[Path] = []
    seen_addresses: set[str] = set()
    for lineno, raw in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        parts = raw.split()
        if len(parts) != 2 or not re.fullmatch(r"--pos=[0-9a-fA-F]+", parts[1]):
            raise ValueError(f"invalid manifest row {manifest}:{lineno}: {raw}")
        address = parts[1][6:].lower()
        if Path(parts[0]).stem.lower() != address:
            raise ValueError(f"manifest filename/address mismatch at {manifest}:{lineno}: {parts[0]} {parts[1]}")
        if address in seen_addresses:
            raise ValueError(f"duplicate manifest address {address} at {manifest}:{lineno}")
        seen_addresses.add(address)
        path = (root / parts[0]).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError(f"missing or out-of-tree manifest source at {manifest}:{lineno}: {parts[0]}")
        if path.suffix.lower() != ".txt":
            raise ValueError(f"manifest source is not a .txt file at {manifest}:{lineno}: {parts[0]}")
        result.append(path)
    if len(result) != expected_count:
        raise ValueError(f"manifest selects {len(result)} scripts; expected {expected_count}")
    return result

def measure(text: str, widths: list[int]) -> tuple[list[int], list[int], list[str], int]:
    """Return worst-case and definitely-static physical line widths."""
    line_widths = [0]
    static_widths = [0]
    uncertain: list[str] = []
    token_count = 0
    fixed_width: int | None = None

    def add_char(ch: str) -> None:
        nonlocal token_count
        if ch == "\n":
            line_widths.append(0)
            static_widths.append(0)
            return
        if ch == "\t":
            line_widths[-1] += 4
            static_widths[-1] += 4
            return
        if ch in NAME_GLYPHS:
            token_count += 1
            name_advance = 9 * (fixed_width if fixed_width is not None else 12)
            uncertain.append(f"{ch} [NAME {NAME_GLYPHS[ch]}] runtime substitution (charged at {name_advance}px worst case)")
            line_widths[-1] += name_advance
            return
        if ord(ch) < 128:
            advance = widths[ord(ch) - 32] if 32 <= ord(ch) <= 126 else 0
        else:
            advance = 12
        if advance:
            if fixed_width is not None:
                advance = fixed_width
            line_widths[-1] += advance
            static_widths[-1] += advance

    def add_segment(segment: str) -> None:
        for ch in segment:
            add_char(ch)
    # Source strings use symbolic [NAME n] tokens. Treat each as worst-case
    # nine fixed/JIS glyphs: the runtime name buffer is nine halfwords.
    pos = 0
    for token in TOKENS.finditer(text):
        segment = text[pos:token.start()]
        add_segment(segment)
        token_name = token.group(1).strip()
        width_match = re.fullmatch(r"WIDTH(?:=|\s+)(\d+)", token_name, re.IGNORECASE)
        if width_match:
            fixed_width = int(width_match.group(1))
        elif token_name.upper() == "WIDTH RESET":
            fixed_width = None
        else:
            token_count += 1
            name_advance = 9 * (fixed_width if fixed_width is not None else 12)
            uncertain.append(f"[{token_name}] dynamic token (charged at {name_advance}px worst case)")
            line_widths[-1] += name_advance
        pos = token.end()
    add_segment(text[pos:])
    return line_widths, static_widths, uncertain, token_count

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--manifest", type=Path, help="selected script manifest (default: <root>/build_scripts.manifest)")
    ap.add_argument("--report", type=Path)
    ap.add_argument("--tsv", type=Path, help="write complete machine-readable findings TSV")
    ap.add_argument("--fail-on-static-overflow", action="store_true",
                    help="return failure if any fixed text exceeds its safe width")
    args = ap.parse_args()
    root = args.root.resolve()
    widths = load_ascii_widths(root / "asm" / "vwf_font.asm")
    findings: list[dict] = []
    checked = 0
    dynamic = 0
    manifest = args.manifest or (root / "build_scripts.manifest")
    script_paths = manifest_script_paths(root, manifest.resolve())
    source_paths = script_paths + sorted((root / "system_messages").glob("*.txt"))
    selected_day2 = sum("Day2_scripts" in path.parts for path in script_paths)
    for path in source_paths:
        for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            cm = COMMAND.match(raw)
            if not cm or cm.group(1) not in DRAW_COMMANDS:
                continue
            command = cm.group(1)
            all_quoted = list(QUOTED.finditer(raw))
            quoted = runtime_quoted_matches(raw)
            if not quoted:
                continue
            # Annotation quotes after an unquoted semicolon are excluded
            # above. For ordinary script lines retain the historical
            # final-quote behavior, including legacy lines containing
            # unescaped inner quotes; annotated system rows have one
            # runtime field, so select its first pre-comment quote.
            payload_quote = quoted[0] if len(quoted) < len(all_quoted) else quoted[-1]
            text = unescape(payload_quote.group(0))
            line_widths, static_widths, uncertain, token_count = measure(text, widths)
            checked += 1
            dynamic += token_count
            safe, hard, rule = DRAW_COMMANDS[command]
            # menutxtp's final numeric argument is a width in pixels/8.
            declared = None
            if command == "menutxtp":
                tail = raw[payload_quote.end():].split(";", 1)[0]
                nums = re.findall(r"\b\d+\b", tail)
                if nums:
                    declared = int(nums[-1]) * 8
                    safe = declared
                    hard = declared
                    rule = f"declared menu width ({declared}px)"
            peak = max(line_widths, default=0)
            static_peak = max(static_widths, default=0)
            kind = ""
            if static_peak > hard:
                kind = "HARD_OVERFLOW"
            elif static_peak > safe:
                kind = "SAFE_OVERFLOW"
            elif uncertain and peak > hard:
                kind = "DYNAMIC_OVERFLOW"
            elif uncertain:
                kind = "DYNAMIC_REVIEW"
            if kind:
                findings.append({"file": str(path.relative_to(root)), "line": lineno,
                                 "command": command, "width": peak, "safe": safe,
                                 "hard": hard, "static_width": static_peak,
                                 "kind": kind, "text": text,
                                 "uncertainty": uncertain, "rule": rule,
                                 "declared_width": declared})
    findings.sort(key=lambda x: (-x["width"], x["file"], x["line"]))
    counts = Counter(f["kind"] for f in findings)
    out = args.report or (root / "qa" / "ui_overflow_report.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fp:
        fp.write("# UI text-fit report\n\n")
        fp.write(f"Generated by `qa/measure_text.py`; manifest-selected runtime scripts include {selected_day2} Day 2 overrides.\n\n")
        fp.write("Semantic coverage note: static integrity and width checks do not establish scene-level correctness. Dynamic NAME expansion and caller-specific UI placement still require emulator review.\n\n")
        fp.write(f"- Commands checked: **{checked}**\n- Findings: **{len(findings)}**\n")
        fp.write(f"- Hard overflows: **{counts['HARD_OVERFLOW']}**\n- Safe-margin overflows: **{counts['SAFE_OVERFLOW']}**\n")
        fp.write(f"- Dynamic worst-case overflows: **{counts['DYNAMIC_OVERFLOW']}**\n- Dynamic-token reviews: **{counts['DYNAMIC_REVIEW']}**\n- Dynamic tokens charged: **{dynamic}**\n\n")
        fp.write("## Model and limits\n\n")
        fp.write("ASCII advances are parsed from `asm/vwf_font.asm` (`AsciiWidths`); ordinary JIS advances are 12px, matching `LookupGlyph`. Raw Greek beta through rho map in the runtime renderer to NAME0 through NAME15, so both those symbols and explicit `[NAME n]` tokens are reported as dynamic substitutions and charged at the conservative nine-glyph bound. WIDTH controls use the fixed advance they set. Safe dialogue width is 224px (28 tiles), with 240px as the screen hard ceiling. Menu/choice callers vary, so 160px is a conservative review threshold unless `menutxtp` declares a narrower width. The VWF renderer has no automatic word wrapping: each quoted command payload is one physical line, so source line/page breaks are the wrap mechanism. `HARD_OVERFLOW` is proven from non-dynamic glyphs alone; `DYNAMIC_OVERFLOW` exceeds the hard limit only under the conservative nine-glyph name bound. Emulator screenshots remain required for caller-specific placement and dynamic names.\n\n")
        by_command = Counter(f["command"] for f in findings)
        by_file = Counter(f["file"] for f in findings)
        fp.write("## Aggregate counts\n\n| Command | Findings |\n|---|---:|\n")
        for command, count in sorted(by_command.items(), key=lambda item: (-item[1], item[0])):
            fp.write(f"| `{command}` | {count} |\n")
        fp.write("\n| File (top 30) | Findings |\n|---|---:|\n")
        for filename, count in by_file.most_common(30):
            fp.write(f"| `{filename}` | {count} |\n")
        fp.write("\n## Practical repair manifest\n\nRepair `HARD_OVERFLOW` entries first, preserving command and existing page/line boundaries; then `SAFE_OVERFLOW`; then `DYNAMIC_OVERFLOW` after checking actual `setname` values and player-name lengths. Review `DYNAMIC_REVIEW` entries in an emulator. The first 50 actionable entries follow.\n\n| Priority | File:line | Command | Static px | Worst px |\n|---|---|---|---:|---:|\n")
        actionable = [f for f in findings if f["kind"] != "DYNAMIC_REVIEW"]
        for f in actionable[:50]:
            fp.write(f"| {f['kind']} | `{f['file']}:{f['line']}` | `{f['command']}` | {f['static_width']} | {f['width']} |\n")
        fp.write("\n## Findings (largest first)\n\n")
        fp.write("| Kind | File:line | Command | Static | Worst | Limit | Text |\n|---|---|---:|---:|---:|---:|---|\n")
        for f in findings:
            text = f["text"].replace("|", "\\|")
            fp.write(f"| {f['kind']} | `{f['file']}:{f['line']}` | `{f['command']}` | {f['static_width']}px | {f['width']}px | {f['safe']}/{f['hard']}px | {text} |\n")
    if args.tsv:
        with args.tsv.open("w", encoding="utf-8") as fp:
            fp.write("kind\tfile\tline\tcommand\tstatic_px\tworst_px\tlimit\ttext\n")
            for f in findings:
                # Keep one finding per physical TSV row even if a source text
                # ever contains escaped control/newline characters.
                safe_text = f["text"].replace("\\", "\\\\").replace("\t", "\\t").replace("\r", "\\r").replace("\n", "\\n")
                fp.write(f"{f['kind']}\t{f['file']}\t{f['line']}\t{f['command']}\t{f['static_width']}\t{f['width']}\t{f['safe']}/{f['hard']}\t{safe_text}\n")
    print(f"checked={checked} findings={len(findings)} hard={counts['HARD_OVERFLOW']} safe={counts['SAFE_OVERFLOW']} dynamic_overflow={counts['DYNAMIC_OVERFLOW']} dynamic_review={counts['DYNAMIC_REVIEW']}")
    print(f"report={out}")
    if args.fail_on_static_overflow and (counts["HARD_OVERFLOW"] or counts["SAFE_OVERFLOW"]):
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
