#!/usr/bin/env python3
"""Unit tests for scripts/parse-review-result.py."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "parse-review-result.py"


def _load():
    spec = importlib.util.spec_from_file_location("parse_review_result", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


parser = _load()


def _tmpfile(contents: str) -> Path:
    fd, name = tempfile.mkstemp(suffix=".md")
    os.write(fd, contents.encode("utf-8"))
    os.close(fd)
    return Path(name)


CLEAN_GREEN_YAML = """task_id: "test-1"
risk_level: "green"
auto_merge_allowed: true
highest_severity: "none"
findings: []
summary: "Looks good."
"""

CLEAN_GREEN_FENCED = """Some preamble.

```yaml
task_id: "test-1"
risk_level: "green"
auto_merge_allowed: true
highest_severity: "none"
findings: []
summary: "Looks good."
```

Trailing prose.
"""

WITH_P1_FINDING = """task_id: "test-2"
risk_level: "green"
auto_merge_allowed: true
highest_severity: "P1"
findings:
  - severity: "P1"
    title: "Bug"
    evidence: "evidence here"
    suggested_fix: "fix here"
summary: "Has a bug."
"""

YELLOW_CLEAN_BUT_ALLOWED = """task_id: "test-3"
risk_level: "yellow"
auto_merge_allowed: true
highest_severity: "none"
findings: []
summary: "Yellow, clean."
"""

UNKNOWN_RISK = """task_id: "test-4"
risk_level: "unknown"
auto_merge_allowed: true
highest_severity: "none"
findings: []
summary: "Unknown risk."
"""

RED_CLEAN_BUT_ALLOWED = """task_id: "test-5"
risk_level: "red"
auto_merge_allowed: true
highest_severity: "none"
findings: []
summary: "Red."
"""

MALFORMED = """this is not yaml at all
no fields here
"""

TOP_NONE_FINDINGS_P1 = """task_id: "test-7"
risk_level: "green"
auto_merge_allowed: true
highest_severity: "none"
findings:
  - severity: "P1"
    title: "Bug hidden in findings"
    evidence: "Top-level says none but a P1 was filed."
    suggested_fix: "fix it"
summary: "Reviewer self-contradiction."
"""

TOP_P2_FINDINGS_P0 = """task_id: "test-8"
risk_level: "green"
auto_merge_allowed: true
highest_severity: "P2"
findings:
  - severity: "P0"
    title: "Critical"
    evidence: "evidence"
    suggested_fix: "fix"
summary: "P0 hidden under P2 top-level."
"""

FINDINGS_INVALID_ENTRIES = """task_id: "test-9"
risk_level: "green"
auto_merge_allowed: true
highest_severity: "none"
findings:
  - "this is a string, not a dict"
  - severity: "LOW"
    title: "Unknown severity label"
  - severity: "Info"
    title: "Informational only"
summary: "Findings list contains invalid and Info entries."
"""


class ParseReviewTests(unittest.TestCase):
    def test_clean_green(self):
        r = parser.parse(CLEAN_GREEN_YAML)
        self.assertEqual(r["risk_level"], "green")
        self.assertEqual(r["highest_severity"], "none")
        self.assertTrue(r["auto_merge_allowed"])
        self.assertEqual(r["task_id"], "test-1")

    def test_clean_green_with_fence(self):
        r = parser.parse(CLEAN_GREEN_FENCED)
        self.assertEqual(r["risk_level"], "green")
        self.assertEqual(r["highest_severity"], "none")
        self.assertTrue(r["auto_merge_allowed"])

    def test_override_p1_overrides_allowed(self):
        r = parser.parse(WITH_P1_FINDING)
        self.assertFalse(
            r["auto_merge_allowed"],
            "P1 finding must override auto_merge_allowed=true from the reviewer",
        )

    def test_override_yellow_overrides_allowed(self):
        r = parser.parse(YELLOW_CLEAN_BUT_ALLOWED)
        self.assertFalse(
            r["auto_merge_allowed"],
            "yellow risk must override auto_merge_allowed=true",
        )

    def test_override_red_overrides_allowed(self):
        r = parser.parse(RED_CLEAN_BUT_ALLOWED)
        self.assertFalse(r["auto_merge_allowed"])

    def test_unknown_risk_blocks_merge(self):
        r = parser.parse(UNKNOWN_RISK)
        self.assertEqual(r["risk_level"], "unknown")
        self.assertFalse(r["auto_merge_allowed"])

    def test_malformed_blocks_merge(self):
        r = parser.parse(MALFORMED)
        # When required fields are missing, default to the most conservative state.
        self.assertEqual(r["risk_level"], "unknown")
        self.assertFalse(r["auto_merge_allowed"])

    def test_cli_env_output(self):
        path = _tmpfile(CLEAN_GREEN_YAML)
        try:
            proc = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), str(path)],
                capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            self.assertIn("RISK_LEVEL=green", proc.stdout)
            self.assertIn("HIGHEST_SEVERITY=none", proc.stdout)
            self.assertIn("AUTO_MERGE_ALLOWED=true", proc.stdout)
        finally:
            path.unlink()

    def test_cli_overrides_allowed(self):
        path = _tmpfile(WITH_P1_FINDING)
        try:
            proc = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), str(path)],
                capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            self.assertIn("AUTO_MERGE_ALLOWED=false", proc.stdout)
            self.assertIn("HIGHEST_SEVERITY=P1", proc.stdout)
        finally:
            path.unlink()

    def test_findings_p1_elevates_severity(self):
        r = parser.parse(TOP_NONE_FINDINGS_P1)
        self.assertEqual(
            r["highest_severity"], "P1",
            msg="Top-level highest_severity=none must be elevated when findings contains P1",
        )
        self.assertFalse(
            r["auto_merge_allowed"],
            msg="A P1 in findings must force AUTO_MERGE_ALLOWED=false",
        )

    def test_findings_p0_overrides_top_p2(self):
        r = parser.parse(TOP_P2_FINDINGS_P0)
        self.assertEqual(
            r["highest_severity"], "P0",
            msg="A P0 in findings must override a lower top-level highest_severity",
        )
        self.assertFalse(r["auto_merge_allowed"])

    def test_invalid_findings_entries_ignored(self):
        # String entry, unknown severity label ("LOW"), and Info-only entries
        # must not elevate severity and must not crash the parser.
        r = parser.parse(FINDINGS_INVALID_ENTRIES)
        self.assertEqual(r["highest_severity"], "none")
        # No blocking finding, risk=green, top-level allowed=true → still allowed.
        self.assertTrue(r["auto_merge_allowed"])

    def test_findings_p1_elevates_through_cli(self):
        path = _tmpfile(TOP_NONE_FINDINGS_P1)
        try:
            proc = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), str(path)],
                capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            self.assertIn("HIGHEST_SEVERITY=P1", proc.stdout)
            self.assertIn("AUTO_MERGE_ALLOWED=false", proc.stdout)
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
