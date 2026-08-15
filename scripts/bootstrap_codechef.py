"""One-time CodeChef baseline bootstrap.

Existing accepted CodeChef problem+language pairs are recorded as seen. No
source code is downloaded and no solution files are created.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.codechef_adapter import fetch_all_accepted_keys

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
BASELINE_FILE = DATA_DIR / "codechef_baseline.json"


def main() -> None:
    keys = sorted(fetch_all_accepted_keys())
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "platform": "CodeChef",
        "purpose": "Existing accepted problem-language pairs ignored by the synchronizer",
        "bootstrapped_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "keys": keys,
    }
    BASELINE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"CodeChef baseline created with {len(keys)} existing problem-language pair(s).")
    print("No source code was downloaded or committed.")


if __name__ == "__main__":
    main()
