from __future__ import annotations

import html
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.codechef_adapter as codechef_adapter
import scripts.sync_runner as base
from scripts.problem_readme import _node_to_markdown, build_problem_readme

# sync_submissions historically imported this adapter as a top-level module.
# Register the package module under that name so the module-mode runner remains
# compatible without changing the already-tested CodeChef adapter itself.
sys.modules.setdefault("codechef_adapter", codechef_adapter)

sync = base.sync


def _leetcode_slug(title: str) -> str:
    value = html.unescape(title or "").lower().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "question"


def _leetcode_question(submission: sync.Submission) -> tuple[str, str]:
    """Fetch the official LeetCode problem content using its title slug.

    LeetCode's authenticated GraphQL question object is used instead of a
    third-party mirror. If the statement cannot be retrieved, syncing the
    accepted source still succeeds and the README records the limitation.
    """
    slug = _leetcode_slug(submission.title)
    query = """
    query questionContent($titleSlug: String!) {
      question(titleSlug: $titleSlug) {
        title
        content
      }
    }
    """
    try:
        result = sync._leetcode_request(query, {"titleSlug": slug})
        question = (result.get("data") or {}).get("question") or {}
        title = str(question.get("title") or submission.title or submission.problem_id)
        content = str(question.get("content") or "")
        if content:
            node = BeautifulSoup(content, "html.parser")
            content = _node_to_markdown(node)
        return title, content
    except Exception as exc:
        print(f"LeetCode problem statement fetch skipped for {submission.problem_id}: {exc}")
        return submission.title, ""


def _problem_folder(submission: sync.Submission) -> Path:
    safe = base._safe_path_component
    slug = _leetcode_slug(submission.title)
    folder_name = safe(f"{submission.problem_id}-{slug}", "Question")
    return (
        ROOT
        / safe(submission.platform, "Platform")
        / safe(submission.language, "Unknown")
        / safe(submission.primary_category or "Other")
        / safe(submission.difficulty or "Unknown")
        / folder_name
    )


def solution_path(submission: sync.Submission) -> Path:
    folder = _problem_folder(submission)
    filename = f"{base._safe_path_component(submission.problem_id, 'Question')}-{_leetcode_slug(submission.title)}.{sync._extension(submission.language)}"
    return folder / filename


def write_solution(submission: sync.Submission) -> Path:
    path = solution_path(submission)
    path.parent.mkdir(parents=True, exist_ok=True)

    title, description = _leetcode_question(submission)
    if title and title != submission.title:
        submission = sync.Submission(
            platform=submission.platform,
            problem_id=submission.problem_id,
            title=title,
            language=submission.language,
            source=submission.source,
            accepted_at=submission.accepted_at,
            difficulty=submission.difficulty,
            difficulty_source=submission.difficulty_source,
            primary_category=submission.primary_category,
            tags=submission.tags,
            submission_id=submission.submission_id,
            difficulty_rating=submission.difficulty_rating,
        )
        path = solution_path(submission)
        path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(submission.source.rstrip() + "\n", encoding="utf-8")
    (path.parent / "README.md").write_text(
        build_problem_readme(submission, submission.source, description),
        encoding="utf-8",
    )
    return path


def commit_submission(submission: sync.Submission, path: Path) -> None:
    if submission.platform.lower() != "leetcode":
        base.commit_submission(submission, path)
        return

    sync._git(
        "add",
        str(path.relative_to(ROOT)),
        str(path.parent.joinpath("README.md").relative_to(ROOT)),
        str(sync.SUBMISSIONS_FILE.relative_to(ROOT)),
    )
    message = f"feat: add {submission.platform} - {submission.title} ({submission.language})"
    sync._git("commit", "-m", message[:180])


_original_solution_path = sync.solution_path
_original_write_solution = sync.write_solution
_original_commit_submission = sync.commit_submission


def _solution_path_dispatch(submission: sync.Submission) -> Path:
    if submission.platform.lower() == "leetcode":
        return solution_path(submission)
    return _original_solution_path(submission)


def _write_solution_dispatch(submission: sync.Submission) -> Path:
    if submission.platform.lower() == "leetcode":
        return write_solution(submission)
    return _original_write_solution(submission)


def _commit_submission_dispatch(submission: sync.Submission, path: Path) -> None:
    if submission.platform.lower() == "leetcode":
        return commit_submission(submission, path)
    return _original_commit_submission(submission, path)


sync.solution_path = _solution_path_dispatch
sync.write_solution = _write_solution_dispatch
sync.commit_submission = _commit_submission_dispatch


if __name__ == "__main__":
    sync.main()
    sync._git("push")
