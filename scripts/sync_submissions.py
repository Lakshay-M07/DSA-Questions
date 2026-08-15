"""Entry point for the GitHub-only DSA submission synchronizer.

Platform adapters will fetch accepted submissions and normalize them into a
common record. The repository itself is the durable source of truth, so a
submission is deduplicated by platform + problem id + language.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SUBMISSIONS_FILE = DATA_DIR / "submissions.json"


@dataclass(frozen=True)
class Submission:
    platform: str
    problem_id: str
    title: str
    language: str
    source: str
    accepted_at: str
    difficulty: str | None = None
    difficulty_source: str | None = None
    primary_category: str | None = None
    tags: tuple[str, ...] = ()
    submission_id: str | None = None

    @property
    def key(self) -> str:
        return f"{self.platform.lower()}::{self.problem_id}::{self.language.lower()}"

    @property
    def source_hash(self) -> str:
        normalized = self.source.replace("\r\n", "\n").strip()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def load_records() -> dict[str, dict[str, Any]]:
    if not SUBMISSIONS_FILE.exists():
        return {}
    data = json.loads(SUBMISSIONS_FILE.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def save_records(records: dict[str, dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SUBMISSIONS_FILE.write_text(
        json.dumps(records, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def fetch_leetcode() -> list[Submission]:
    """TODO: implement authenticated LeetCode adapter."""
    return []


def fetch_codechef() -> list[Submission]:
    """TODO: implement authenticated CodeChef adapter."""
    return []


def fetch_hackerrank() -> list[Submission]:
    """TODO: implement authenticated HackerRank adapter."""
    return []


def normalize_new_submissions(
    submissions: list[Submission], records: dict[str, dict[str, Any]]
) -> list[Submission]:
    """Return only previously unseen problem/language combinations.

    The key deliberately excludes the source hash: re-submitting the same
    problem in the same language must not create another contribution.
    """
    new: list[Submission] = []
    for submission in submissions:
        existing = records.get(submission.key)
        if existing is not None:
            continue
        new.append(submission)
    return new


def main() -> None:
    records = load_records()

    submissions = fetch_leetcode()
    submissions += fetch_codechef()
    submissions += fetch_hackerrank()

    new_submissions = normalize_new_submissions(submissions, records)

    # Adapters and the repository writer will be added after platform
    # authentication/endpoint verification. Keeping this entry point safe
    # means scheduled runs currently make no speculative repository changes.
    for submission in new_submissions:
        records[submission.key] = {
            **asdict(submission),
            "tags": list(submission.tags),
            "source_hash": submission.source_hash,
        }

    if new_submissions:
        save_records(records)
        print(f"Discovered {len(new_submissions)} new accepted submission(s).")
    else:
        print("No new accepted submissions discovered.")


if __name__ == "__main__":
    main()
