"""Small validation helper used to catch syntax and dashboard issues before CI sync."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    generator = ROOT / "scripts" / "dashboard_generator.py"
    ast.parse(generator.read_text(encoding="utf-8"), filename=str(generator))
    print("dashboard_generator.py syntax OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
