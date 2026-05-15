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
_SEVERITY_RANK = {"none": 0, "P2": 1, "P1": 2, "P0": 3}

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


def _max_severity_from_findings(findings) -> tuple[str, bool]:
    """Scan a findings list and report ``(max_blocking_severity, malformed)``.

    Only dict entries with a string ``severity`` in the recognised set
    ``{P0, P1, P2, Info}`` are accepted. ``Info`` is non-elevating but
    valid. Anything else (non-dict entry, missing severity, non-string
    severity, or an unknown severity label) counts as schema drift; the
    caller is expected to fail closed by inspecting the ``malformed`` flag.
    """
    if not isinstance(findings, list):
        return ("none", False)
    valid = ("P0", "P1", "P2", "Info")
    best = "none"
    best_rank = 0
    for item in findings:
        if not isinstance(item, dict):
            return ("P0", True)
        sev = item.get("severity")
        if not isinstance(sev, str) or sev not in valid:
            return ("P0", True)
        if sev == "Info":
            continue
        rank = _SEVERITY_RANK[sev]
        if rank > best_rank:
            best_rank = rank
            best = sev
    return (best, False)


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

    top_severity = parsed.get("highest_severity")
    if top_severity not in VALID_SEVERITY:
        # Conservative default: assume the worst when the reviewer omitted it.
        top_severity = "P0"

    raw_findings = parsed.get("findings")
    # Fail closed on a malformed `findings` shape: present but not a list.
    # `None`/absent is fine (no findings); a non-list scalar or dict is
    # suspicious enough to force the most-conservative effective severity.
    findings_top_malformed = raw_findings is not None and not isinstance(raw_findings, list)
    findings = raw_findings if isinstance(raw_findings, list) else []

    # Effective severity is the max of the top-level field and any blocking
    # severity in the findings list. This closes the bypass where a reviewer
    # writes `highest_severity: none` but lists a P0/P1 entry inside findings.
    # Any per-entry schema drift (non-dict, missing severity, non-string
    # severity, or unknown severity label) also forces P0 via the second
    # return value below.
    findings_severity, findings_entry_malformed = _max_severity_from_findings(findings)
    if _SEVERITY_RANK[findings_severity] > _SEVERITY_RANK[top_severity]:
        effective_severity = findings_severity
    else:
        effective_severity = top_severity

    if findings_top_malformed or findings_entry_malformed:
        # Reviewer emitted malformed `findings` data — schema violation.
        # Force P0 so the sanity override below blocks auto-merge.
        effective_severity = "P0"

    allowed = _to_bool(parsed.get("auto_merge_allowed", False))

    # Sanity override. P0 and P1 are blocking and always force allowed=false.
    # P2 is informational (per risk-policy.md "a P2 alone does not block
    # green-lane auto-merge") and stays at the reviewer's reported value.
    # Non-green risk levels still block regardless of severity.
    if effective_severity in ("P0", "P1"):
        allowed = False
    if risk != "green":
        allowed = False

    return {
        "task_id": parsed.get("task_id") or "",
        "risk_level": risk,
        "highest_severity": effective_severity,
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
