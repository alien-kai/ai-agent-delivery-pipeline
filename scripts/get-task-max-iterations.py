#!/usr/bin/env python3
"""Read max_iterations and allow_auto_fix from a task-spec YAML.

Defaults:
- max_iterations missing  -> 2
- allow_auto_fix missing  -> true (false for red tasks)
- max_iterations out of [0,5] -> error, non-zero exit

Output (env-style on stdout):
    MAX_ITERATIONS=N
    ALLOW_AUTO_FIX=true|false
"""

from __future__ import annotations

import sys
from pathlib import Path

_PARENT_DIR = str(Path(__file__).resolve().parent)
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)
from _yamlmini import parse_yaml  # noqa: E402

DEFAULT_MAX_ITERATIONS = 2


def extract(text: str) -> dict:
    try:
        spec = parse_yaml(text)
    except Exception:  # noqa: BLE001
        spec = {}
    if not isinstance(spec, dict):
        spec = {}

    raw_max = spec.get("max_iterations")
    max_err: str | None = None
    if raw_max is None:
        max_iter: int | None = DEFAULT_MAX_ITERATIONS
    elif isinstance(raw_max, bool) or not isinstance(raw_max, int):
        max_iter = None
        max_err = f"max_iterations must be an integer, got {type(raw_max).__name__}"
    elif not 0 <= raw_max <= 5:
        max_iter = None
        max_err = f"max_iterations must be between 0 and 5, got {raw_max}"
    else:
        max_iter = raw_max

    risk = spec.get("risk_level")
    raw_allow = spec.get("allow_auto_fix")
    if raw_allow is None:
        allow = risk != "red"
    elif isinstance(raw_allow, bool):
        allow = raw_allow
    else:
        # Invalid type — fail closed.
        allow = False

    return {
        "max_iterations": max_iter,
        "max_iterations_error": max_err,
        "allow_auto_fix": bool(allow),
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: get-task-max-iterations.py .ai/tasks/123.yaml", file=sys.stderr)
        return 2

    path = Path(argv[1])
    if not path.exists():
        print(f"Task spec not found: {path}", file=sys.stderr)
        return 2

    result = extract(path.read_text(encoding="utf-8"))
    if result["max_iterations_error"]:
        print(f"Invalid task spec: {result['max_iterations_error']}", file=sys.stderr)
        return 1

    print(f"MAX_ITERATIONS={result['max_iterations']}")
    print(f"ALLOW_AUTO_FIX={'true' if result['allow_auto_fix'] else 'false'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
