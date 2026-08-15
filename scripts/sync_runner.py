from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import scripts.codechef_adapter as codechef
import scripts.sync_submissions as sync
from scripts.problem_readme import build_problem_readme, extract_problem_description


DESCRIPTION_BY_PROBLEM: dict[str, str] = {}


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
    problem_dir = _problem_path(submission)
    filename = f"{_safe_path_component(submission.problem_id or submission.title, 'Question')}.{sync._extension(submission.language)}"
    return problem_dir / filename


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
            description = extract_problem_description(driver.page_source)
            if not description:
                raise codechef.CodeChefAuthError(
                    f"Could not extract problem statement for CodeChef problem {problem_id}; url={driver.current_url!r}"
                )
            DESCRIPTION_BY_PROBLEM[problem_id] = description
    finally:
        driver.quit()


# The existing CodeChef adapter continues to handle authentication, accepted
# submissions, source extraction, title, difficulty, and tags. This runner only
# adds the problem-statement/documentation layer around that adapter.
_original_fetch_details = codechef.fetch_recent_accepted_details


def fetch_recent_accepted_details(limit: int = 20):
    return _original_fetch_details(limit)


codechef.fetch_recent_accepted_details = fetch_recent_accepted_details


def write_solution(submission: sync.Submission) -> Path:
    # Only fetch a statement for a submission that survived duplicate/baseline
    # filtering and is actually going to be written to the repository.
    _fetch_problem_descriptions([submission.problem_id])

    path = solution_path(submission)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(submission.source.rstrip() + "\n", encoding="utf-8")

    description = DESCRIPTION_BY_PROBLEM.get(submission.problem_id, "")
    if not description:
        raise codechef.CodeChefAuthError(f"Problem statement missing for {submission.problem_id}")

    readme = path.parent / "README.md"
    readme.write_text(
        build_problem_readme(submission, submission.source, description),
        encoding="utf-8",
    )
    return path


def commit_submission(submission: sync.Submission, path: Path) -> None:
    sync._git(
        "add",
        str(path.relative_to(sync.ROOT)),
        str(path.parent.joinpath("README.md").relative_to(sync.ROOT)),
        str(sync.SUBMISSIONS_FILE.relative_to(sync.ROOT)),
    )
    message = f"feat: add {submission.platform} - {submission.title} ({submission.language})"
    sync._git("commit", "-m", message[:180])


_original_migrate = sync.migrate_legacy_records


def migrate_legacy_records(records):
    changed = _original_migrate(records)
    codechef_records = [
        record
        for record in records.values()
        if record.get("platform") == "CodeChef" and record.get("problem_id")
    ]

    if codechef_records:
        _fetch_problem_descriptions(record["problem_id"] for record in codechef_records)
        for record in codechef_records:
            submission = sync.Submission(
                platform="CodeChef",
                problem_id=str(record.get("problem_id") or ""),
                title=str(record.get("title") or record.get("problem_id") or "Question"),
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
            path.parent.mkdir(parents=True, exist_ok=True)
            readme = path.parent / "README.md"
            if not readme.exists():
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


# Patch only the orchestration layer; the existing platform adapters and
# duplicate/difficulty logic remain unchanged.
sync.solution_path = solution_path
sync.write_solution = write_solution
sync.commit_submission = commit_submission
sync.migrate_legacy_records = migrate_legacy_records


if __name__ == "__main__":
    sync.main()
