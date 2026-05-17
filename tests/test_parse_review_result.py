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

FINDINGS_NOT_A_LIST = """task_id: "test-10"
risk_level: "green"
auto_merge_allowed: true
highest_severity: "none"
findings: "this should be a list, not a scalar string"
summary: "Findings field has the wrong shape."
"""

FINDINGS_EMPTY_LIST = """task_id: "test-empty-findings"
risk_level: "green"
auto_merge_allowed: true
highest_severity: "none"
findings: []
summary: "Empty findings list."
"""

FINDINGS_MISSING_KEY = """task_id: "test-missing-findings"
risk_level: "green"
auto_merge_allowed: true
highest_severity: "none"
summary: "No findings key at all."
"""

FINDINGS_NON_DICT_ENTRY = """task_id: "test-non-dict"
risk_level: "green"
auto_merge_allowed: true
highest_severity: "none"
findings:
  - "this should be a dict"
summary: "Non-dict finding entry."
"""

FINDINGS_MISSING_SEVERITY = """task_id: "test-missing-severity"
risk_level: "green"
auto_merge_allowed: true
highest_severity: "none"
findings:
  - title: "no severity"
    evidence: "..."
summary: "Finding without severity."
"""

FINDINGS_UNKNOWN_SEVERITY = """task_id: "test-unknown-severity"
risk_level: "green"
auto_merge_allowed: true
highest_severity: "none"
findings:
  - severity: "LOW"
    title: "Unknown severity"
summary: "Unknown severity label."
"""

FINDINGS_NON_STRING_SEVERITY = """task_id: "test-non-string-severity"
risk_level: "green"
auto_merge_allowed: true
highest_severity: "none"
findings:
  - severity: 123
    title: "Numeric severity"
summary: "Severity is an integer."
"""

FINDINGS_INFO_ONLY = """task_id: "test-info-only"
risk_level: "green"
auto_merge_allowed: true
highest_severity: "none"
findings:
  - severity: "Info"
    title: "Just informational"
    evidence: "no real bug"
    suggested_fix: "n/a"
summary: "Info-only finding."
"""

FINDINGS_P2_MISSING_REQUIRED = """task_id: "test-p2-missing-required"
risk_level: "green"
auto_merge_allowed: true
highest_severity: "P2"
findings:
  - severity: "P2"
summary: "P2 finding missing title/evidence/suggested_fix."
"""

FINDINGS_P2_EMPTY_TITLE = """task_id: "test-p2-empty-title"
risk_level: "green"
auto_merge_allowed: true
highest_severity: "P2"
findings:
  - severity: "P2"
    title: ""
    evidence: "evidence text"
    suggested_fix: "fix text"
summary: "P2 finding with empty title."
"""

FINDINGS_P2_EMPTY_EVIDENCE = """task_id: "test-p2-empty-evidence"
risk_level: "green"
auto_merge_allowed: true
highest_severity: "P2"
findings:
  - severity: "P2"
    title: "title text"
    evidence: ""
    suggested_fix: "fix text"
summary: "P2 finding with empty evidence."
"""

FINDINGS_P2_EMPTY_SUGGESTED_FIX = """task_id: "test-p2-empty-suggested-fix"
risk_level: "green"
auto_merge_allowed: true
highest_severity: "P2"
findings:
  - severity: "P2"
    title: "title text"
    evidence: "evidence text"
    suggested_fix: ""
summary: "P2 finding with empty suggested_fix."
"""

FINDINGS_P2_EXTRA_KEY = """task_id: "test-p2-extra-key"
risk_level: "green"
auto_merge_allowed: true
highest_severity: "P2"
findings:
  - severity: "P2"
    title: "title text"
    evidence: "evidence text"
    suggested_fix: "fix text"
    extra: "unexpected"
summary: "P2 finding with an extra schema-drift key."
"""

FINDINGS_EXPLICIT_NULL = """task_id: "test-findings-null"
risk_level: "green"
auto_merge_allowed: true
highest_severity: "none"
findings: null
summary: "Explicit null findings."
"""

FINDINGS_BARE_KEY = """task_id: "test-findings-bare"
risk_level: "green"
auto_merge_allowed: true
highest_severity: "none"
findings:
summary: "Bare findings key with no value."
"""

FINDINGS_EMPTY_DICT = """task_id: "test-findings-dict"
risk_level: "green"
auto_merge_allowed: true
highest_severity: "none"
findings: {}
summary: "Findings as empty dict."
"""

