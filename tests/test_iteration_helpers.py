#!/usr/bin/env python3
"""Unit tests for scripts/get-pr-iteration.py and scripts/get-task-max-iterations.py."""

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
ITER_SCRIPT = REPO_ROOT / "scripts" / "get-pr-iteration.py"
MAX_ITER_SCRIPT = REPO_ROOT / "scripts" / "get-task-max-iterations.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


iter_mod = _load("get_pr_iteration", ITER_SCRIPT)
max_iter_mod = _load("get_task_max_iterations", MAX_ITER_SCRIPT)


def _tmp(contents: str, suffix: str = ".yaml") -> Path:
    fd, name = tempfile.mkstemp(suffix=suffix)
    os.write(fd, contents.encode("utf-8"))
    os.close(fd)
    return Path(name)


class GetPRIterationTests(unittest.TestCase):
    def test_empty_list_returns_zero_no_error(self):
        self.assertEqual(iter_mod.extract_iteration([]), (0, False))

    def test_no_iter_labels_returns_zero_no_error(self):
        labels = [{"name": "ai:review"}, {"name": "risk:green"}]
        self.assertEqual(iter_mod.extract_iteration(labels), (0, False))

    def test_single_iter_label(self):
        labels = [{"name": "ai:iter-1"}, {"name": "ai:review"}]
        self.assertEqual(iter_mod.extract_iteration(labels), (1, False))

    def test_multiple_iter_labels_picks_max(self):
        labels = [{"name": "ai:iter-1"}, {"name": "ai:iter-2"}, {"name": "ai:iter-3"}]
        self.assertEqual(iter_mod.extract_iteration(labels), (3, False))

    def test_gh_object_wrapper(self):
        data = {"labels": [{"name": "ai:iter-2"}]}
        self.assertEqual(iter_mod.extract_iteration(data), (2, False))

    def test_dict_without_labels_key_treated_as_empty(self):
        # gh always emits at least `labels: []`; a dict without that key is
        # unusual but not a parse failure — treat as empty.
        self.assertEqual(iter_mod.extract_iteration({"unrelated": "x"}), (0, False))

    def test_top_level_none_fails_closed(self):
        self.assertEqual(iter_mod.extract_iteration(None), (0, True))

    def test_top_level_int_fails_closed(self):
        self.assertEqual(iter_mod.extract_iteration(42), (0, True))

    def test_top_level_string_fails_closed(self):
        self.assertEqual(iter_mod.extract_iteration("garbage"), (0, True))

    def test_strings_as_label_items_fail_closed(self):
        # gh emits dict items; a list of bare strings is off-spec.
        self.assertEqual(iter_mod.extract_iteration(["ai:iter-5", "x"]), (0, True))

    def test_labels_not_a_list_fails_closed(self):
        self.assertEqual(iter_mod.extract_iteration({"labels": "not a list"}), (0, True))

    def test_label_name_not_a_string_fails_closed(self):
        self.assertEqual(iter_mod.extract_iteration([{"name": 42}]), (0, True))

    def test_label_missing_name_fails_closed(self):
        self.assertEqual(iter_mod.extract_iteration([{"color": "red"}]), (0, True))

    def test_malformed_iter_suffix_fails_closed(self):
        # `ai:iter-x` looks like an iteration label but has a non-numeric suffix.
        self.assertEqual(
            iter_mod.extract_iteration([{"name": "ai:iter-x"}]),
            (0, True),
        )

    def test_cli_via_stdin_emits_both_env_vars(self):
        labels = json.dumps([{"name": "ai:iter-2"}])
        proc = subprocess.run(
            [sys.executable, str(ITER_SCRIPT)],
            input=labels, capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertIn("CURRENT_ITERATION=2", proc.stdout)
        self.assertIn("ITERATION_PARSE_ERROR=false", proc.stdout)

    def test_cli_via_file_emits_both_env_vars(self):
        path = _tmp(json.dumps({"labels": [{"name": "ai:iter-3"}]}), suffix=".json")
        try:
            proc = subprocess.run(
                [sys.executable, str(ITER_SCRIPT), str(path)],
                capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            self.assertIn("CURRENT_ITERATION=3", proc.stdout)
            self.assertIn("ITERATION_PARSE_ERROR=false", proc.stdout)
        finally:
            path.unlink()

    def test_cli_invalid_json_exits_nonzero(self):
        proc = subprocess.run(
            [sys.executable, str(ITER_SCRIPT)],
            input="not json", capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 1, msg=proc.stdout)
        self.assertIn("CURRENT_ITERATION=0", proc.stdout)
        self.assertIn("ITERATION_PARSE_ERROR=true", proc.stdout)

    def test_cli_structural_error_exits_nonzero(self):
        labels = json.dumps({"labels": "not a list"})
        proc = subprocess.run(
            [sys.executable, str(ITER_SCRIPT)],
            input=labels, capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 1, msg=proc.stdout)
        self.assertIn("ITERATION_PARSE_ERROR=true", proc.stdout)

    def test_cli_iter_like_malformed_exits_nonzero(self):
        labels = json.dumps([{"name": "ai:iter-x"}])
        proc = subprocess.run(
            [sys.executable, str(ITER_SCRIPT)],
            input=labels, capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 1, msg=proc.stdout)
        self.assertIn("ITERATION_PARSE_ERROR=true", proc.stdout)


class GetTaskMaxIterationsTests(unittest.TestCase):
    def test_missing_defaults_to_two(self):
        text = (FIXTURES / "valid-green.yaml").read_text(encoding="utf-8")
        stripped = "\n".join(
            line for line in text.splitlines() if not line.startswith("max_iterations:")
        )
        result = max_iter_mod.extract(stripped)
        self.assertEqual(result["max_iterations"], 2)
        self.assertTrue(result["allow_auto_fix"])

    def test_explicit_value_used(self):
        result = max_iter_mod.extract("max_iterations: 4\nrisk_level: green\n")
        self.assertEqual(result["max_iterations"], 4)

    def test_zero_is_valid(self):
        result = max_iter_mod.extract("max_iterations: 0\nrisk_level: red\n")
        self.assertEqual(result["max_iterations"], 0)

    def test_out_of_range_returns_error(self):
        result = max_iter_mod.extract("max_iterations: 99\nrisk_level: green\n")
        self.assertIsNone(result["max_iterations"])
        self.assertTrue(result["errors"])

    def test_negative_is_rejected(self):
        result = max_iter_mod.extract("max_iterations: -1\nrisk_level: green\n")
        self.assertIsNone(result["max_iterations"])

    def test_red_defaults_allow_auto_fix_false(self):
        result = max_iter_mod.extract("risk_level: red\nmerge_policy: draft_only\n")
        self.assertFalse(result["allow_auto_fix"])

    def test_non_red_defaults_allow_auto_fix_true(self):
        result = max_iter_mod.extract("risk_level: green\n")
        self.assertTrue(result["allow_auto_fix"])

    def test_explicit_allow_auto_fix_false(self):
        result = max_iter_mod.extract("risk_level: green\nallow_auto_fix: false\n")
        self.assertFalse(result["allow_auto_fix"])

    def test_cli_valid(self):
        proc = subprocess.run(
            [sys.executable, str(MAX_ITER_SCRIPT), str(FIXTURES / "valid-green.yaml")],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertIn("MAX_ITERATIONS=2", proc.stdout)
        self.assertIn("ALLOW_AUTO_FIX=true", proc.stdout)

    def test_cli_red(self):
        proc = subprocess.run(
            [sys.executable, str(MAX_ITER_SCRIPT), str(FIXTURES / "valid-red.yaml")],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertIn("MAX_ITERATIONS=0", proc.stdout)
        self.assertIn("ALLOW_AUTO_FIX=false", proc.stdout)

    def test_cli_out_of_range_fails(self):
        path = _tmp("max_iterations: 99\nrisk_level: green\n")
        try:
            proc = subprocess.run(
                [sys.executable, str(MAX_ITER_SCRIPT), str(path)],
                capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("max_iterations", proc.stderr)
        finally:
            path.unlink()

    def test_red_missing_max_iterations_normalized_to_zero(self):
        result = max_iter_mod.extract("risk_level: red\nmerge_policy: draft_only\n")
        self.assertEqual(result["max_iterations"], 0)
        self.assertFalse(result["allow_auto_fix"])
        self.assertFalse(result["errors"])

    def test_red_nonzero_max_iterations_rejected(self):
        result = max_iter_mod.extract(
            "risk_level: red\nmerge_policy: draft_only\nmax_iterations: 3\n"
        )
        self.assertIsNone(result["max_iterations"])
        self.assertTrue(result["errors"])
        self.assertTrue(any("max_iterations" in e for e in result["errors"]))
        # Fail-closed: helper must not assert a usable budget.
        self.assertFalse(result["allow_auto_fix"])

    def test_red_allow_auto_fix_true_rejected(self):
        result = max_iter_mod.extract(
            "risk_level: red\nmerge_policy: draft_only\nallow_auto_fix: true\n"
        )
        self.assertTrue(result["errors"])
        self.assertTrue(any("allow_auto_fix" in e for e in result["errors"]))
        self.assertFalse(result["allow_auto_fix"])
        self.assertIsNone(result["max_iterations"])

    def test_yellow_defaults_to_two(self):
        result = max_iter_mod.extract("risk_level: yellow\n")
        self.assertEqual(result["max_iterations"], 2)
        self.assertTrue(result["allow_auto_fix"])
        self.assertFalse(result["errors"])

    def test_missing_risk_level_fails_closed(self):
        result = max_iter_mod.extract("max_iterations: 2\n")
        self.assertIsNone(result["max_iterations"])
        self.assertFalse(result["allow_auto_fix"])
        self.assertTrue(result["errors"])

    def test_unknown_risk_level_fails_closed(self):
        result = max_iter_mod.extract(
            "risk_level: unknown\nmax_iterations: 2\n"
        )
        self.assertIsNone(result["max_iterations"])
        self.assertFalse(result["allow_auto_fix"])
        self.assertTrue(result["errors"])

    def test_cli_red_nonzero_exits_nonzero(self):
        path = _tmp(
            "risk_level: red\nmerge_policy: draft_only\nmax_iterations: 3\n"
        )
        try:
            proc = subprocess.run(
                [sys.executable, str(MAX_ITER_SCRIPT), str(path)],
                capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("max_iterations", proc.stderr)
        finally:
            path.unlink()

    def test_cli_red_allow_auto_fix_true_exits_nonzero(self):
        path = _tmp(
            "risk_level: red\nmerge_policy: draft_only\nallow_auto_fix: true\n"
        )
        try:
            proc = subprocess.run(
                [sys.executable, str(MAX_ITER_SCRIPT), str(path)],
                capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("allow_auto_fix", proc.stderr)
        finally:
            path.unlink()

    def test_cli_missing_risk_exits_nonzero(self):
        path = _tmp("max_iterations: 2\n")
        try:
            proc = subprocess.run(
                [sys.executable, str(MAX_ITER_SCRIPT), str(path)],
                capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("risk_level", proc.stderr)
        finally:
            path.unlink()

    def test_cli_unknown_risk_exits_nonzero(self):
        path = _tmp("risk_level: unknown\nmax_iterations: 2\n")
        try:
            proc = subprocess.run(
                [sys.executable, str(MAX_ITER_SCRIPT), str(path)],
                capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("risk_level", proc.stderr)
        finally:
            path.unlink()

    def test_duplicate_risk_level_fails_closed(self):
        # A duplicate `risk_level` key is schema drift — the parser raises,
        # the helper's try/except catches it, and the resulting spec={}
        # falls through to the missing-risk-level fail-closed branch.
        text = (
            "risk_level: red\n"
            "risk_level: green\n"
            "allow_auto_fix: true\n"
            "max_iterations: 2\n"
        )
        result = max_iter_mod.extract(text)
        self.assertIsNone(result["max_iterations"])
        self.assertTrue(result["errors"])
        self.assertFalse(result["allow_auto_fix"])

    def test_duplicate_max_iterations_fails_closed(self):
        text = (
            "risk_level: green\n"
            "max_iterations: 0\n"
            "max_iterations: 2\n"
        )
        result = max_iter_mod.extract(text)
        self.assertIsNone(result["max_iterations"])
        self.assertTrue(result["errors"])

    def test_duplicate_allow_auto_fix_fails_closed(self):
        text = (
            "risk_level: green\n"
            "allow_auto_fix: false\n"
            "allow_auto_fix: true\n"
        )
        result = max_iter_mod.extract(text)
        self.assertTrue(result["errors"])
        self.assertFalse(result["allow_auto_fix"])

    def test_cli_duplicate_risk_level_exits_nonzero(self):
        path = _tmp(
            "risk_level: red\n"
            "risk_level: green\n"
            "allow_auto_fix: true\n"
            "max_iterations: 2\n"
        )
        try:
            proc = subprocess.run(
                [sys.executable, str(MAX_ITER_SCRIPT), str(path)],
                capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 1)
        finally:
            path.unlink()

    def test_green_max_iterations_null_fails_closed(self):
        text = "risk_level: green\nmax_iterations: null\n"
        result = max_iter_mod.extract(text)
        self.assertIsNone(result["max_iterations"])
        self.assertFalse(result["allow_auto_fix"])
        self.assertTrue(
            any("max_iterations" in e for e in result["errors"]),
            msg=result["errors"],
        )

    def test_green_bare_max_iterations_fails_closed(self):
        text = "risk_level: green\nmax_iterations:\n"
        result = max_iter_mod.extract(text)
        self.assertIsNone(result["max_iterations"])
        self.assertTrue(result["errors"])

    def test_green_allow_auto_fix_null_fails_closed(self):
        text = "risk_level: green\nallow_auto_fix: null\n"
        result = max_iter_mod.extract(text)
        self.assertFalse(result["allow_auto_fix"])
        self.assertTrue(
            any("allow_auto_fix" in e for e in result["errors"]),
            msg=result["errors"],
        )

    def test_green_bare_allow_auto_fix_fails_closed(self):
        text = "risk_level: green\nallow_auto_fix:\n"
        result = max_iter_mod.extract(text)
        self.assertFalse(result["allow_auto_fix"])
        self.assertTrue(result["errors"])

    def test_green_missing_max_and_allow_uses_defaults(self):
        # A green spec that omits both fields is still valid and emits
        # the documented defaults.
        text = "risk_level: green\n"
        result = max_iter_mod.extract(text)
        self.assertEqual(result["max_iterations"], 2)
        self.assertTrue(result["allow_auto_fix"])
        self.assertFalse(result["errors"])

    def test_red_missing_max_and_allow_uses_defaults(self):
        text = "risk_level: red\n"
        result = max_iter_mod.extract(text)
        self.assertEqual(result["max_iterations"], 0)
        self.assertFalse(result["allow_auto_fix"])
        self.assertFalse(result["errors"])

    def test_red_max_iterations_null_fails_closed(self):
        text = "risk_level: red\nmax_iterations: null\n"
        result = max_iter_mod.extract(text)
        self.assertIsNone(result["max_iterations"])
        self.assertTrue(result["errors"])

    def test_red_allow_auto_fix_null_fails_closed(self):
        text = "risk_level: red\nallow_auto_fix: null\n"
        result = max_iter_mod.extract(text)
        self.assertFalse(result["allow_auto_fix"])
        self.assertTrue(result["errors"])

    def test_risk_level_null_fails_closed(self):
        # `risk_level: null` is structurally present but parses to None,
        # which is not in VALID_RISK — must fail closed.
        text = "risk_level: null\nmax_iterations: 2\n"
        result = max_iter_mod.extract(text)
        self.assertIsNone(result["max_iterations"])
        self.assertFalse(result["allow_auto_fix"])
        self.assertTrue(result["errors"])

    def test_bare_risk_level_fails_closed(self):
        text = "risk_level:\nmax_iterations: 2\n"
        result = max_iter_mod.extract(text)
        self.assertIsNone(result["max_iterations"])
        self.assertFalse(result["allow_auto_fix"])
        self.assertTrue(result["errors"])

    def test_cli_green_max_iterations_null_exits_nonzero(self):
        path = _tmp("risk_level: green\nmax_iterations: null\n")
        try:
            proc = subprocess.run(
                [sys.executable, str(MAX_ITER_SCRIPT), str(path)],
                capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("max_iterations", proc.stderr)
        finally:
            path.unlink()

    def test_cli_green_allow_auto_fix_null_exits_nonzero(self):
        path = _tmp("risk_level: green\nallow_auto_fix: null\n")
        try:
            proc = subprocess.run(
                [sys.executable, str(MAX_ITER_SCRIPT), str(path)],
                capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("allow_auto_fix", proc.stderr)
        finally:
            path.unlink()

    def test_malformed_max_iterations_syntax_fails_closed(self):
        # A bareword `max_iterations [` is not valid YAML; the helper
        # must catch the parse error and refuse to emit a usable budget.
        text = "risk_level: green\nmax_iterations [\n"
        result = max_iter_mod.extract(text)
        self.assertIsNone(result["max_iterations"])
        self.assertFalse(result["allow_auto_fix"])
        self.assertTrue(result["errors"])

    def test_malformed_risk_level_syntax_fails_closed(self):
        text = "risk_level [\nmax_iterations: 2\n"
        result = max_iter_mod.extract(text)
        self.assertIsNone(result["max_iterations"])
        self.assertFalse(result["allow_auto_fix"])
        self.assertTrue(result["errors"])

    def test_cli_malformed_max_iterations_exits_nonzero(self):
        path = _tmp("risk_level: green\nmax_iterations [\n")
        try:
            proc = subprocess.run(
                [sys.executable, str(MAX_ITER_SCRIPT), str(path)],
                capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 1)
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
