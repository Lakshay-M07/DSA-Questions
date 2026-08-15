from pathlib import Path

from scripts import leetcode_sync_runner as runner
from scripts.sync_submissions import Submission


def test_leetcode_slug_and_path():
    submission = Submission(
        platform="LeetCode",
        problem_id="1",
        title="Two Sum",
        language="C++",
        source="int main() {}",
        accepted_at="123",
        difficulty="Easy",
        difficulty_source="leetcode_question_metadata",
        primary_category="Array",
        tags=("Array", "Hash Table"),
    )

    path = runner.solution_path(submission)
    assert path == runner.ROOT / "LeetCode/C++/Array/Easy/1-two-sum/1-two-sum.cpp"


def test_leetcode_problem_readme_contains_metadata():
    submission = Submission(
        platform="LeetCode",
        problem_id="1",
        title="Two Sum",
        language="Python",
        source="print('ok')",
        accepted_at="123",
        difficulty="Easy",
        difficulty_source="leetcode_question_metadata",
        primary_category="Array",
        tags=("Array", "Hash Table"),
    )

    readme = runner.build_problem_readme(submission, submission.source, "Given an array of integers.")
    assert "# Two Sum" in readme
    assert "**Question ID:** `1`" in readme
    assert "Given an array of integers." in readme
    assert "print('ok')" in readme

# Re-run full wrapper verification after the import compatibility fix.
