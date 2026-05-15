#!/usr/bin/env python3
"""Parse a Codex adversarial review result and emit GitHub Actions env vars.

Accepts either a raw YAML body or a markdown document containing a fenced
```yaml ... ``` block. Applies sanity overrides so that the downstream
review gate cannot be tricked by a malformed or self-contradicting review:
auto-merge is only permitted when the review reports zero findings AND a
green risk classification AND explicitly approves auto-merge.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

_PARENT_DIR = str(Path(__file__).resolve().parent)
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)
from _yamlmini import parse_yaml  # noqa: E402

VALID_RISK = ("green", "yellow", "red", "unknown")
VALID_SEVERITY = ("none", "P2", "P1", "P0")

_FENCE_RE = re.compile(
    r"```(?:yaml|yml)?\s*\n(.*?)\n```",
    re.DOTALL | re.IGNORECASE,
)
_TASK_ID_RE = re.compile(r"^task_id\s*:", re.MULTILINE)


def extract_yaml_block(text: str) -> str:
    m = _FENCE_RE.search(text)
    if m:
        return m.group(1)
    m = _TASK_ID_RE.search(text)
    if m:
        return text[m.start():]
    return text


def _to_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() == "true"
    return False


def parse(text: str) -> dict:
    body = extract_yaml_block(text)
    try:
        parsed = parse_yaml(body)
    except Exception:  # noqa: BLE001
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}

    risk = parsed.get("risk_level")
    if risk not in VALID_RISK:
        risk = "unknown"

    severity = parsed.get("highest_severity")
    if severity not in VALID_SEVERITY:
        # Conservative default: assume the worst when the reviewer omitted it.
        severity = "P0"

    allowed = _to_bool(parsed.get("auto_merge_allowed", False))

    # Sanity override: never trust the LLM's self-reported flag.
    if severity != "none":
        allowed = False
    if risk != "green":
        allowed = False

    findings = parsed.get("findings") or []
    if not isinstance(findings, list):
        findings = []

    return {
        "task_id": parsed.get("task_id") or "",
        "risk_level": risk,
        "highest_severity": severity,
        "auto_merge_allowed": allowed,
        "findings": findings,
        "summary": parsed.get("summary") or "",
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: parse-review-result.py codex-review.md", file=sys.stderr)
        return 2

    path = Path(argv[1])
    if not path.exists():
        print(f"Review result not found: {path}", file=sys.stderr)
        return 2

    result = parse(path.read_text(encoding="utf-8"))
    print(f"RISK_LEVEL={result['risk_level']}")
    print(f"HIGHEST_SEVERITY={result['highest_severity']}")
    print(f"AUTO_MERGE_ALLOWED={'true' if result['auto_merge_allowed'] else 'false'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