P2_GREEN_ALLOWED_TRUE = """task_id: "test-11"
risk_level: "green"
auto_merge_allowed: true
highest_severity: "P2"
findings:
  - severity: "P2"
    title: "Minor style nit"
    evidence: "evidence"
    suggested_fix: "fix"
summary: "P2-only on a green PR."
"""

P2_GREEN_ALLOWED_FALSE = """task_id: "test-12"
risk_level: "green"
auto_merge_allowed: false
highest_severity: "P2"
findings:
  - severity: "P2"
    title: "Minor"
    evidence: "evidence"
    suggested_fix: "fix"
summary: "P2-only on a green PR but reviewer withheld allowed."
"""

P2_YELLOW_ALLOWED_TRUE = """task_id: "test-13"
risk_level: "yellow"
auto_merge_allowed: true
highest_severity: "P2"
findings:
  - severity: "P2"
    title: "Minor"
    evidence: "evidence"
    suggested_fix: "fix"
summary: "P2 on a yellow PR; reviewer-allowed must still be overridden."
"""

P1_GREEN_ALLOWED_TRUE = """task_id: "test-14"
risk_level: "green"
auto_merge_allowed: true
highest_severity: "P1"
findings:
  - severity: "P1"
    title: "Real bug"
    evidence: "evidence"
    suggested_fix: "fix"
summary: "Reviewer self-contradicted: P1 finding with allowed=true."
"""

