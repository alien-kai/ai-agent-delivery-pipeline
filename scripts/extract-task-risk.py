#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

def main() -> int:
    if len(sys.argv) != 2:
        print("unknown")
        return 0
    text = Path(sys.argv[1]).read_text(encoding="utf-8")
    m = re.search(r'^risk_level:\s*["\']?([a-z]+)["\']?\s*$', text, re.M)
    print(m.group(1) if m else "unknown")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
