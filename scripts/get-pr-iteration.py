#!/usr/bin/env python3
"""Read the current AI iteration count from a PR's labels JSON.

Accepts the canonical shape emitted by `gh pr view --json labels`:
- {"labels": [{"name": "ai:iter-1", ...}, ...]}
- [{"name": "ai:iter-1", ...}, ...]   (the same labels list, unwrapped)

Anything else is treated as a parse failure. The script always emits
both env vars on stdout, but exits non-zero when a parse error is
detected so the workflow's `set -e` aborts before the fix loop runs:

    CURRENT_ITERATION=N
    ITERATION_PARSE_ERROR=true|false

The downstream review gate (`decide-review-gate.py --iteration-parse-error`)
must also be invoked with the same flag, so that a malformed iteration
count escalates the PR to `human_required` instead of silently resetting
the loop budget and bypassing `max_iterations`.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

_ITER_RE = re.compile(r"^ai:iter-(\d+)$")
_ITER_LIKE_RE = re.compile(r"^ai:iter-")


def extract_iteration(data: Any) -> tuple[int, bool]:
    """Return ``(max_iteration, parse_error)``.

    ``parse_error`` is True if any structural anomaly is found:
    - the container is neither a list nor a dict
    - the dict's ``labels`` key is present but not a list
    - any label entry is not a dict
    - a label dict's ``name`` is not a string
    - a label name has the ``ai:iter-`` prefix but a non-numeric suffix
    """
    if isinstance(data, list):
        labels = data
    elif isinstance(data, dict):
        labels = data.get("labels", [])
        if not isinstance(labels, list):
            return (0, True)
    else:
        return (0, True)

    max_n = 0
    for item in labels:
        if not isinstance(item, dict):
            return (0, True)
        name = item.get("name")
        if not isinstance(name, str):
            return (0, True)
        stripped = name.strip()
        m = _ITER_RE.match(stripped)
        if m:
            n = int(m.group(1))
            if n > max_n:
                max_n = n
            continue
        if _ITER_LIKE_RE.match(stripped):
            return (0, True)
    return (max_n, False)


def _emit(current: int, parse_error: bool) -> None:
    print(f"CURRENT_ITERATION={current}")
    print(f"ITERATION_PARSE_ERROR={'true' if parse_error else 'false'}")


def main(argv: list[str]) -> int:
    if len(argv) > 2:
        print("Usage: get-pr-iteration.py [labels.json or - for stdin]", file=sys.stderr)
        return 2

    if len(argv) == 1 or argv[1] == "-":
        try:
            data = json.load(sys.stdin)
        except (json.JSONDecodeError, ValueError) as exc:
            print(f"ERROR: failed to parse labels JSON from stdin: {exc}", file=sys.stderr)
            _emit(0, True)
            return 1
    else:
        path = Path(argv[1])
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            print(f"ERROR: failed to read labels JSON: {exc}", file=sys.stderr)
            _emit(0, True)
            return 1

    current, parse_error = extract_iteration(data)
    _emit(current, parse_error)
    return 1 if parse_error else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
