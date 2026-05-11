#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REQUIRED = [
    "task_id",
    "source_issue",
    "objective",
    "risk_level",
    "merge_policy",
    "implementation_units",
    "acceptance_criteria",
    "verification_commands",
    "review_requirements",
]

VALID_RISK = {"green", "yellow", "red"}
VALID_MERGE = {"auto_merge_if_green", "require_human", "draft_only"}


def simple_yaml_value(text: str, key: str) -> str | None:
    match = re.search(rf"^{re.escape(key)}:\s*[\"']?([^\"'\n]+)[\"']?\s*$", text, re.MULTILINE)
    return match.group(1).strip() if match else None


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: validate-task-spec.py .ai/tasks/123.yaml", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    text = path.read_text(encoding="utf-8")

    errors: list[str] = []
    for key in REQUIRED:
        if not re.search(rf"^{re.escape(key)}:", text, re.MULTILINE):
            errors.append(f"missing required key: {key}")

    risk = simple_yaml_value(text, "risk_level")
    if risk and risk not in VALID_RISK:
        errors.append(f"invalid risk_level: {risk}")

    merge = simple_yaml_value(text, "merge_policy")
    if merge and merge not in VALID_MERGE:
        errors.append(f"invalid merge_policy: {merge}")

    if risk == "red" and merge != "draft_only":
        errors.append("red tasks must use merge_policy: draft_only")

    if errors:
        print("Task spec validation failed:", file=sys.stderr)
        for err in errors:
            print(f"- {err}", file=sys.stderr)
        return 1

    print(json.dumps({"ok": True, "risk_level": risk, "merge_policy": merge}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
