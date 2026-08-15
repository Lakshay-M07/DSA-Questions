"""GitHub-only DSA submission synchronizer."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SUBMISSIONS_FILE = DATA_DIR / "submissions.json"
CODECHEF_BASELINE_FILE = DATA_DIR / "codechef_baseline.json"
LEETCODE_ENDPOINT = "https://leetcode.com/graphql"


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
    difficulty_rating: int | None = None

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
    SUBMISSIONS_FILE.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_codechef_baseline() -> set[str]:
    if not CODECHEF_BASELINE_FILE.exists():
        return set()
    data = json.loads(CODECHEF_BASELINE_FILE.read_text(encoding="utf-8"))
    return set(data.get("keys") or []) if isinstance(data, dict) else set()


def _leetcode_request(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    session = os.environ.get("LEETCODE_SESSION")
    csrf = os.environ.get("LEETCODE_CSRF_TOKEN")
    if not session or not csrf:
        raise RuntimeError("LeetCode authentication secrets are not available.")

    payload = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    request = urllib.request.Request(
        LEETCODE_ENDPOINT,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": "https://leetcode.com",
            "Referer": "https://leetcode.com/",
            "x-csrftoken": csrf,
            "Cookie": f"LEETCODE_SESSION={session}; csrftoken={csrf}",
            "User-Agent": "Mozilla/5.0 GitHubActions-DsaQuestions/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"LeetCode HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("LeetCode network request failed") from exc
    if result.get("errors"):
        raise RuntimeError("LeetCode GraphQL returned an error")
    return result


def leetcode_auth_smoke_test() -> str:
    query = """
    query {
      userStatus {
        isSignedIn
        username
      }
    }
    """
    result = _leetcode_request(query)
    status = (result.get("data") or {}).get("userStatus") or {}
    if not status.get("isSignedIn"):
        raise RuntimeError("LeetCode authentication was rejected.")
    return status.get("username") or "unknown"


def _leetcode_recent_accepted(limit: int = 20) -> list[dict[str, Any]]:
    query = """
    query recentAccepted($username: String!, $limit: Int!) {
      recentAcSubmissionList(username: $username, limit: $limit) {
        id
        title
        titleSlug
        timestamp
      }
    }
    """
    username = leetcode_auth_smoke_test()
    result = _leetcode_request(query, {"username": username, "limit": limit})
    return ((result.get("data") or {}).get("recentAcSubmissionList") or [])


def _leetcode_submission_details(submission_id: str) -> dict[str, Any]:
    query = """
    query submissionDetails($submissionId: Int!) {
      submissionDetails(submissionId: $submissionId) {
        code
        timestamp
        statusCode
        lang { name verboseName }
        question {
          questionId
          title
          titleSlug
          difficulty
          topicTags { name slug }
        }
      }
    }
    """
    result = _leetcode_request(query, {"submissionId": int(submission_id)})
    details = (result.get("data") or {}).get("submissionDetails")
    if not details:
        raise RuntimeError(f"LeetCode submission details unavailable for {submission_id}")
    return details


def _canonical_language(name: str) -> str:
    mapping = {
        "c": "C", "cpp": "C++", "c++": "C++", "python": "Python",
        "python3": "Python", "javascript": "JavaScript", "java": "Java",
    }
    return mapping.get(name.strip().lower(), name.strip())


def _difficulty(value: str | None) -> str | None:
    return value if value in {"Easy", "Medium", "Hard"} else None


def _extension(language: str) -> str:
    return {"C": "c", "C++": "cpp", "Python": "py", "JavaScript": "js", "Java": "java"}.get(language, "txt")


def _primary_category(tags: tuple[str, ...]) -> str:
    priority = [
        "Array", "String", "Hash Table", "Two Pointers", "Binary Search",
        "Linked List", "Stack", "Queue", "Tree", "Graph", "Dynamic Programming",
        "Greedy", "Backtracking", "Heap",
    ]
    lowered = {tag.lower(): tag for tag in tags}
    for preferred in priority:
        if preferred.lower() in lowered:
            return preferred
    return tags[0] if tags else "Other"


def fetch_leetcode() -> list[Submission]:
    submissions: list[Submission] = []
    for item in _leetcode_recent_accepted(limit=20):
        submission_id = str(item.get("id", ""))
        if not submission_id:
            continue
        details = _leetcode_submission_details(submission_id)
        if details.get("statusCode") != 10:
            continue
        question = details.get("question") or {}
        language = _canonical_language((details.get("lang") or {}).get("name", ""))
        tags = tuple(t.get("name", "") for t in (question.get("topicTags") or []) if t.get("name"))
        submissions.append(Submission(
            platform="LeetCode",
            problem_id=str(question.get("questionId") or question.get("titleSlug") or submission_id),
            title=question.get("title") or item.get("title") or "Unknown",
            language=language,
            source=details.get("code") or "",
            accepted_at=str(details.get("timestamp") or item.get("timestamp") or ""),
            difficulty=_difficulty(question.get("difficulty")),
            difficulty_source="leetcode_question_metadata",
            primary_category=_primary_category(tags),
            tags=tags,
            submission_id=submission_id,
        ))
    return submissions


def fetch_codechef() -> list[Submission]:
    """Fetch new CodeChef data only after the existing-account baseline exists."""
    if not CODECHEF_BASELINE_FILE.exists():
        print("CodeChef baseline not found; skipping CodeChef sync to prevent backfill.")
        return []

    from scripts.codechef_adapter import fetch_recent_accepted_details

    submissions: list[Submission] = []
    for detail in fetch_recent_accepted_details(limit=20):
        raw = detail.raw
        metadata = detail.metadata
        tags = tuple(metadata.tags)
        submissions.append(Submission(
            platform="CodeChef",
            problem_id=raw.problem_id,
            title=raw.title or raw.problem_id,
            language=detail.language,
            source=detail.source,
            accepted_at=raw.accepted_at,
            difficulty=metadata.difficulty,
            difficulty_source=metadata.difficulty_source,
            primary_category=_primary_category(tags),
            tags=tags,
            submission_id=raw.submission_id,
            difficulty_rating=metadata.difficulty_rating,
        ))
    return submissions


def fetch_hackerrank() -> list[Submission]:
    return []


def normalize_new_submissions(submissions: list[Submission], records: dict[str, dict[str, Any]], baseline_keys: set[str]) -> list[Submission]:
    new: list[Submission] = []
    for submission in submissions:
        if submission.key in records or submission.key in baseline_keys:
            continue
        new.append(submission)
    return new


def _safe_component(value: str, fallback: str = "Other") -> str:
    value = re.sub(r"[^A-Za-z0-9._ -]+", "", value).strip()
    value = re.sub(r"\s+", "-", value)
    return value[:100] or fallback


def solution_path(submission: Submission) -> Path:
    platform = _safe_component(submission.platform)
    language = _safe_component(submission.language)
    category = _safe_component(submission.primary_category or "Other")
    difficulty = _safe_component(submission.difficulty or "Unknown")
    filename = f"{_safe_component(submission.problem_id)}-{_safe_component(submission.title, submission.problem_id)}.{_extension(submission.language)}"
    return ROOT / platform / language / category / difficulty / filename


def write_solution(submission: Submission) -> Path:
    path = solution_path(submission)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(submission.source.rstrip() + "\n", encoding="utf-8")
    return path


def record_submission(records: dict[str, dict[str, Any]], submission: Submission) -> None:
    records[submission.key] = {
        **asdict(submission),
        "tags": list(submission.tags),
        "source_hash": submission.source_hash,
        "solution_path": str(solution_path(submission).relative_to(ROOT)),
    }


def _git(*args: str) -> None:
    subprocess.run(["git", *args], cwd=ROOT, check=True)


def commit_submission(submission: Submission, path: Path) -> None:
    _git("add", str(path.relative_to(ROOT)), str(SUBMISSIONS_FILE.relative_to(ROOT)))
    message = f"feat: add {submission.platform} - {submission.title} ({submission.language})"
    _git("commit", "-m", message[:180])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--leetcode-smoke", action="store_true")
    parser.add_argument("--leetcode-read-only", action="store_true")
    args = parser.parse_args()

    if args.leetcode_smoke:
        username = leetcode_auth_smoke_test()
        print(f"LeetCode authentication successful for username: {username}")
        print("Read-only authentication test passed; repository was not modified.")
        return

    if args.leetcode_read_only:
        username = leetcode_auth_smoke_test()
        submissions = fetch_leetcode()
        print(f"Authenticated LeetCode account: {username}")
        print(f"Recent accepted submissions returned: {len(submissions)}")
        print("Read-only LeetCode fetch passed; repository was not modified.")
        return

    records = load_records()
    baseline_keys = load_codechef_baseline()
    fetched = fetch_leetcode() + fetch_codechef() + fetch_hackerrank()
    new_submissions = normalize_new_submissions(fetched, records, baseline_keys)

    if not new_submissions:
        print("No new accepted submissions discovered.")
        return

    # Each new accepted problem/language gets its own Git commit. A single
    # workflow run can therefore produce 10+ qualifying commits if 10 new
    # accepted submissions arrived since the previous poll.
    for submission in new_submissions:
        path = write_solution(submission)
        record_submission(records, submission)
        save_records(records)
        commit_submission(submission, path)
        print(f"Committed {submission.platform}: {submission.problem_id} / {submission.language}")

    _git("push")
    print(f"Pushed {len(new_submissions)} separate submission commit(s).")


if __name__ == "__main__":
    main()