P0_GREEN_ALLOWED_TRUE = """task_id: "test-15"
risk_level: "green"
auto_merge_allowed: true
highest_severity: "P0"
findings:
  - severity: "P0"
    title: "Critical"
    evidence: "evidence"
    suggested_fix: "fix"
summary: "Reviewer self-contradicted: P0 finding with allowed=true."
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

    def test_invalid_findings_entries_fail_closed(self):
        # A non-dict entry or an unknown severity label is schema drift —
        # the parser must force fail-closed rather than silently ignore it.
        r = parser.parse(FINDINGS_INVALID_ENTRIES)
        self.assertEqual(r["highest_severity"], "P0")
        self.assertFalse(r["auto_merge_allowed"])

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

    def test_findings_not_a_list_fails_closed(self):
        # A scalar `findings` value violates the schema. The parser must not
        # silently coerce it to an empty list; it must fall through to the
        # most-conservative effective severity (P0) and block auto-merge.
        r = parser.parse(FINDINGS_NOT_A_LIST)
        self.assertEqual(r["highest_severity"], "P0")
        self.assertFalse(r["auto_merge_allowed"])

    def test_p2_green_allowed_true_keeps_allowed(self):
        # P2 alone is informational (per risk-policy.md). A green PR with
        # only P2 findings and the reviewer's auto_merge_allowed=true must
        # keep allowed=true.
        r = parser.parse(P2_GREEN_ALLOWED_TRUE)
        self.assertEqual(r["highest_severity"], "P2")
        self.assertTrue(r["auto_merge_allowed"])

    def test_p2_green_allowed_false_stays_false(self):
        # If the reviewer explicitly withholds auto-merge on a green PR
        # despite only P2 findings, the parser must honour that.
        r = parser.parse(P2_GREEN_ALLOWED_FALSE)
        self.assertEqual(r["highest_severity"], "P2")
        self.assertFalse(r["auto_merge_allowed"])

    def test_p2_yellow_overrides_to_false(self):
        # Yellow never auto-merges regardless of severity.
        r = parser.parse(P2_YELLOW_ALLOWED_TRUE)
        self.assertEqual(r["highest_severity"], "P2")
        self.assertFalse(r["auto_merge_allowed"])

    def test_p1_green_overrides_to_false(self):
        r = parser.parse(P1_GREEN_ALLOWED_TRUE)
        self.assertEqual(r["highest_severity"], "P1")
        self.assertFalse(r["auto_merge_allowed"])

    def test_p0_green_overrides_to_false(self):
        r = parser.parse(P0_GREEN_ALLOWED_TRUE)
        self.assertEqual(r["highest_severity"], "P0")
        self.assertFalse(r["auto_merge_allowed"])

    def test_findings_missing_key_uses_top_level(self):
        # Absent `findings` is the same as "no findings"; top-level severity
        # decides and auto_merge stays at the reviewer's reported value.
        r = parser.parse(FINDINGS_MISSING_KEY)
        self.assertEqual(r["highest_severity"], "none")
        self.assertTrue(r["auto_merge_allowed"])

    def test_findings_empty_list_uses_top_level(self):
        # An explicitly empty findings list is also "no findings".
        r = parser.parse(FINDINGS_EMPTY_LIST)
        self.assertEqual(r["highest_severity"], "none")
        self.assertTrue(r["auto_merge_allowed"])

    def test_findings_non_dict_entry_fails_closed(self):
        r = parser.parse(FINDINGS_NON_DICT_ENTRY)
        self.assertEqual(r["highest_severity"], "P0")
        self.assertFalse(r["auto_merge_allowed"])

    def test_findings_missing_severity_fails_closed(self):
        r = parser.parse(FINDINGS_MISSING_SEVERITY)
        self.assertEqual(r["highest_severity"], "P0")
        self.assertFalse(r["auto_merge_allowed"])

    def test_findings_unknown_severity_fails_closed(self):
        r = parser.parse(FINDINGS_UNKNOWN_SEVERITY)
        self.assertEqual(r["highest_severity"], "P0")
        self.assertFalse(r["auto_merge_allowed"])

    def test_findings_non_string_severity_fails_closed(self):
        r = parser.parse(FINDINGS_NON_STRING_SEVERITY)
        self.assertEqual(r["highest_severity"], "P0")
        self.assertFalse(r["auto_merge_allowed"])

    def test_findings_info_only_does_not_block(self):
        # Info is recognised as non-elevating; a green + allowed review with
        # only Info findings must keep allowed=true and severity=none.
        r = parser.parse(FINDINGS_INFO_ONLY)
        self.assertEqual(r["highest_severity"], "none")
        self.assertTrue(r["auto_merge_allowed"])

    def test_findings_p2_missing_required_fields_fail_closed(self):
        # A P2 entry with only `severity` set is a schema violation; it
        # must not be allowed to ride P2's non-blocking semantics.
        r = parser.parse(FINDINGS_P2_MISSING_REQUIRED)
        self.assertEqual(r["highest_severity"], "P0")
        self.assertFalse(r["auto_merge_allowed"])

    def test_findings_p2_empty_title_fails_closed(self):
        r = parser.parse(FINDINGS_P2_EMPTY_TITLE)
        self.assertEqual(r["highest_severity"], "P0")
        self.assertFalse(r["auto_merge_allowed"])

    def test_findings_p2_empty_evidence_fails_closed(self):
        r = parser.parse(FINDINGS_P2_EMPTY_EVIDENCE)
        self.assertEqual(r["highest_severity"], "P0")
        self.assertFalse(r["auto_merge_allowed"])

    def test_findings_p2_empty_suggested_fix_fails_closed(self):
        r = parser.parse(FINDINGS_P2_EMPTY_SUGGESTED_FIX)
        self.assertEqual(r["highest_severity"], "P0")
        self.assertFalse(r["auto_merge_allowed"])

    def test_findings_p2_extra_key_fails_closed(self):
        # Schema drift: an unexpected key beside the canonical four must
        # short-circuit to fail-closed even though severity/required fields
        # are individually fine.
        r = parser.parse(FINDINGS_P2_EXTRA_KEY)
        self.assertEqual(r["highest_severity"], "P0")
        self.assertFalse(r["auto_merge_allowed"])

    def test_findings_explicit_null_fails_closed(self):
        # A present key with explicit YAML `null` is not the same as a
        # missing key; the helper must fail closed.
        r = parser.parse(FINDINGS_EXPLICIT_NULL)
        self.assertEqual(r["highest_severity"], "P0")
        self.assertFalse(r["auto_merge_allowed"])

    def test_findings_bare_key_fails_closed(self):
        # A bare `findings:` (no value) parses to None and must also fail
        # closed, the same as explicit null.
        r = parser.parse(FINDINGS_BARE_KEY)
        self.assertEqual(r["highest_severity"], "P0")
        self.assertFalse(r["auto_merge_allowed"])

    def test_findings_empty_dict_fails_closed(self):
        r = parser.parse(FINDINGS_EMPTY_DICT)
        self.assertEqual(r["highest_severity"], "P0")
        self.assertFalse(r["auto_merge_allowed"])


if __name__ == "__main__":
    unittest.main()
