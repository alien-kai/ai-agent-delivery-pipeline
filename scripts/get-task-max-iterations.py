#!/usr/bin/env python3
"""Read max_iterations and allow_auto_fix from a task-spec YAML.

Contract (matches Ticket #1 risk_level semantics):

- risk_level missing or not in {green, yellow, red} -> fail closed.
- risk_level=green/yellow:
    - max_iterations missing            -> 2 (default)
    - max_iterations out of [0, 5]      -> fail closed
    - max_iterations non-integer        -> fail closed
    - allow_auto_fix missing            -> true (default)
- risk_level=red:
    - max_iterations missing            -> 0
    - max_iterations != 0               -> fail closed
    - allow_auto_fix=true               -> fail closed
    - allow_auto_fix missing            -> false (default)

"Fail closed" means: return errors, set max_iterations=None, set
allow_auto_fix=False, and emit a non-zero CLI exit. Callers must route
the PR to human_required when the helper exits non-zero.

Output (env-style on stdout, only on success):
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
VALID_RISK = ("green", "yellow", "red")


def extract(text: str) -> dict:
    try:
        spec = parse_yaml(text)
    except Exception:  # noqa: BLE001
        spec = {}
    if not isinstance(spec, dict):
        spec = {}

    risk = spec.get("risk_level")
    if risk not in VALID_RISK:
        # Without a known risk_level we cannot decide a budget. Fail closed
        # before reading any other field so a malformed spec never produces
        # a usable MAX_ITERATIONS value.
        return {
            "max_iterations": None,
            "allow_auto_fix": False,
            "errors": [
                f"risk_level must be green/yellow/red, got {risk!r}"
            ],
        }

    errors: list[str] = []

    raw_max = spec.get("max_iterations")
    max_iter: int | None = None

    if raw_max is None:
        max_iter = 0 if risk == "red" else DEFAULT_MAX_ITERATIONS
    elif isinstance(raw_max, bool) or not isinstance(raw_max, int):
        errors.append(
            f"max_iterations must be an integer, got {type(raw_max).__name__}"
        )
    elif not 0 <= raw_max <= 5:
        errors.append(f"max_iterations must be between 0 and 5, got {raw_max}")
    elif risk == "red" and raw_max != 0:
        errors.append(
            f"red tasks must have max_iterations: 0, got {raw_max}"
        )
    else:
        max_iter = raw_max

    raw_allow = spec.get("allow_auto_fix")
    if raw_allow is None:
        allow = risk != "red"
    elif isinstance(raw_allow, bool):
        if risk == "red" and raw_allow is True:
            errors.append("red tasks must have allow_auto_fix: false")
            allow = False
        else:
            allow = raw_allow
    else:
        errors.append(
            f"allow_auto_fix must be a boolean, got {type(raw_allow).__name__}"
        )
        allow = False

    # Any helper error invalidates the budget value. A nonzero red value
    # already left max_iter=None above; force the same for allow-side errors
    # so callers cannot mistake a partial result for a usable budget.
    if errors:
        max_iter = None
        allow = False

    return {
        "max_iterations": max_iter,
        "allow_auto_fix": bool(allow),
        "errors": errors,
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
    if result["errors"]:
        for err in result["errors"]:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1

    print(f"MAX_ITERATIONS={result['max_iterations']}")
    print(f"ALLOW_AUTO_FIX={'true' if result['allow_auto_fix'] else 'false'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
