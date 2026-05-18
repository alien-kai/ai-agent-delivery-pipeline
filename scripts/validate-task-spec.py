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

# See `_is_repo_wide_allowed_pattern` for the green-scope guard. We do not
# enumerate broad patterns as exact strings any more — semantically
# equivalent variants such as `./**/*` or `**/**` previously slipped past
# an exact-match check.


def _normalize_scope_pattern(pattern: str) -> str:
    """Collapse cosmetic variations in a glob pattern.

    This is a conservative normalization for the green-scope guard; it is
    not a full glob engine. It strips whitespace, folds backslashes to
    forward slashes, collapses repeated slashes, peels leading ``./``
    segments, and drops a trailing slash. After this, semantically
    equivalent repo-wide patterns such as ``./**/*`` and ``**/*`` compare
    equal and can be rejected by the same rule.
    """
    s = pattern.strip().replace("\\", "/")
    while "//" in s:
        s = s.replace("//", "/")
    while s.startswith("./"):
        s = s[2:]
    if s == ".":
        s = ""
    if len(s) > 1 and s.endswith("/"):
        s = s[:-1]
    return s


def _is_repo_wide_allowed_pattern(pattern: str) -> bool:
    """Return True if ``pattern`` is too broad or unsafe for a green scope.

    A pattern is treated as repo-wide when, after normalization, it is
    empty (``.`` / ``./`` / ``""``), absolute (starts with ``/``), contains
    a ``..`` traversal segment, or consists only of pure-wildcard segments
    (``*`` or ``**``). A segment with literal content alongside a wildcard,
    such as ``*.md`` or ``docs``, anchors the pattern to a real subset of
    the tree and is not considered repo-wide.
    """
    norm = _normalize_scope_pattern(pattern)
    if norm == "":
        return True
    if norm.startswith("/"):
        return True
    segments = norm.split("/")
    if any(seg == ".." for seg in segments):
        return True
    return all(seg in ("*", "**") for seg in segments)

# Sentinel for `_check_string_list` so it can tell a genuinely absent key
# from a key that is present with `null` / a bare value.
_MISSING = object()


def _present(value) -> bool:
    if value is None:
        return False
    if isinstance(value, (str, list, dict)) and len(value) == 0:
        return False
    return True


def _check_string_list(value, field_name: str, errors: list) -> None:
    """Validate that ``value`` is a non-empty list of non-empty strings.

    Callers must pass ``_MISSING`` when the key is genuinely absent —
    that is the only case this helper tolerates. Any other value,
    including ``None`` from an explicit YAML ``null`` or a bare key,
    counts as a present field that must satisfy the non-empty-list
    contract.
    """
    if value is _MISSING:
        return
    if not isinstance(value, list):
        errors.append(f"{field_name} must be a list of strings")
        return
    if len(value) == 0:
        errors.append(f"{field_name} must be a non-empty list of strings")
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

    # Distinguish a missing key from an explicit `null` / bare key. Only
    # true absence applies the legacy default; an explicit null is schema
    # drift and must fail closed.
    if "allow_auto_fix" in spec:
        raw_allow_auto_fix = spec["allow_auto_fix"]
        if raw_allow_auto_fix is None:
            errors.append("allow_auto_fix must be boolean, got null")
            allow_auto_fix = None
        elif not isinstance(raw_allow_auto_fix, bool):
            errors.append(
                f"allow_auto_fix must be boolean, got {type(raw_allow_auto_fix).__name__}"
            )
            allow_auto_fix = None
        else:
            allow_auto_fix = raw_allow_auto_fix
    else:
        allow_auto_fix = None

    if risk == "red" and allow_auto_fix is True:
        errors.append("red tasks must set allow_auto_fix: false")

    if "max_iterations" in spec:
        raw_max_iter = spec["max_iterations"]
        if raw_max_iter is None:
            errors.append("max_iterations must be an integer, got null")
            max_iter = None
        elif isinstance(raw_max_iter, bool) or not isinstance(raw_max_iter, int):
            errors.append(
                f"max_iterations must be an integer, got {type(raw_max_iter).__name__}"
            )
            max_iter = None
        elif not 0 <= raw_max_iter <= 5:
            errors.append(
                f"max_iterations must be between 0 and 5, got {raw_max_iter}"
            )
            max_iter = None
        else:
            max_iter = raw_max_iter
    else:
        max_iter = None

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
        spec.get("allowed_file_patterns", _MISSING),
        "allowed_file_patterns",
        errors,
    )
    _check_string_list(
        spec.get("forbidden_file_patterns", _MISSING),
        "forbidden_file_patterns",
        errors,
    )
    _check_string_list(
        spec.get("risk_reasoning", _MISSING), "risk_reasoning", errors
    )

    # Green tasks must not declare globally-permissive allowed patterns;
    # those defeat the auto-merge scope guard. Empty / whitespace-only
    # items are already rejected by `_check_string_list` — skipping them
    # here avoids emitting a duplicate error for the same item.
    if risk == "green":
        afp = spec.get("allowed_file_patterns")
        if isinstance(afp, list):
            for i, item in enumerate(afp):
                if (
                    isinstance(item, str)
                    and item.strip()
                    and _is_repo_wide_allowed_pattern(item)
                ):
                    errors.append(
                        f"allowed_file_patterns[{i}]={item!r} is too broad "
                        f"or unsafe for a green task; green requires a "
                        f"bounded, repo-relative path"
                    )

    hrrr = spec.get("human_review_required_reason")
    if hrrr is not None and not isinstance(hrrr, str):
        errors.append("human_review_required_reason must be a string")

    # Green specs should declare an allowlist. We only treat the *missing
    # key* case as the legacy-compatible warning; an explicitly empty list
    # is a clearer violation and is rejected by `_check_string_list` above
    # in both modes. In --strict mode the missing key is also an error.
    if risk == "green" and "allowed_file_patterns" not in spec:
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
