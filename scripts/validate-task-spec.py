#!/usr/bin/env python3
"""Validate a task-spec YAML file using only the Python standard library.

The parser implements the limited YAML subset that this repo's task specs
actually use: top-level mappings, lists of scalars, lists of mappings, and
block scalars (`|`, `>`, `|-`, `>-`, `|+`, `>+`). No flow style, anchors,
tags, or merge keys.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Minimal YAML reader (shared with sibling scripts via scripts/_yamlmini.py)
# ---------------------------------------------------------------------------

_PARENT_DIR = str(Path(__file__).resolve().parent)
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)
from _yamlmini import parse_yaml  # noqa: E402


# ---------------------------------------------------------------------------
# Validation rules
# ---------------------------------------------------------------------------

REQUIRED = (
    "task_id",
    "source_issue",
    "objective",
    "risk_level",
    "merge_policy",
    "implementation_units",
    "acceptance_criteria",
    "verification_commands",
    "review_requirements",
)
VALID_RISK = ("green", "yellow", "red")
VALID_MERGE = ("auto_merge_if_green", "require_human", "draft_only")
RISK_MERGE_POLICY = {
    "green": "auto_merge_if_green",
    "yellow": "require_human",
    "red": "draft_only",
}
DEFAULT_MAX_ITERATIONS = 2


def _present(value) -> bool:
    if value is None:
        return False
    if isinstance(value, (str, list, dict)) and len(value) == 0:
        return False
    return True


def validate(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return {
            "ok": False,
            "errors": [f"unable to read {path}: {exc}"],
            "warnings": [],
            "summary": {},
        }

    try:
        spec = parse_yaml(text)
    except Exception as exc:  # noqa: BLE001 — parser may raise anything
        return {
            "ok": False,
            "errors": [f"YAML parse failure: {exc}"],
            "warnings": [],
            "summary": {},
        }

    if not isinstance(spec, dict):
        return {
            "ok": False,
            "errors": ["top-level must be a mapping"],
            "warnings": [],
            "summary": {},
        }

    errors: list[str] = []
    warnings: list[str] = []

    for key in REQUIRED:
        if key not in spec or not _present(spec[key]):
            errors.append(f"missing required field: {key}")

    risk = spec.get("risk_level")
    if risk == "unknown":
        errors.append(
            "risk_level=unknown is not allowed in task specs; "
            "planner must classify as green, yellow, or red"
        )
    elif risk is not None and risk not in VALID_RISK:
        errors.append(f"invalid risk_level: {risk!r}")

    merge = spec.get("merge_policy")
    if merge is not None and merge not in VALID_MERGE:
        errors.append(f"invalid merge_policy: {merge!r}")

    expected_merge = RISK_MERGE_POLICY.get(risk)
    if expected_merge is not None and merge != expected_merge:
        errors.append(f"{risk} tasks must use merge_policy: {expected_merge}")

    allow_auto_fix = spec.get("allow_auto_fix")
    if allow_auto_fix is not None and not isinstance(allow_auto_fix, bool):
        errors.append(
            f"allow_auto_fix must be boolean, got {type(allow_auto_fix).__name__}"
        )

    if risk == "red" and allow_auto_fix is True:
        errors.append("red tasks must set allow_auto_fix: false")

    max_iter = spec.get("max_iterations")
    if max_iter is not None:
        if isinstance(max_iter, bool) or not isinstance(max_iter, int):
            errors.append(
                f"max_iterations must be an integer, got {type(max_iter).__name__}"
            )
        elif not 0 <= max_iter <= 5:
            errors.append(f"max_iterations must be between 0 and 5, got {max_iter}")

    # Red tasks never enter the AI fix loop, so any nonzero max_iterations
    # value is contradictory. Reject it so the planner can't ship a spec
    # that suggests a fix budget exists where it does not.
    if (
        risk == "red"
        and isinstance(max_iter, int)
        and not isinstance(max_iter, bool)
        and max_iter != 0
    ):
        errors.append(
            "red tasks must set max_iterations: 0 (no auto-fix iterations allowed)"
        )

    for list_key in (
        "allowed_file_patterns",
        "forbidden_file_patterns",
        "risk_reasoning",
    ):
        value = spec.get(list_key)
        if value is not None and not isinstance(value, list):
            errors.append(f"{list_key} must be a list of strings")

    hrrr = spec.get("human_review_required_reason")
    if hrrr is not None and not isinstance(hrrr, str):
        errors.append("human_review_required_reason must be a string")

    if risk == "green" and not spec.get("allowed_file_patterns"):
        errors.append(
            "green tasks require allowed_file_patterns to keep auto-merge scope tight"
        )

    if risk == "red" and not spec.get("human_review_required_reason"):
        warnings.append(
            "red task should declare human_review_required_reason"
        )

    # Normalize max_iterations for the summary so downstream consumers never
    # see a contradictory red+nonzero value, even if the spec is invalid.
    if risk == "red":
        summary_max_iter = 0
    elif (
        max_iter is not None
        and isinstance(max_iter, int)
        and not isinstance(max_iter, bool)
        and 0 <= max_iter <= 5
    ):
        summary_max_iter = max_iter
    else:
        summary_max_iter = DEFAULT_MAX_ITERATIONS

    summary = {
        "ok": not errors,
        "task_id": spec.get("task_id"),
        "risk_level": risk,
        "merge_policy": merge,
        "max_iterations": summary_max_iter,
        "allow_auto_fix": (
            allow_auto_fix if allow_auto_fix is not None else (risk != "red")
        ),
    }

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "summary": summary,
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: validate-task-spec.py .ai/tasks/123.yaml", file=sys.stderr)
        return 2

    path = Path(argv[1])
    if not path.exists():
        print(f"Task spec not found: {path}", file=sys.stderr)
        return 2

    result = validate(path)

    for w in result["warnings"]:
        print(f"WARN: {w}", file=sys.stderr)

    if not result["ok"]:
        print("Task spec validation failed:", file=sys.stderr)
        for e in result["errors"]:
            print(f"- {e}", file=sys.stderr)
        return 1

    print(json.dumps(result["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
