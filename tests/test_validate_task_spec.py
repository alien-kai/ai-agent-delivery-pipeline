#!/usr/bin/env python3
"""Unit tests for scripts/validate-task-spec.py."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "validate-task-spec.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load_module():
    spec = importlib.util.spec_from_file_location("validate_task_spec", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


validator = _load_module()


def _tmpfile(contents: str) -> Path:
    fd, name = tempfile.mkstemp(suffix=".yaml")
    os.write(fd, contents.encode("utf-8"))
    os.close(fd)
    return Path(name)


class ValidateTaskSpecTests(unittest.TestCase):
    def test_valid_green(self):
        result = validator.validate(FIXTURES / "valid-green.yaml")
        self.assertTrue(result["ok"], msg=result["errors"])
        self.assertEqual(result["summary"]["risk_level"], "green")
        self.assertEqual(result["summary"]["merge_policy"], "auto_merge_if_green")
        self.assertEqual(result["summary"]["max_iterations"], 2)
        self.assertIs(result["summary"]["allow_auto_fix"], True)

    def test_valid_yellow(self):
        result = validator.validate(FIXTURES / "valid-yellow.yaml")
        self.assertTrue(result["ok"], msg=result["errors"])
        self.assertEqual(result["summary"]["risk_level"], "yellow")
        self.assertEqual(result["summary"]["merge_policy"], "require_human")

    def test_valid_red(self):
        result = validator.validate(FIXTURES / "valid-red.yaml")
        self.assertTrue(result["ok"], msg=result["errors"])
        self.assertEqual(result["summary"]["risk_level"], "red")
        self.assertEqual(result["summary"]["merge_policy"], "draft_only")
        self.assertIs(result["summary"]["allow_auto_fix"], False)
        self.assertEqual(result["summary"]["max_iterations"], 0)

    def test_invalid_unknown_risk(self):
        result = validator.validate(FIXTURES / "invalid-unknown-risk.yaml")
        self.assertFalse(result["ok"])
        self.assertTrue(
            any("unknown" in e for e in result["errors"]),
            msg=result["errors"],
        )

    def test_invalid_merge_policy(self):
        base = (FIXTURES / "valid-green.yaml").read_text(encoding="utf-8")
        broken = base.replace(
            'merge_policy: "auto_merge_if_green"',
            'merge_policy: "auto_merge_always"',
        )
        path = _tmpfile(broken)
        try:
            result = validator.validate(path)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("merge_policy" in e for e in result["errors"]),
                msg=result["errors"],
            )
        finally:
            path.unlink()

    def test_invalid_green_without_allowed_file_patterns(self):
        base = (FIXTURES / "valid-green.yaml").read_text(encoding="utf-8")
        broken = base.replace(
            'allowed_file_patterns:\n  - "README.md"\n',
            "",
        )
        path = _tmpfile(broken)
        try:
            result = validator.validate(path)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("green tasks require allowed_file_patterns" in e for e in result["errors"]),
                msg=result["errors"],
            )
        finally:
            path.unlink()

    def test_invalid_red_without_draft_only(self):
        result = validator.validate(FIXTURES / "invalid-red-wrong-merge.yaml")
        self.assertFalse(result["ok"])
        self.assertTrue(
            any("draft_only" in e for e in result["errors"]),
            msg=result["errors"],
        )

    def test_invalid_yellow_with_auto_merge(self):
        base = (FIXTURES / "valid-yellow.yaml").read_text(encoding="utf-8")
        broken = base.replace(
            'merge_policy: "require_human"',
            'merge_policy: "auto_merge_if_green"',
        )
        path = _tmpfile(broken)
        try:
            result = validator.validate(path)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("require_human" in e for e in result["errors"]),
                msg=result["errors"],
            )
        finally:
            path.unlink()

    def test_invalid_red_with_allow_auto_fix(self):
        base = (FIXTURES / "valid-red.yaml").read_text(encoding="utf-8")
        broken = base.replace(
            "allow_auto_fix: false",
            "allow_auto_fix: true",
        )
        path = _tmpfile(broken)
        try:
            result = validator.validate(path)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("allow_auto_fix" in e for e in result["errors"]),
                msg=result["errors"],
            )
        finally:
            path.unlink()

    def test_backwards_compat_optional_fields_missing(self):
        legacy = REPO_ROOT / ".ai" / "tasks" / "local-smoke-001.yaml"
        result = validator.validate(legacy)
        self.assertTrue(result["ok"], msg=result["errors"])
        self.assertEqual(result["summary"]["risk_level"], "green")
        self.assertEqual(
            result["summary"]["max_iterations"], 2,
            msg="max_iterations should fall back to default 2 when absent",
        )
        self.assertIs(
            result["summary"]["allow_auto_fix"], True,
            msg="allow_auto_fix should fall back to True for non-red tasks",
        )

    def test_invalid_max_iterations(self):
        result = validator.validate(FIXTURES / "invalid-max-iterations.yaml")
        self.assertFalse(result["ok"])
        self.assertTrue(
            any("max_iterations" in e for e in result["errors"]),
            msg=result["errors"],
        )

    def test_cli_exit_code_on_success(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(FIXTURES / "valid-green.yaml")],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(data["task_id"], "test-green")

    def test_cli_exit_code_on_failure(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), str(FIXTURES / "invalid-unknown-risk.yaml")],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("unknown", proc.stderr)


if __name__ == "__main__":
    unittest.main()
