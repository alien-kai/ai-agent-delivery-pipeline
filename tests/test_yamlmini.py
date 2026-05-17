#!/usr/bin/env python3
"""Unit tests for scripts/_yamlmini.py — duplicate-key fail-closed behavior."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "scripts" / "_yamlmini.py"


def _load():
    spec = importlib.util.spec_from_file_location("yamlmini", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


parser = _load()


class DuplicateKeyTests(unittest.TestCase):
    def test_duplicate_top_level_key_raises(self):
        text = "a: 1\na: 2\n"
        with self.assertRaises(ValueError):
            parser.parse_yaml(text)

    def test_duplicate_nested_mapping_key_raises(self):
        text = "outer:\n  a: 1\n  a: 2\n"
        with self.assertRaises(ValueError):
            parser.parse_yaml(text)

    def test_duplicate_key_inline_then_extra_raises(self):
        text = (
            "items:\n"
            "  - severity: P2\n"
            "    severity: Info\n"
            "    title: x\n"
        )
        with self.assertRaises(ValueError):
            parser.parse_yaml(text)

    def test_duplicate_key_in_list_item_extras_only_raises(self):
        text = (
            "items:\n"
            "  - severity: P2\n"
            "    title: x\n"
            "    title: y\n"
        )
        with self.assertRaises(ValueError):
            parser.parse_yaml(text)

    def test_same_key_in_two_separate_list_items_allowed(self):
        # Two different list items may legitimately share the same key.
        text = (
            "items:\n"
            "  - severity: P2\n"
            "    title: a\n"
            "  - severity: P1\n"
            "    title: b\n"
        )
        result = parser.parse_yaml(text)
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["items"][0]["severity"], "P2")
        self.assertEqual(result["items"][1]["severity"], "P1")

    def test_no_duplicates_parses_normally(self):
        text = (
            "task_id: t\n"
            "risk_level: green\n"
            "items:\n"
            "  - a: 1\n"
            "    b: 2\n"
        )
        result = parser.parse_yaml(text)
        self.assertEqual(result["task_id"], "t")
        self.assertEqual(result["risk_level"], "green")
        self.assertEqual(result["items"], [{"a": 1, "b": 2}])


class MalformedSyntaxTests(unittest.TestCase):
    def test_malformed_top_level_line_raises(self):
        # `findings [` is not a valid mapping entry; the parser must
        # raise rather than silently treat `findings` as absent.
        with self.assertRaises(ValueError):
            parser.parse_yaml("a: 1\nfindings [\n")

    def test_bareword_top_level_line_raises(self):
        with self.assertRaises(ValueError):
            parser.parse_yaml("a: 1\nbareword\nb: 2\n")

    def test_malformed_line_in_nested_mapping_raises(self):
        with self.assertRaises(ValueError):
            parser.parse_yaml(
                "outer:\n"
                "  a: 1\n"
                "  bad_no_colon\n"
                "  b: 2\n"
            )

    def test_malformed_inline_list_entry_raises(self):
        # A bareword that doesn't start with `- ` at the list's indent
        # would have been silently dropped by the old skipping logic.
        with self.assertRaises(ValueError):
            parser.parse_yaml(
                "items:\n"
                "  - a\n"
                "  bareword_not_a_dash\n"
            )

    def test_plain_scalar_continuation_is_allowed(self):
        # YAML plain scalars can wrap onto subsequent indented lines.
        # The parser should NOT raise on this legitimate construct.
        text = (
            "assumptions:\n"
            "  - No GitHub issue is filed for this task; source_issue is set to 0\n"
            "    indicate a planner-generated local draft.\n"
            "  - The reader already has the Claude Code CLI installed.\n"
        )
        result = parser.parse_yaml(text)
        self.assertEqual(len(result["assumptions"]), 2)

    def test_block_scalar_still_parses(self):
        # Block scalars (|) must continue to work — they consume indented
        # content explicitly, not via the plain-scalar continuation path.
        text = (
            "objective: |\n"
            "  multi line\n"
            "  body text\n"
            "risk_level: green\n"
        )
        result = parser.parse_yaml(text)
        self.assertEqual(result["risk_level"], "green")
        self.assertIn("multi line", result["objective"])

    def test_indented_list_item_after_scalar_value_raises(self):
        # `findings: []` followed by an indented `- severity: P0` must not
        # be silently treated as plain-scalar continuation. It is schema
        # drift that, if accepted, would hide a P0 finding from the gate.
        text = (
            "findings: []\n"
            "  - severity: P0\n"
            "    title: hidden\n"
        )
        with self.assertRaises(ValueError):
            parser.parse_yaml(text)

    def test_indented_mapping_entry_after_scalar_value_raises(self):
        text = (
            "key: value\n"
            "   nested: x\n"
        )
        with self.assertRaises(ValueError):
            parser.parse_yaml(text)

    def test_plain_text_continuation_with_no_colon_or_dash_allowed(self):
        # Wrapped plain-scalar text without colon or dash should still be
        # accepted so legitimate human-readable specs keep parsing.
        text = (
            "summary: first line of text\n"
            "  continues with more plain words\n"
            "  and yet more words here\n"
            "other_key: x\n"
        )
        result = parser.parse_yaml(text)
        self.assertEqual(result["other_key"], "x")


if __name__ == "__main__":
    unittest.main()
