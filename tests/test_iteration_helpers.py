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
    def test_no_labels_returns_zero(self):
        self.assertEqual(iter_mod.extract_iteration([]), 0)

    def test_no_iter_labels_returns_zero(self):
        labels = [{"name": "ai:review"}, {"name": "risk:green"}]
        self.assertEqual(iter_mod.extract_iteration(labels), 0)

    def test_single_iter_label(self):
        labels = [{"name": "ai:iter-1"}, {"name": "ai:review"}]
        self.assertEqual(iter_mod.extract_iteration(labels), 1)

    def test_multiple_iter_labels_picks_max(self):
        labels = [{"name": "ai:iter-1"}, {"name": "ai:iter-2"}, {"name": "ai:iter-3"}]
        self.assertEqual(iter_mod.extract_iteration(labels), 3)

    def test_gh_object_wrapper(self):
        data = {"labels": [{"name": "ai:iter-2"}]}
        self.assertEqual(iter_mod.extract_iteration(data), 2)

    def test_array_of_strings(self):
        self.assertEqual(iter_mod.extract_iteration(["ai:iter-5", "x"]), 5)

    def test_malformed_does_not_crash(self):
        self.assertEqual(iter_mod.extract_iteration(None), 0)
        self.assertEqual(iter_mod.extract_iteration(42), 0)
        self.assertEqual(iter_mod.extract_iteration("garbage"), 0)
        self.assertEqual(iter_mod.extract_iteration({"unrelated": "x"}), 0)

    def test_cli_via_stdin(self):
        labels = json.dumps([{"name": "ai:iter-2"}])
        proc = subprocess.run(
            [sys.executable, str(ITER_SCRIPT)],
            input=labels, capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertIn("CURRENT_ITERATION=2", proc.stdout)

    def test_cli_via_file(self):
        path = _tmp(json.dumps({"labels": [{"name": "ai:iter-3"}]}), suffix=".json")
        try:
            proc = subprocess.run(
                [sys.executable, str(ITER_SCRIPT), str(path)],
                capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            self.assertIn("CURRENT_ITERATION=3", proc.stdout)
        finally:
            path.unlink()

    def test_cli_malformed_json_does_not_crash(self):
        proc = subprocess.run(
            [sys.executable, str(ITER_SCRIPT)],
            input="not json", capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertIn("CURRENT_ITERATION=0", proc.stdout)


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
        self.assertIsNotNone(result["max_iterations_error"])

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


if __name__ == "__main__":
    unittest.main()
