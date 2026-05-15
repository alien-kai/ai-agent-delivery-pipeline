#!/usr/bin/env python3
"""Decide the next pipeline action after a Codex review.

Inputs come from prior steps in the workflow:
- risk_level, highest_severity, auto_merge_allowed from parse-review-result.py
- iteration from get-pr-iteration.py
- max_iterations, allow_auto_fix from get-task-max-iterations.py

Output (env vars on stdout, designed to be `source`d):
- NEXT_ACTION         auto_merge | needs_fix | human_required | max_iterations_reached
- SHOULD_FIX          true | false
- SHOULD_STOP         true | false  (terminal state — no further automation)
- AUTO_MERGE_ALLOWED  true | false
- NEXT_ITERATION      integer (current iteration unchanged unless SHOULD_FIX=true)
- HUMAN_REQUIRED_REASON  short token for label/comment routing

Policy:
- P0 finding              -> human_required (regardless of risk or budget)
- risk=red                -> human_required
- risk=unknown            -> human_required
- allow_auto_fix=false +  -> human_required (anything other than clean+green)
  findings present
- iteration >= max + P1/P2 -> max_iterations_reached
- P1 or P2, budget left,  -> needs_fix
  risk in {green, yellow}
- clean + green + allowed -> auto_merge
- clean + yellow          -> human_required (yellow needs human merge approval)
- anything else           -> human_required
"""

from __future__ import annotations

import argparse
import sys

VALID_RISK = ("green", "yellow", "red", "unknown")
VALID_SEVERITY = ("none", "P2", "P1", "P0")

NEXT_AUTO_MERGE = "auto_merge"
NEXT_NEEDS_FIX = "needs_fix"
NEXT_HUMAN_REQUIRED = "human_required"
NEXT_MAX_ITER = "max_iterations_reached"


def decide(
    risk_level: str,
    highest_severity: str,
    auto_merge_allowed: bool,
    iteration: int,
    max_iterations: int,
    allow_auto_fix: bool,
    iteration_parse_error: bool = False,
) -> dict:
    # Fail-closed: a malformed iteration count means we cannot honour the
    # loop bound. Escalate before any other policy runs.
    if iteration_parse_error:
        return _result(
            NEXT_HUMAN_REQUIRED, False, True, False, iteration,
            "iteration_parse_error",
        )

    if risk_level not in VALID_RISK:
        risk_level = "unknown"
    if highest_severity not in VALID_SEVERITY:
        highest_severity = "P0"

    if highest_severity == "P0":
        return _result(NEXT_HUMAN_REQUIRED, False, True, False, iteration, "p0_finding")

    if risk_level == "red":
        return _result(NEXT_HUMAN_REQUIRED, False, True, False, iteration, "red_risk")

    if risk_level == "unknown":
        return _result(NEXT_HUMAN_REQUIRED, False, True, False, iteration, "unknown_risk")

    if highest_severity == "none":
        if risk_level == "green" and auto_merge_allowed:
            return _result(NEXT_AUTO_MERGE, False, False, True, iteration, "")
        if risk_level == "yellow":
            return _result(NEXT_HUMAN_REQUIRED, False, True, False, iteration, "yellow_human_merge")
        return _result(NEXT_HUMAN_REQUIRED, False, True, False, iteration, "merge_not_allowed")

    if highest_severity == "P2":
        # P2 is informational: a P2 alone does not block green-lane auto-merge
        # (per risk-policy.md). Yellow always requires human merge approval,
        # so P2 + yellow falls through to human_required.
        if risk_level == "green" and auto_merge_allowed:
            return _result(NEXT_AUTO_MERGE, False, False, True, iteration, "")
        return _result(NEXT_HUMAN_REQUIRED, False, True, False, iteration, "p2_finding")

    # Severity is P1 — the only remaining path. P0 was handled above and
    # P2/none never reach here.
    if not allow_auto_fix:
        return _result(NEXT_HUMAN_REQUIRED, False, True, False, iteration, "auto_fix_disabled")

    if iteration >= max_iterations:
        return _result(NEXT_MAX_ITER, False, True, False, iteration, "max_iterations_reached")

    return _result(NEXT_NEEDS_FIX, True, False, False, iteration + 1, "")


def _result(action, should_fix, should_stop, allowed, next_iter, reason):
    return {
        "NEXT_ACTION": action,
        "SHOULD_FIX": "true" if should_fix else "false",
        "SHOULD_STOP": "true" if should_stop else "false",
        "AUTO_MERGE_ALLOWED": "true" if allowed else "false",
        "NEXT_ITERATION": str(next_iter),
        "HUMAN_REQUIRED_REASON": reason,
    }


def _emit(result: dict) -> None:
    for k, v in result.items():
        print(f"{k}={v}")


