from pathlib import Path

from scripts import sync_runner
from scripts.sync_submissions import Submission


def test_sync_runner_import_and_codechef_path():
    submission = Submission(
        platform="CodeChef",
        problem_id="DSACPR45",
        title="DSACPR45",
        language="C++",
        source="#include <iostream>\nint main() { return 0; }",
        accepted_at="",
        difficulty="Easy",
        primary_category="Array",
    )

    path = sync_runner.solution_path(submission)

    assert path == (
        Path(sync_runner.sync.ROOT)
        / "CodeChef"
        / "C++"
        / "Array"
        / "Easy"
        / "DSACPR45"
        / "DSACPR45.cpp"
    )


# Trigger the final metadata/path verification.
