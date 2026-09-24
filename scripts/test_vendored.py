#!/usr/bin/env python3
"""Vendored copies of design_tokens.py must be byte-identical to the canonical one.

Skills install independently (`npx skills add ... --skill X`), so each skill
that reads the design system ships its own copy of the loader. This check
keeps the copies from drifting. Fix a failure by re-copying the canonical file:
    cp skills/diagram-design-system/scripts/design_tokens.py skills/<name>/scripts/
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANON = ROOT / "skills/diagram-design-system/scripts/design_tokens.py"


def main() -> int:
    want = CANON.read_bytes()
    copies = [p for p in ROOT.glob("skills/*/scripts/design_tokens.py") if p != CANON]
    stale = [p for p in copies if p.read_bytes() != want]
    for p in stale:
        print(f"FAIL: {p.relative_to(ROOT)} differs from {CANON.relative_to(ROOT)}")
    if not copies:
        print("FAIL: no vendored copies found")
        return 1
    if not stale:
        print(f"OK: {len(copies)} vendored design_tokens.py copies match")
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