def _str_bool(s: str) -> bool:
    return s.strip().lower() == "true"


def _self_test() -> int:
    cases = [
        (dict(risk_level="green", highest_severity="none", auto_merge_allowed=True,
              iteration=0, max_iterations=2, allow_auto_fix=True),
         NEXT_AUTO_MERGE),
        (dict(risk_level="green", highest_severity="P1", auto_merge_allowed=False,
              iteration=0, max_iterations=2, allow_auto_fix=True),
         NEXT_NEEDS_FIX),
        (dict(risk_level="green", highest_severity="P1", auto_merge_allowed=False,
              iteration=2, max_iterations=2, allow_auto_fix=True),
         NEXT_MAX_ITER),
        (dict(risk_level="green", highest_severity="P0", auto_merge_allowed=False,
              iteration=0, max_iterations=2, allow_auto_fix=True),
         NEXT_HUMAN_REQUIRED),
        (dict(risk_level="yellow", highest_severity="none", auto_merge_allowed=False,
              iteration=0, max_iterations=3, allow_auto_fix=True),
         NEXT_HUMAN_REQUIRED),
        (dict(risk_level="red", highest_severity="none", auto_merge_allowed=False,
              iteration=0, max_iterations=0, allow_auto_fix=False),
         NEXT_HUMAN_REQUIRED),
        (dict(risk_level="unknown", highest_severity="P1", auto_merge_allowed=False,
              iteration=0, max_iterations=2, allow_auto_fix=True),
         NEXT_HUMAN_REQUIRED),
        (dict(risk_level="green", highest_severity="P1", auto_merge_allowed=False,
              iteration=0, max_iterations=2, allow_auto_fix=False),
         NEXT_HUMAN_REQUIRED),
        (dict(risk_level="yellow", highest_severity="P1", auto_merge_allowed=False,
              iteration=0, max_iterations=3, allow_auto_fix=True),
         NEXT_NEEDS_FIX),
        (dict(risk_level="green", highest_severity="P2", auto_merge_allowed=True,
              iteration=1, max_iterations=2, allow_auto_fix=True),
         NEXT_AUTO_MERGE),
        (dict(risk_level="green", highest_severity="P2", auto_merge_allowed=False,
              iteration=1, max_iterations=2, allow_auto_fix=True),
         NEXT_HUMAN_REQUIRED),
        (dict(risk_level="yellow", highest_severity="P2", auto_merge_allowed=True,
              iteration=0, max_iterations=3, allow_auto_fix=True),
         NEXT_HUMAN_REQUIRED),
        (dict(risk_level="green", highest_severity="none", auto_merge_allowed=True,
              iteration=0, max_iterations=2, allow_auto_fix=True,
              iteration_parse_error=True),
         NEXT_HUMAN_REQUIRED),
        (dict(risk_level="green", highest_severity="P1", auto_merge_allowed=False,
              iteration=0, max_iterations=2, allow_auto_fix=True,
              iteration_parse_error=True),
         NEXT_HUMAN_REQUIRED),
    ]
    fails = []
    for inp, expected in cases:
        got = decide(**inp)["NEXT_ACTION"]
        if got != expected:
            fails.append(f"FAIL: {inp} expected {expected!r}, got {got!r}")
    if fails:
        for line in fails:
            print(line, file=sys.stderr)
        return 1
    print(f"self-test OK: {len(cases)} cases passed")
    return 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Decide next action after Codex review")
    p.add_argument("--risk-level")
    p.add_argument("--highest-severity")
    p.add_argument("--auto-merge-allowed")
    p.add_argument("--iteration", type=int, default=0)
    p.add_argument("--max-iterations", type=int, default=2)
    p.add_argument("--allow-auto-fix", default="true")
    p.add_argument(
        "--iteration-parse-error",
        default="false",
        help="set to 'true' when get-pr-iteration.py reported a parse error",
    )
    p.add_argument("--self-test", action="store_true")
    args = p.parse_args(argv[1:])

    if args.self_test:
        return _self_test()

    missing = [
        flag for flag, val in (
            ("--risk-level", args.risk_level),
            ("--highest-severity", args.highest_severity),
            ("--auto-merge-allowed", args.auto_merge_allowed),
        )
        if val is None
    ]
    if missing:
        print(f"Missing required flags: {', '.join(missing)}", file=sys.stderr)
        p.print_help(sys.stderr)
        return 2

    result = decide(
        risk_level=args.risk_level,
        highest_severity=args.highest_severity,
        auto_merge_allowed=_str_bool(args.auto_merge_allowed),
        iteration=args.iteration,
        max_iterations=args.max_iterations,
        allow_auto_fix=_str_bool(args.allow_auto_fix),
        iteration_parse_error=_str_bool(args.iteration_parse_error),
    )
    _emit(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
