import json
import os
import subprocess
from pathlib import Path
from typing import Any

from scripts.hackerrank_adapter import (
    HackerRankClient,
    HackerRankSubmission,
    extract_problem_metadata,
    extract_source,
    slugify,
    parse_submission,
)

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "data" / "hackerrank_imports.json"


def git(*args: str) -> None:
    subprocess.run(["git", *args], cwd=ROOT, check=True)


def load_state() -> set[str]:
    if not STATE_PATH.exists():
        return set()
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    return set(data.get("accepted_keys", [])) if isinstance(data, dict) else set()


def save_state(keys: set[str]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps({"accepted_keys": sorted(keys)}, indent=2) + "\n", encoding="utf-8")


def difficulty_from_metadata(data: dict[str, Any]) -> str | None:
    _, difficulty, _, _, _ = extract_problem_metadata(data)
    if difficulty in {"Easy", "Medium", "Hard"}:
        return difficulty
    candidates = []

    def walk(value: Any):
        if isinstance(value, dict):
            for key, child in value.items():
                if "difficult" in str(key).lower() or str(key).lower() in {"rating", "score"}:
                    candidates.append(child)
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(data)
    for value in candidates:
        try:
            rating = float(value)
        except (TypeError, ValueError):
            continue
        if rating <= 2:
            return "Easy"
        if rating <= 3:
            return "Medium"
        if rating <= 5:
            return "Hard"
    return None


def category_from_metadata(data: dict[str, Any]) -> str:
    _, _, category, tags, _ = extract_problem_metadata(data)
    if category:
        return category
    for key in ("track", "domain", "category"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            name = value.get("name") or value.get("label") or value.get("slug")
            if name:
                return str(name)
    if tags:
        return tags[0]
    return "Other"


def build_readme(
    problem: HackerRankSubmission,
    difficulty: str,
    category: str,
    tags: tuple[str, ...],
    description: str | None,
    source_filename: str,
) -> str:
    lines = [
        f"# {problem.title}",
        "",
        "- **Platform:** HackerRank",
        f"- **Question ID:** {problem.problem_id}",
        f"- **Difficulty:** {difficulty}",
        f"- **Category:** {category}",
        f"- **Language:** {problem.language}",
    ]
    if tags:
        lines.append(f"- **Tags:** {', '.join(tags)}")
    if problem.submitted_at:
        lines.append(f"- **Submitted:** {problem.submitted_at}")
    lines += [
        "",
        "## Question",
        "",
        description or "Problem description was not exposed by the current HackerRank endpoint.",
        "",
        "## Solution",
        "",
        f"See `{source_filename}` in this directory.",
        "",
    ]
    return "\n".join(lines)


def import_one(client: HackerRankClient, submission: HackerRankSubmission, state: set[str]) -> bool:
    key = f"hackerrank::{submission.problem_id}::{submission.language}"
    if key in state:
        return False

    source_payload = client.fetch_submission_source(submission.slug, submission.submission_id)
    source = extract_source(source_payload)
    if not source:
        raise RuntimeError(f"Could not retrieve source for HackerRank submission {submission.submission_id}")

    challenge = client.fetch_challenge(submission.slug)
    title, _, category, tags, description = extract_problem_metadata(challenge)
    difficulty = difficulty_from_metadata(challenge)
    if not difficulty:
        raise RuntimeError(
            f"No authoritative/classifiable difficulty found for HackerRank problem {submission.slug}; refusing to guess"
        )

    if title:
        submission = HackerRankSubmission(**{**submission.__dict__, "title": title})
    category = category or category_from_metadata(challenge)

    question_folder = f"{submission.problem_id}-{slugify(submission.title)}"
    folder = ROOT / "HackerRank" / submission.language / slugify(category) / difficulty / question_folder
    folder.mkdir(parents=True, exist_ok=True)
    source_filename = f"{question_folder}{submission.extension}"
    source_path = folder / source_filename
    readme_path = folder / "README.md"

    source_path.write_text(source, encoding="utf-8")
    readme_path.write_text(
        build_readme(submission, difficulty, category, tags, description, source_filename),
        encoding="utf-8",
    )
    state.add(key)
    save_state(state)
    git(
        "add",
        str(source_path.relative_to(ROOT)),
        str(readme_path.relative_to(ROOT)),
        str(STATE_PATH.relative_to(ROOT)),
    )
    git("commit", "-m", "Add HackerRank: " + submission.title + " (" + submission.language + ")")
    git("push")
    return True


def main() -> None:
    email = os.environ.get("HACKERRANK_EMAIL")
    password = os.environ.get("HACKERRANK_PASSWORD")
    session_id = os.environ.get("HACKERRANK_SESSION_ID")
    if not session_id and (not email or not password):
        raise SystemExit("HACKERRANK_SESSION_ID or HACKERRANK_EMAIL/HACKERRANK_PASSWORD secrets are required")
    client = HackerRankClient(email, password, session_id=session_id)
    state = load_state()
    records = client.fetch_submissions(limit=1000)
    accepted = []
    for record in records:
        parsed = parse_submission(record)
        if parsed:
            accepted.append(parsed)
    accepted.sort(key=lambda x: x.submitted_at or "")
    imported = 0
    for submission in accepted:
        if import_one(client, submission, state):
            imported += 1
    print(f"HackerRank: {len(accepted)} Accepted records in returned page; {imported} newly imported.")


if __name__ == "__main__":
    main()
