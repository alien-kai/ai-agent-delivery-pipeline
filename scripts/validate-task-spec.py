#!/usr/bin/env python3
"""Validate a task-spec YAML file using only the Python standard library.

The parser implements the limited YAML subset that this repo's task specs
actually use: top-level mappings, lists of scalars, lists of mappings, and
block scalars (`|`, `>`, `|-`, `>-`, `|+`, `>+`). No flow style, anchors,
tags, or merge keys.
"""

from __future__ import annotations

import argparse
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

# Patterns that span the entire tree and therefore make no useful scope
# guard for a green auto-merge task. The validator rejects them outright
# on green specs.
MEANINGLESS_GREEN_PATTERNS = frozenset({"*", "**", "**/*", ".", "./", "/"})


def _present(value) -> bool:
    if value is None:
        return False
    if isinstance(value, (str, list, dict)) and len(value) == 0:
        return False
    return True


def _check_string_list(value, field_name: str, errors: list) -> None:
    """Validate that ``value`` is a list of non-empty strings.

    Empty / missing values are tolerated by this helper — required-field
    presence checks live elsewhere. We only enforce item-level shape.
    """
    if value is None:
        return
    if not isinstance(value, list):
        errors.append(f"{field_name} must be a list of strings")
        return
    for i, item in enumerate(value):
        if not isinstance(item, str):
            errors.append(
                f"{field_name}[{i}] must be a string, got {type(item).__name__}"
            )
        elif not item.strip():
            errors.append(f"{field_name}[{i}] must be a non-empty string")


def validate(path: Path, strict: bool = False) -> dict:
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

    _check_string_list(
        spec.get("allowed_file_patterns"), "allowed_file_patterns", errors
    )
    _check_string_list(
        spec.get("forbidden_file_patterns"), "forbidden_file_patterns", errors
    )
    _check_string_list(spec.get("risk_reasoning"), "risk_reasoning", errors)

    # Green tasks must not declare globally-permissive allowed patterns;
    # those defeat the auto-merge scope guard.
    if risk == "green":
        afp = spec.get("allowed_file_patterns")
        if isinstance(afp, list):
            for i, item in enumerate(afp):
                if isinstance(item, str) and item.strip() in MEANINGLESS_GREEN_PATTERNS:
                    errors.append(
                        f"allowed_file_patterns[{i}]={item!r} is too broad for a "
                        f"green task; green requires a specific file or glob"
                    )

    hrrr = spec.get("human_review_required_reason")
    if hrrr is not None and not isinstance(hrrr, str):
        errors.append("human_review_required_reason must be a string")

    # Green specs should declare an allowlist. In --strict mode this is an
    # error; in the default (legacy-compatible) mode it is only a warning
    # so older specs don't strand open plan PRs.
    if risk == "green" and not spec.get("allowed_file_patterns"):
        if strict:
            errors.append(
                "green tasks require allowed_file_patterns in --strict mode"
            )
        else:
            warnings.append(
                "green task should declare allowed_file_patterns to keep "
                "auto-merge scope tight"
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
        "warnings": warnings,
    }

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "summary": summary,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a task-spec YAML against the Ticket #1 contract.",
    )
    parser.add_argument("path", help="path to the task-spec YAML")
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "treat missing allowed_file_patterns on green tasks as an error "
            "(default: emit a warning, exit 0)"
        ),
    )
    args = parser.parse_args(argv[1:])

    path = Path(args.path)
    if not path.exists():
        print(f"Task spec not found: {path}", file=sys.stderr)
        return 2

    result = validate(path, strict=args.strict)

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
