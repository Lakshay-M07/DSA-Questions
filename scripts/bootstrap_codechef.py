"""One-time CodeChef baseline bootstrap.

Existing accepted CodeChef problem+language pairs are recorded as seen. No
source code is downloaded and no solution files are created.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.codechef_adapter import fetch_all_accepted_keys

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
BASELINE_FILE = DATA_DIR / "codechef_baseline.json"


def main() -> None:
    if BASELINE_FILE.exists():
        raise SystemExit("CodeChef baseline already exists; refusing to overwrite it.")

    keys = sorted(fetch_all_accepted_keys())
    if not keys:
        raise SystemExit(
            "CodeChef baseline returned zero accepted problem-language pairs. "
            "Refusing to create an empty baseline so existing solutions cannot be backfilled accidentally."
        )

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "platform": "CodeChef",
        "purpose": "Existing accepted problem-language pairs ignored by the synchronizer",
        "bootstrapped_at": datetime.now(timezone.utc).isoformat(),
        "keys": keys,
    }
    BASELINE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"CodeChef baseline created with {len(keys)} existing problem-language pair(s).")
    print("No source code was downloaded or committed.")


if __name__ == "__main__":
    main()
