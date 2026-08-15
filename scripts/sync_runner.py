from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable

from bs4 import BeautifulSoup

# Make both `python scripts/sync_runner.py` and `python -m scripts.sync_runner`
# work from the repository root. The former puts `scripts/` on sys.path, so
# imports such as `scripts.codechef_adapter` would otherwise fail.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.codechef_adapter as codechef
import scripts.sync_submissions as sync
from scripts.problem_readme import build_problem_readme, extract_problem_description


DESCRIPTION_BY_PROBLEM: dict[str, str] = {}
TITLE_BY_PROBLEM: dict[str, str] = {}


_original_solution_path = sync.solution_path
_original_write_solution = sync.write_solution
_original_commit_submission = sync.commit_submission
_original_migrate = sync.migrate_legacy_records


def _safe_path_component(value: str, fallback: str = "Other") -> str:
    # Preserve language symbols such as C++ in directory names.
    value = re.sub(r"[^A-Za-z0-9._ +#-]+", "", value).strip()
    value = re.sub(r"\s+", "-", value)
    return value[:100] or fallback


def _problem_path(submission: sync.Submission) -> Path:
    return (
        sync.ROOT
        / _safe_path_component(submission.platform, "Platform")
        / _safe_path_component(submission.language, "Unknown")
        / _safe_path_component(submission.primary_category or "Other")
        / _safe_path_component(submission.difficulty or "Unknown")
        / _safe_path_component(submission.problem_id or submission.title, "Question")
    )


def solution_path(submission: sync.Submission) -> Path:
    if submission.platform.lower() != "codechef":
        return _original_solution_path(submission)
    problem_dir = _problem_path(submission)
    filename = f"{_safe_path_component(submission.problem_id or submission.title, 'Question')}.{sync._extension(submission.language)}"
    return problem_dir / filename


def _fallback_codechef_metadata(html_text: str, problem_id: str) -> tuple[str, str]:
    """Use CodeChef's own metadata if the full statement is unavailable."""
    soup = BeautifulSoup(html_text, "html.parser")
    meta = soup.select_one('meta[name="description"]')
    description = (meta.get("content", "") if meta else "").strip()
    title = ""
    if description:
        match = re.search(r"our\s+(.+?)\s+practice\s+problem", description, re.I)
        if match:
            title = re.sub(r"\s+", " ", match.group(1)).strip()
    return title, description


def _fetch_problem_descriptions(problem_ids: Iterable[str]) -> None:
    wanted = [problem_id for problem_id in dict.fromkeys(problem_ids) if problem_id and problem_id not in DESCRIPTION_BY_PROBLEM]
    if not wanted:
        return

    username, password = codechef._credentials()
    driver = codechef.build_driver()
    try:
        codechef._login(driver, username, password)
        for problem_id in wanted:
            driver.get(f"{codechef.BASE_URL}/problems/{codechef.quote(problem_id)}")
            codechef.WebDriverWait(driver, 25).until(
                codechef.EC.presence_of_element_located((codechef.By.TAG_NAME, "body"))
            )

            page_html = driver.page_source
            description = extract_problem_description(page_html)
            title = codechef.extract_problem_title(page_html, problem_id)

            if not description:
                fallback_title, fallback_description = _fallback_codechef_metadata(page_html, problem_id)
                description = fallback_description
                if fallback_title:
                    title = fallback_title

            if not description:
                description = (
                    f"The full problem statement for `{problem_id}` is not currently "
                    "available from CodeChef's public problem page."
                )

            if not title or title == problem_id:
                fallback_title, _ = _fallback_codechef_metadata(page_html, problem_id)
                if fallback_title:
                    title = fallback_title

            DESCRIPTION_BY_PROBLEM[problem_id] = description
            TITLE_BY_PROBLEM[problem_id] = title or problem_id
    finally:
        driver.quit()


def write_solution(submission: sync.Submission) -> Path:
    if submission.platform.lower() != "codechef":
        path = _original_solution_path(submission)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(submission.source.rstrip() + "\n", encoding="utf-8")
        return path

    _fetch_problem_descriptions([submission.problem_id])

    path = solution_path(submission)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(submission.source.rstrip() + "\n", encoding="utf-8")

    description = DESCRIPTION_BY_PROBLEM.get(submission.problem_id, "")
    readme = path.parent / "README.md"
    readme.write_text(
        build_problem_readme(submission, submission.source, description),
        encoding="utf-8",
    )
    return path


def commit_submission(submission: sync.Submission, path: Path) -> None:
    if submission.platform.lower() != "codechef":
        _original_commit_submission(submission, path)
        return

    sync._git(
        "add",
        str(path.relative_to(sync.ROOT)),
        str(path.parent.joinpath("README.md").relative_to(sync.ROOT)),
        str(sync.SUBMISSIONS_FILE.relative_to(sync.ROOT)),
    )
    message = f"feat: add {submission.platform} - {submission.title} ({submission.language})"
    sync._git("commit", "-m", message[:180])


def migrate_legacy_records(records):
    changed = _original_migrate(records)
    codechef_records = [
        record
        for record in records.values()
        if record.get("platform") == "CodeChef" and record.get("problem_id")
    ]

    if codechef_records:
        needs_readme = []
        for record in codechef_records:
            problem_id = str(record.get("problem_id") or "")
            submission = sync.Submission(
                platform="CodeChef",
                problem_id=problem_id,
                title=str(record.get("title") or problem_id or "Question"),
                language=str(record.get("language") or "Unknown"),
                source=str(record.get("source") or ""),
                accepted_at=str(record.get("accepted_at") or ""),
                difficulty=record.get("difficulty"),
                difficulty_source=record.get("difficulty_source"),
                primary_category=record.get("primary_category"),
                tags=tuple(record.get("tags") or ()),
                submission_id=record.get("submission_id"),
                difficulty_rating=record.get("difficulty_rating"),
            )
            path = solution_path(submission)
            readme = path.parent / "README.md"
            if not readme.exists():
                needs_readme.append((record, submission, path, readme))

        _fetch_problem_descriptions(submission.problem_id for _, submission, _, _ in needs_readme)
        for record, submission, path, readme in needs_readme:
            title = TITLE_BY_PROBLEM.get(submission.problem_id, submission.title)
            if title and title != submission.problem_id and record.get("title") != title:
                record["title"] = title
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

            path.parent.mkdir(parents=True, exist_ok=True)
            readme.write_text(
                build_problem_readme(
                    submission,
                    submission.source,
                    DESCRIPTION_BY_PROBLEM[submission.problem_id],
                ),
                encoding="utf-8",
            )
            changed = True

    return changed


sync.solution_path = solution_path
sync.write_solution = write_solution
sync.commit_submission = commit_submission
sync.migrate_legacy_records = migrate_legacy_records


if __name__ == "__main__":
    sync.main()
