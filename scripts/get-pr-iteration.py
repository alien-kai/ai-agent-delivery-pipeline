#!/usr/bin/env python3
"""Read the current AI iteration count from a PR's labels JSON.

Accepts label payloads in any of the shapes produced by `gh pr view`:
- {"labels": [{"name": "ai:iter-1"}, ...]}
- [{"name": "ai:iter-1"}, ...]
- ["ai:iter-1", ...]

Outputs (env-style on stdout):
    CURRENT_ITERATION=N

Where N is the largest integer found among `ai:iter-N` label names, or 0
if none are present. Any parse error is reported as a warning to stderr
and N defaults to 0 — never crash the workflow.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

_ITER_RE = re.compile(r"^ai:iter-(\d+)$")


def extract_iteration(labels_data: Any) -> int:
    names = _to_label_names(labels_data)
    max_n = 0
    for name in names:
        m = _ITER_RE.match(name.strip())
        if not m:
            continue
        try:
            n = int(m.group(1))
        except ValueError:
            continue
        if n > max_n:
            max_n = n
    return max_n


def _to_label_names(data: Any) -> list[str]:
    if isinstance(data, list):
        out: list[str] = []
        for item in data:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict) and isinstance(item.get("name"), str):
                out.append(item["name"])
        return out
    if isinstance(data, dict):
        return _to_label_names(data.get("labels", []))
    return []


def main(argv: list[str]) -> int:
    if len(argv) > 2:
        print("Usage: get-pr-iteration.py [labels.json or - for stdin]", file=sys.stderr)
        return 2

    if len(argv) == 1 or argv[1] == "-":
        try:
            data = json.load(sys.stdin)
        except (json.JSONDecodeError, ValueError) as exc:
            print(f"WARN: failed to parse labels JSON from stdin: {exc}", file=sys.stderr)
            print("CURRENT_ITERATION=0")
            return 0
    else:
        path = Path(argv[1])
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            print(f"WARN: failed to read labels JSON: {exc}", file=sys.stderr)
            print("CURRENT_ITERATION=0")
            return 0

    print(f"CURRENT_ITERATION={extract_iteration(data)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
