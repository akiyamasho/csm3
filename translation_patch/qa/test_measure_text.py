#!/usr/bin/env python3
"""Regression tests for the static UI text-fit checker."""
import unittest

from measure_text import runtime_quoted_matches, unescape


class RuntimePayloadTests(unittest.TestCase):
    def test_ignores_semicolon_delimited_source_comment(self):
        raw = 'menutxtp 0x08bc9d00, "Equipment", 8 ; 0x080bacf0="装備"'
        quoted = runtime_quoted_matches(raw)
        self.assertEqual([unescape(match.group(0)) for match in quoted], ["Equipment"])

    def test_keeps_escaped_quotes_in_runtime_payload(self):
        raw = r'dialogtxt "Say, \"strike\" now" ; "元の台詞"'
        quoted = runtime_quoted_matches(raw)
        self.assertEqual([unescape(match.group(0)) for match in quoted], ['Say, "strike" now'])


if __name__ == "__main__":
    unittest.main()
