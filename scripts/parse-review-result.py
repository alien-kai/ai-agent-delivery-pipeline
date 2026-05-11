#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


def get_scalar(text: str, key: str, default: str) -> str:
    m = re.search(rf"^{re.escape(key)}:\s*[\"']?([^\"'\n]+)[\"']?\s*$", text, re.MULTILINE)
    if not m:
        return default
    return m.group(1).strip()


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: parse-review-result.py codex-review.md", file=sys.stderr)
        return 2

    text = Path(sys.argv[1]).read_text(encoding="utf-8")

    risk = get_scalar(text, "risk_level", "unknown")
    highest = get_scalar(text, "highest_severity", "P1")
    allowed = get_scalar(text, "auto_merge_allowed", "false").lower()

    if allowed not in {"true", "false"}:
        allowed = "false"

    print(f"RISK_LEVEL={risk}")
    print(f"HIGHEST_SEVERITY={highest}")
    print(f"AUTO_MERGE_ALLOWED={allowed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
