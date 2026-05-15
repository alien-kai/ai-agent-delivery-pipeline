#!/usr/bin/env python3
"""Unit tests for scripts/decide-review-gate.py."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "decide-review-gate.py"


def _load():
    spec = importlib.util.spec_from_file_location("decide_review_gate", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


gate = _load()


class DecideTests(unittest.TestCase):
    def test_clean_green_auto_merge(self):
        r = gate.decide("green", "none", True, 0, 2, True)
        self.assertEqual(r["NEXT_ACTION"], "auto_merge")
        self.assertEqual(r["SHOULD_FIX"], "false")
        self.assertEqual(r["SHOULD_STOP"], "false")
        self.assertEqual(r["AUTO_MERGE_ALLOWED"], "true")
        self.assertEqual(r["HUMAN_REQUIRED_REASON"], "")

    def test_p1_within_budget_needs_fix(self):
        r = gate.decide("green", "P1", False, 0, 2, True)
        self.assertEqual(r["NEXT_ACTION"], "needs_fix")
        self.assertEqual(r["SHOULD_FIX"], "true")
        self.assertEqual(r["NEXT_ITERATION"], "1")

    def test_p1_at_budget_max_iterations_reached(self):
        r = gate.decide("green", "P1", False, 2, 2, True)
        self.assertEqual(r["NEXT_ACTION"], "max_iterations_reached")
        self.assertEqual(r["SHOULD_FIX"], "false")
        self.assertEqual(r["SHOULD_STOP"], "true")

    def test_p1_above_budget_max_iterations_reached(self):
        r = gate.decide("green", "P1", False, 3, 2, True)
        self.assertEqual(r["NEXT_ACTION"], "max_iterations_reached")

    def test_p0_human_required(self):
        r = gate.decide("green", "P0", False, 0, 2, True)
        self.assertEqual(r["NEXT_ACTION"], "human_required")
        self.assertEqual(r["HUMAN_REQUIRED_REASON"], "p0_finding")

    def test_yellow_clean_human_required(self):
        r = gate.decide("yellow", "none", False, 0, 3, True)
        self.assertEqual(r["NEXT_ACTION"], "human_required")
        self.assertEqual(r["HUMAN_REQUIRED_REASON"], "yellow_human_merge")

    def test_red_human_required(self):
        r = gate.decide("red", "P1", False, 0, 0, False)
        self.assertEqual(r["NEXT_ACTION"], "human_required")
        self.assertEqual(r["HUMAN_REQUIRED_REASON"], "red_risk")

    def test_unknown_human_required(self):
        r = gate.decide("unknown", "P1", False, 0, 2, True)
        self.assertEqual(r["NEXT_ACTION"], "human_required")
        self.assertEqual(r["HUMAN_REQUIRED_REASON"], "unknown_risk")

    def test_allow_auto_fix_false_human_required(self):
        r = gate.decide("green", "P1", False, 0, 2, False)
        self.assertEqual(r["NEXT_ACTION"], "human_required")
        self.assertEqual(r["HUMAN_REQUIRED_REASON"], "auto_fix_disabled")

    def test_yellow_p1_needs_fix(self):
        r = gate.decide("yellow", "P1", False, 0, 3, True)
        self.assertEqual(r["NEXT_ACTION"], "needs_fix")
        self.assertEqual(r["NEXT_ITERATION"], "1")

    def test_p2_green_allowed_true_auto_merges(self):
        r = gate.decide("green", "P2", True, 0, 2, True)
        self.assertEqual(r["NEXT_ACTION"], "auto_merge")
        self.assertEqual(r["AUTO_MERGE_ALLOWED"], "true")
        self.assertEqual(r["SHOULD_FIX"], "false")

    def test_p2_green_allowed_false_human_required(self):
        r = gate.decide("green", "P2", False, 0, 2, True)
        self.assertEqual(r["NEXT_ACTION"], "human_required")
        self.assertEqual(r["HUMAN_REQUIRED_REASON"], "p2_finding")
        self.assertEqual(r["SHOULD_FIX"], "false")

    def test_p2_yellow_human_required(self):
        r = gate.decide("yellow", "P2", True, 0, 2, True)
        self.assertEqual(r["NEXT_ACTION"], "human_required")
        self.assertEqual(r["SHOULD_FIX"], "false")

    def test_p2_red_human_required(self):
        r = gate.decide("red", "P2", True, 0, 2, True)
        self.assertEqual(r["NEXT_ACTION"], "human_required")
        self.assertEqual(r["SHOULD_FIX"], "false")

    def test_p2_unknown_human_required(self):
        r = gate.decide("unknown", "P2", True, 0, 2, True)
        self.assertEqual(r["NEXT_ACTION"], "human_required")
        self.assertEqual(r["SHOULD_FIX"], "false")

    def test_p2_never_returns_needs_fix(self):
        # Parametric: P2 must not enter the fix loop under any combination
        # of risk / allowed / iteration budget.
        combos = [
            ("green", True), ("green", False),
            ("yellow", True), ("yellow", False),
            ("red", True), ("red", False),
            ("unknown", True), ("unknown", False),
        ]
        budgets = [(0, 2), (1, 2), (2, 2), (5, 2)]
        for risk, allowed in combos:
            for iteration, max_iter in budgets:
                with self.subTest(risk=risk, allowed=allowed,
                                  iteration=iteration, max_iter=max_iter):
                    r = gate.decide(risk, "P2", allowed, iteration, max_iter, True)
                    self.assertNotEqual(
                        r["NEXT_ACTION"], "needs_fix",
                        msg="P2 must never enter the fix loop",
                    )
                    self.assertEqual(r["SHOULD_FIX"], "false")

    def test_p0_green_allowed_true_still_human_required(self):
        # Even if reviewer self-reported allowed=true, a P0 must escalate.
        r = gate.decide("green", "P0", True, 0, 2, True)
        self.assertEqual(r["NEXT_ACTION"], "human_required")
        self.assertEqual(r["HUMAN_REQUIRED_REASON"], "p0_finding")

    def test_p1_green_allowed_true_iter_zero_needs_fix(self):
        # P1 + budget left → fix loop, even if reviewer (incorrectly) set
        # allowed=true. The gate evaluates the fix loop based on severity.
        r = gate.decide("green", "P1", True, 0, 2, True)
        self.assertEqual(r["NEXT_ACTION"], "needs_fix")

    def test_override_auto_merge_allowed_true_but_p1(self):
        # Caller supplies auto_merge_allowed=True but severity is P1 — gate
        # must not honour the boolean.
        r = gate.decide("green", "P1", True, 0, 2, True)
        self.assertNotEqual(r["NEXT_ACTION"], "auto_merge")
        self.assertEqual(r["AUTO_MERGE_ALLOWED"], "false")

    def test_override_auto_merge_allowed_true_but_yellow(self):
        r = gate.decide("yellow", "none", True, 0, 2, True)
        self.assertNotEqual(r["NEXT_ACTION"], "auto_merge")
        self.assertEqual(r["AUTO_MERGE_ALLOWED"], "false")

    def test_self_test_cli(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--self-test"],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
        self.assertIn("self-test OK", proc.stdout)

    def test_cli_normal(self):
        proc = subprocess.run(
            [
                sys.executable, str(SCRIPT_PATH),
                "--risk-level", "green",
                "--highest-severity", "P1",
                "--auto-merge-allowed", "false",
                "--iteration", "0",
                "--max-iterations", "2",
                "--allow-auto-fix", "true",
            ],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertIn("NEXT_ACTION=needs_fix", proc.stdout)
        self.assertIn("NEXT_ITERATION=1", proc.stdout)

    def test_iteration_parse_error_routes_human_required(self):
        r = gate.decide("green", "none", True, 0, 2, True, iteration_parse_error=True)
        self.assertEqual(r["NEXT_ACTION"], "human_required")
        self.assertEqual(r["HUMAN_REQUIRED_REASON"], "iteration_parse_error")
        self.assertEqual(r["SHOULD_FIX"], "false")
        self.assertEqual(r["SHOULD_STOP"], "true")
        self.assertEqual(r["AUTO_MERGE_ALLOWED"], "false")

    def test_iteration_parse_error_overrides_clean_green_auto_merge(self):
        # Even a clean green PR that would otherwise auto-merge must escalate
        # when the iteration count cannot be trusted.
        r = gate.decide("green", "none", True, 0, 2, True, iteration_parse_error=True)
        self.assertNotEqual(r["NEXT_ACTION"], "auto_merge")

    def test_iteration_parse_error_overrides_p1_needs_fix(self):
        # A fixable P1 must NOT enter the fix loop when iteration is malformed —
        # otherwise the loop bound could be silently violated.
        r = gate.decide("green", "P1", False, 0, 2, True, iteration_parse_error=True)
        self.assertEqual(r["NEXT_ACTION"], "human_required")
        self.assertEqual(r["HUMAN_REQUIRED_REASON"], "iteration_parse_error")
        self.assertEqual(r["SHOULD_FIX"], "false")

    def test_cli_iteration_parse_error_flag(self):
        proc = subprocess.run(
            [
                sys.executable, str(SCRIPT_PATH),
                "--risk-level", "green",
                "--highest-severity", "none",
                "--auto-merge-allowed", "true",
                "--iteration", "0",
                "--max-iterations", "2",
                "--allow-auto-fix", "true",
                "--iteration-parse-error", "true",
            ],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertIn("NEXT_ACTION=human_required", proc.stdout)
        self.assertIn("HUMAN_REQUIRED_REASON=iteration_parse_error", proc.stdout)


if __name__ == "__main__":
    unittest.main()
