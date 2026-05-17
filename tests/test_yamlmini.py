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


if __name__ == "__main__":
    unittest.main()
