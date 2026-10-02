#!/usr/bin/env python3
"""Regression tests for the static UI text-fit checker."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from check_translation_integrity import (
    comparison_group_expectations,
    current_line_tokens,
    dialogue_token_blocks,
    normalize_source_tokens,
    protected_non_name_tokens,
    protected_text_tokens,
    unmapped_dialogue_name_blocks,
    unmapped_runtime_name_fields,
)
from measure_text import NAME_GLYPHS, manifest_script_paths, measure, runtime_quoted_matches, unescape


class RuntimePayloadTests(unittest.TestCase):
    def test_ignores_semicolon_delimited_source_comment(self):
        raw = 'menutxtp 0x08bc9d00, "Equipment", 8 ; 0x080bacf0="装備"'
        quoted = runtime_quoted_matches(raw)
        self.assertEqual([unescape(match.group(0)) for match in quoted], ["Equipment"])

    def test_keeps_escaped_quotes_in_runtime_payload(self):
        raw = r'dialogtxt "Say, \"strike\" now" ; "元の台詞"'
        quoted = runtime_quoted_matches(raw)
        self.assertEqual([unescape(match.group(0)) for match in quoted], ['Say, "strike" now'])

    def test_uses_manifest_selected_day2_override_once(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "script" / "Day2_scripts").mkdir(parents=True)
            (root / "script" / "17344cc.txt").write_text("root", encoding="utf-8")
            day2 = root / "script" / "Day2_scripts" / "17344cc.txt"
            day2.write_text("day2", encoding="utf-8")
            (root / "script" / "17344dc.txt").write_text("second", encoding="utf-8")
            manifest = root / "build_scripts.manifest"
            manifest.write_text(
                "script/Day2_scripts/17344cc.txt --pos=17344cc\n"
                "script/17344dc.txt --pos=17344dc\n",
                encoding="utf-8",
            )
            selected = manifest_script_paths(root, manifest, expected_count=2)
            self.assertEqual(selected, [day2.resolve(), (root / "script" / "17344dc.txt").resolve()])

    def test_rejects_duplicate_manifest_address(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "script").mkdir()
            (root / "script" / "17344cc.txt").write_text("script", encoding="utf-8")
            manifest = root / "build_scripts.manifest"
            manifest.write_text(
                "script/17344cc.txt --pos=17344cc\nscript/17344cc.txt --pos=17344CC\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "duplicate manifest address"):
                manifest_script_paths(root, manifest, expected_count=2)

    def test_protected_tokens_survive_dialogue_fit_reflow(self):
        before = ['dialogtxt "[NAME 4] Put down the sword."', 'dialogtxt "[NAME 8] Listen!"']
        after = ['dialogtxt "Put down the sword."', 'dialogtxt "[NAME 4][NAME 8] Listen!"']
        self.assertEqual(protected_text_tokens(before), protected_text_tokens(after))

    def test_protected_token_loss_fails_even_when_quoted_prose_changes(self):
        before = ['dialogtxt "[NAME 4] Put down the sword."']
        after = ['dialogtxt "Put down the sword."']
        self.assertNotEqual(protected_text_tokens(before), protected_text_tokens(after))

    def test_tokens_cannot_move_across_an_opcode_block(self):
        before = ['dialogtxt "[OUT] First block."', "code0309 1", 'dialogtxt "Second block."']
        after = ['dialogtxt "First block."', "code0309 1", 'dialogtxt "[OUT] Second block."']
        self.assertNotEqual(protected_text_tokens(before), protected_text_tokens(after))

    def test_raw_greek_name_control_matches_explicit_name_token(self):
        raw_symbol = ['dialogtxt "Listen, γ."']
        explicit_token = ['dialogtxt "Listen, [NAME 1]."']
        self.assertEqual(protected_text_tokens(raw_symbol), protected_text_tokens(explicit_token))

    def test_duplicate_raw_greek_name_control_is_detected(self):
        correct = ['dialogtxt "[NAME 1] Hello."']
        duplicate = ['dialogtxt "[NAME 1]γ Hello."']
        self.assertNotEqual(protected_text_tokens(correct), protected_text_tokens(duplicate))

    def test_non_name_inline_width_control_is_protected_but_name_is_source_checked(self):
        baseline = ['dialogtxt "[WIDTH 2][NAME 4] Hello [OUT]"']
        width_removed = ['dialogtxt "[NAME 4] Hello [OUT]"']
        name_removed = ['dialogtxt "[WIDTH 2] Hello [OUT]"']
        self.assertNotEqual(protected_non_name_tokens(baseline), protected_non_name_tokens(width_removed))
        self.assertEqual(protected_non_name_tokens(baseline), protected_non_name_tokens(name_removed))

    def test_raw_greek_name_control_is_dynamic_not_a_jis_glyph(self):
        line_widths, static_widths, uncertain, tokens = measure("γ", [8] * 95)
        self.assertEqual(line_widths, [108])
        self.assertEqual(static_widths, [0])
        self.assertEqual(tokens, 1)
        self.assertIn("[NAME 1]", uncertain[0])

    def test_dispatcher_name_controls_cover_all_sixteen_indices(self):
        self.assertEqual(len(NAME_GLYPHS), 16)
        self.assertEqual(NAME_GLYPHS["ρ"], 15)
        line_widths, static_widths, uncertain, tokens = measure("ρ", [8] * 95)
        self.assertEqual((line_widths, static_widths, tokens), ([108], [0], 1))
        self.assertIn("[NAME 15]", uncertain[0])

    def test_original_source_controls_are_compared_per_anchored_dialogue_block(self):
        source_tokens = [("{NAME_1}", "{NAME_1}"), ("{NAME_15}",)]
        current = [
            'dialogtxt "[NAME 1] Player"',
            'dialogtxt "γ name"',
            'goto @Next',
            'dialogtxt "ρ name"',
        ]
        self.assertEqual(
            dialogue_token_blocks(current),
            [normalize_source_tokens(list(tokens)) for tokens in source_tokens],
        )
        self.assertEqual(current_line_tokens('strlen 280, "γ"'), ("[NAME 1]",))

    def test_many_to_many_anchor_groups_compare_aggregated_tokens_once(self):
        source_blocks = [["{NAME_4}"], ["{NAME_4}"], ["{NAME_4}"]]
        current_blocks = [("[NAME 4]",), ("[NAME 4]",), ("[NAME 4]",)]
        source_group = comparison_group_expectations({
            "mapping_kind": "anchored_many_to_many",
            "original_tokens": [token for block in source_blocks for token in block],
        })[0]
        current_group = tuple(token for block in current_blocks for token in block)
        self.assertEqual(source_group, current_group)

    def test_alternative_branch_controls_are_checked_per_original_alternative(self):
        group = {
            "mapping_kind": "alternative_branch",
            "original_alternative_tokens": [["{NAME_1}"], ["{NAME_1}"]],
        }
        self.assertEqual(
            comparison_group_expectations(group),
            [("[NAME 1]",), ("[NAME 1]",)],
        )

    def test_common_prefix_branch_mapping_uses_each_source_path_expectation(self):
        group = {
            "mapping_kind": "alternative_branch_with_common_prefix",
            "original_tokens": [],
            "original_path_block_indices": [[103, 104], [103, 105]],
            "original_alternative_tokens": [["{NAME_1}"], ["{NAME_1}"]],
            "current_tokens": ["{NAME_1}"],
        }
        expected = comparison_group_expectations(group)
        self.assertEqual(expected, [("[NAME 1]",), ("[NAME 1]",)])
        self.assertIn(("[NAME 1]",), expected)

    def test_current_name_controls_without_verified_source_mapping_are_findings(self):
        dialogue = ['dialogtxt "[NAME 4] Hello."']
        runtime = ['menutxt "[NAME 4]"']
        self.assertEqual(unmapped_dialogue_name_blocks(dialogue, set()), [(0, ("[NAME 4]",))])
        self.assertEqual(unmapped_dialogue_name_blocks(dialogue, {0}), [])
        self.assertEqual(unmapped_runtime_name_fields(runtime, set()), [(1, ("[NAME 4]",))])
        self.assertEqual(unmapped_runtime_name_fields(runtime, {1}), [])

    def test_source_hex_labels_anchor_dialogue_blocks(self):
        lines = [
            'dialogtxt "[NAME 1] A"',
            '@start:',
            'dialogtxt "[NAME 2] B"',
            '@Label_1234:',
            'dialogtxt "[NAME 4] C"',
        ]
        self.assertEqual(
            dialogue_token_blocks(lines),
            [("[NAME 1]", "[NAME 2]"), ("[NAME 4]",)],
        )


if __name__ == "__main__":
    unittest.main()
