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

    def test_strict_green_without_allowed_file_patterns_invalid(self):
        base = (FIXTURES / "valid-green.yaml").read_text(encoding="utf-8")
        broken = base.replace(
            'allowed_file_patterns:\n  - "README.md"\n',
            "",
        )
        path = _tmpfile(broken)
        try:
            result = validator.validate(path, strict=True)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("allowed_file_patterns" in e for e in result["errors"]),
                msg=result["errors"],
            )
        finally:
            path.unlink()

    def test_default_green_without_allowed_file_patterns_warns(self):
        base = (FIXTURES / "valid-green.yaml").read_text(encoding="utf-8")
        broken = base.replace(
            'allowed_file_patterns:\n  - "README.md"\n',
            "",
        )
        path = _tmpfile(broken)
        try:
            result = validator.validate(path)  # default: not strict
            self.assertTrue(result["ok"], msg=result["errors"])
            self.assertTrue(result["warnings"], msg="expected a warning")
            self.assertIn("warnings", result["summary"])
            self.assertTrue(result["summary"]["warnings"])
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

    def test_red_without_max_iterations_defaults_to_zero(self):
        # A red spec that omits max_iterations is valid; the summary must
        # normalize it to 0 so downstream cannot think a fix budget exists.
        base = (FIXTURES / "valid-red.yaml").read_text(encoding="utf-8")
        stripped = "\n".join(
            line for line in base.splitlines()
            if not line.startswith("max_iterations:")
        )
        path = _tmpfile(stripped)
        try:
            result = validator.validate(path)
            self.assertTrue(result["ok"], msg=result["errors"])
            self.assertEqual(
                result["summary"]["max_iterations"], 0,
                msg="red task with no max_iterations must normalize to 0",
            )
        finally:
            path.unlink()

    def test_invalid_red_with_nonzero_max_iterations(self):
        base = (FIXTURES / "valid-red.yaml").read_text(encoding="utf-8")
        broken = base.replace("max_iterations: 0", "max_iterations: 3")
        path = _tmpfile(broken)
        try:
            result = validator.validate(path)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("max_iterations" in e for e in result["errors"]),
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

    def test_invalid_allowed_file_patterns_dict_item(self):
        base = (FIXTURES / "valid-green.yaml").read_text(encoding="utf-8")
        broken = base.replace(
            'allowed_file_patterns:\n  - "README.md"',
            'allowed_file_patterns:\n  - pattern: "src/**"',
        )
        path = _tmpfile(broken)
        try:
            result = validator.validate(path)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("allowed_file_patterns" in e for e in result["errors"]),
                msg=result["errors"],
            )
        finally:
            path.unlink()

    def test_invalid_allowed_file_patterns_empty_string(self):
        base = (FIXTURES / "valid-green.yaml").read_text(encoding="utf-8")
        broken = base.replace(
            'allowed_file_patterns:\n  - "README.md"',
            'allowed_file_patterns:\n  - ""',
        )
        path = _tmpfile(broken)
        try:
            result = validator.validate(path)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("allowed_file_patterns" in e for e in result["errors"]),
                msg=result["errors"],
            )
        finally:
            path.unlink()

    def test_invalid_allowed_file_patterns_whitespace_only(self):
        base = (FIXTURES / "valid-green.yaml").read_text(encoding="utf-8")
        broken = base.replace(
            'allowed_file_patterns:\n  - "README.md"',
            'allowed_file_patterns:\n  - "   "',
        )
        path = _tmpfile(broken)
        try:
            result = validator.validate(path)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("allowed_file_patterns" in e for e in result["errors"]),
                msg=result["errors"],
            )
        finally:
            path.unlink()

    def test_green_meaningless_pattern_invalid(self):
        base = (FIXTURES / "valid-green.yaml").read_text(encoding="utf-8")
        broken = base.replace(
            'allowed_file_patterns:\n  - "README.md"',
            'allowed_file_patterns:\n  - "**/*"',
        )
        path = _tmpfile(broken)
        try:
            result = validator.validate(path)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("too broad" in e for e in result["errors"]),
                msg=result["errors"],
            )
        finally:
            path.unlink()

    def test_invalid_forbidden_file_patterns_empty_string(self):
        base = (FIXTURES / "valid-green.yaml").read_text(encoding="utf-8")
        broken = base.replace(
            'forbidden_file_patterns:\n  - "src/**"\n  - ".env*"',
            'forbidden_file_patterns:\n  - ""',
        )
        path = _tmpfile(broken)
        try:
            result = validator.validate(path)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("forbidden_file_patterns" in e for e in result["errors"]),
                msg=result["errors"],
            )
        finally:
            path.unlink()

    def test_green_explicit_empty_allowed_file_patterns_invalid(self):
        # An explicitly empty list violates the non-empty-list contract;
        # it must be an error in both default and strict modes, not just
        # the legacy "missing key" warning.
        base = (FIXTURES / "valid-green.yaml").read_text(encoding="utf-8")
        broken = base.replace(
            'allowed_file_patterns:\n  - "README.md"',
            'allowed_file_patterns: []',
        )
        path = _tmpfile(broken)
        try:
            result_default = validator.validate(path)
            self.assertFalse(result_default["ok"])
            self.assertTrue(
                any(
                    "allowed_file_patterns" in e and "non-empty" in e
                    for e in result_default["errors"]
                ),
                msg=result_default["errors"],
            )

            result_strict = validator.validate(path, strict=True)
            self.assertFalse(result_strict["ok"])
        finally:
            path.unlink()

    def test_empty_forbidden_file_patterns_invalid(self):
        base = (FIXTURES / "valid-green.yaml").read_text(encoding="utf-8")
        broken = base.replace(
            'forbidden_file_patterns:\n  - "src/**"\n  - ".env*"',
            'forbidden_file_patterns: []',
        )
        path = _tmpfile(broken)
        try:
            result = validator.validate(path)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any(
                    "forbidden_file_patterns" in e and "non-empty" in e
                    for e in result["errors"]
                ),
                msg=result["errors"],
            )
        finally:
            path.unlink()

    def test_empty_risk_reasoning_invalid(self):
        base = (FIXTURES / "valid-green.yaml").read_text(encoding="utf-8")
        broken = base.replace(
            'risk_reasoning:\n'
            '  - "Documentation-only update with narrow scope."\n'
            '  - "No auth, payment, privacy, dependency, or schema impact."',
            'risk_reasoning: []',
        )
        path = _tmpfile(broken)
        try:
            result = validator.validate(path)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any(
                    "risk_reasoning" in e and "non-empty" in e
                    for e in result["errors"]
                ),
                msg=result["errors"],
            )
        finally:
            path.unlink()

    def test_cli_explicit_empty_pattern_list_exits_nonzero(self):
        # Even in default mode, an explicit empty list is a hard error and
        # the CLI must exit non-zero.
        base = (FIXTURES / "valid-green.yaml").read_text(encoding="utf-8")
        broken = base.replace(
            'allowed_file_patterns:\n  - "README.md"',
            'allowed_file_patterns: []',
        )
        path = _tmpfile(broken)
        try:
            proc = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), str(path)],
                capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("allowed_file_patterns", proc.stderr)
        finally:
            path.unlink()

    def test_invalid_risk_reasoning_non_string(self):
        base = (FIXTURES / "valid-green.yaml").read_text(encoding="utf-8")
        broken = base.replace(
            'risk_reasoning:\n  - "Documentation-only update with narrow scope."',
            'risk_reasoning:\n  - 123',
        )
        path = _tmpfile(broken)
        try:
            result = validator.validate(path)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("risk_reasoning" in e for e in result["errors"]),
                msg=result["errors"],
            )
        finally:
            path.unlink()

    def test_legacy_yellow_without_allowed_file_patterns_valid(self):
        base = (FIXTURES / "valid-yellow.yaml").read_text(encoding="utf-8")
        broken = base.replace(
            'allowed_file_patterns:\n  - "src/components/Settings/**"\n',
            "",
        )
        path = _tmpfile(broken)
        try:
            result = validator.validate(path)
            self.assertTrue(result["ok"], msg=result["errors"])
        finally:
            path.unlink()

    def test_legacy_red_without_allowed_file_patterns_valid(self):
        base = (FIXTURES / "valid-red.yaml").read_text(encoding="utf-8")
        broken = base.replace(
            'allowed_file_patterns:\n  - "docs/auth-refactor-plan.md"\n',
            "",
        )
        path = _tmpfile(broken)
        try:
            result = validator.validate(path)
            self.assertTrue(result["ok"], msg=result["errors"])
        finally:
            path.unlink()

    def test_cli_default_warns_on_missing_pattern(self):
        base = (FIXTURES / "valid-green.yaml").read_text(encoding="utf-8")
        broken = base.replace(
            'allowed_file_patterns:\n  - "README.md"\n',
            "",
        )
        path = _tmpfile(broken)
        try:
            proc = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), str(path)],
                capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            self.assertIn("WARN:", proc.stderr)
            data = json.loads(proc.stdout)
            self.assertIn("warnings", data)
            self.assertTrue(data["warnings"])
        finally:
            path.unlink()

    def test_cli_strict_fails_on_missing_pattern(self):
        base = (FIXTURES / "valid-green.yaml").read_text(encoding="utf-8")
        broken = base.replace(
            'allowed_file_patterns:\n  - "README.md"\n',
            "",
        )
        path = _tmpfile(broken)
        try:
            proc = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "--strict", str(path)],
                capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("allowed_file_patterns", proc.stderr)
        finally:
            path.unlink()

    def test_green_allowed_file_patterns_explicit_null_invalid_default(self):
        # An explicit YAML `null` for an allowlist is schema drift, not
        # "missing": the validator must treat it as a present-but-invalid
        # field and fail in default mode.
        base = (FIXTURES / "valid-green.yaml").read_text(encoding="utf-8")
        broken = base.replace(
            'allowed_file_patterns:\n  - "README.md"',
            'allowed_file_patterns: null',
        )
        path = _tmpfile(broken)
        try:
            result = validator.validate(path)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("allowed_file_patterns" in e for e in result["errors"]),
                msg=result["errors"],
            )
        finally:
            path.unlink()

    def test_green_allowed_file_patterns_explicit_null_invalid_strict(self):
        base = (FIXTURES / "valid-green.yaml").read_text(encoding="utf-8")
        broken = base.replace(
            'allowed_file_patterns:\n  - "README.md"',
            'allowed_file_patterns: null',
        )
        path = _tmpfile(broken)
        try:
            result = validator.validate(path, strict=True)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("allowed_file_patterns" in e for e in result["errors"]),
                msg=result["errors"],
            )
        finally:
            path.unlink()

    def test_green_bare_allowed_file_patterns_invalid(self):
        # A bare `allowed_file_patterns:` with no value also parses to
        # None and must fail in default mode.
        base = (FIXTURES / "valid-green.yaml").read_text(encoding="utf-8")
        broken = base.replace(
            'allowed_file_patterns:\n  - "README.md"',
            'allowed_file_patterns:',
        )
        path = _tmpfile(broken)
        try:
            result = validator.validate(path)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("allowed_file_patterns" in e for e in result["errors"]),
                msg=result["errors"],
            )
        finally:
            path.unlink()

    def test_forbidden_file_patterns_explicit_null_invalid(self):
        base = (FIXTURES / "valid-green.yaml").read_text(encoding="utf-8")
        broken = base.replace(
            'forbidden_file_patterns:\n  - "src/**"\n  - ".env*"',
            'forbidden_file_patterns: null',
        )
        path = _tmpfile(broken)
        try:
            result = validator.validate(path)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("forbidden_file_patterns" in e for e in result["errors"]),
                msg=result["errors"],
            )
        finally:
            path.unlink()

    def test_bare_forbidden_file_patterns_invalid(self):
        base = (FIXTURES / "valid-green.yaml").read_text(encoding="utf-8")
        broken = base.replace(
            'forbidden_file_patterns:\n  - "src/**"\n  - ".env*"',
            'forbidden_file_patterns:',
        )
        path = _tmpfile(broken)
        try:
            result = validator.validate(path)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("forbidden_file_patterns" in e for e in result["errors"]),
                msg=result["errors"],
            )
        finally:
            path.unlink()

    def test_risk_reasoning_explicit_null_invalid(self):
        base = (FIXTURES / "valid-green.yaml").read_text(encoding="utf-8")
        broken = base.replace(
            'risk_reasoning:\n'
            '  - "Documentation-only update with narrow scope."\n'
            '  - "No auth, payment, privacy, dependency, or schema impact."',
            'risk_reasoning: null',
        )
        path = _tmpfile(broken)
        try:
            result = validator.validate(path)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("risk_reasoning" in e for e in result["errors"]),
                msg=result["errors"],
            )
        finally:
            path.unlink()

    def test_bare_risk_reasoning_invalid(self):
        base = (FIXTURES / "valid-green.yaml").read_text(encoding="utf-8")
        broken = base.replace(
            'risk_reasoning:\n'
            '  - "Documentation-only update with narrow scope."\n'
            '  - "No auth, payment, privacy, dependency, or schema impact."',
            'risk_reasoning:',
        )
        path = _tmpfile(broken)
        try:
            result = validator.validate(path)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("risk_reasoning" in e for e in result["errors"]),
                msg=result["errors"],
            )
        finally:
            path.unlink()

    def test_duplicate_risk_level_invalid(self):
        # A spec with a duplicate top-level `risk_level` is malformed; the
        # parser must reject it and the validator must surface a failure.
        base = (FIXTURES / "valid-green.yaml").read_text(encoding="utf-8")
        broken = base.replace(
            'risk_level: "green"',
            'risk_level: "green"\nrisk_level: "red"',
        )
        path = _tmpfile(broken)
        try:
            result = validator.validate(path)
            self.assertFalse(result["ok"])
        finally:
            path.unlink()

    def test_duplicate_merge_policy_invalid(self):
        base = (FIXTURES / "valid-green.yaml").read_text(encoding="utf-8")
        broken = base.replace(
            'merge_policy: "auto_merge_if_green"',
            'merge_policy: "auto_merge_if_green"\nmerge_policy: "draft_only"',
        )
        path = _tmpfile(broken)
        try:
            result = validator.validate(path)
            self.assertFalse(result["ok"])
        finally:
            path.unlink()

    def test_duplicate_allowed_file_patterns_invalid(self):
        base = (FIXTURES / "valid-green.yaml").read_text(encoding="utf-8")
        broken = base.replace(
            'allowed_file_patterns:\n  - "README.md"\n',
            'allowed_file_patterns:\n  - "docs/**"\n'
            'allowed_file_patterns:\n  - "src/**"\n',
        )
        path = _tmpfile(broken)
        try:
            result = validator.validate(path)
            self.assertFalse(result["ok"])
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
