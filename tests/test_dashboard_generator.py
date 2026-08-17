from datetime import datetime, timezone

from scripts.dashboard_generator import (
    END_MARKER,
    START_MARKER,
    _recent_records,
    discover_platform_records,
    platform_stats,
    render_dashboard,
    streak_stats,
    update_readme,
)


def test_platform_stats_counts_unique_problem_language_pairs():
    records = [
        {"problem_id": "1", "language": "C++", "difficulty": "Easy", "primary_category": "Array"},
        {"problem_id": "1", "language": "C++", "difficulty": "Easy", "primary_category": "Array"},
        {"problem_id": "2", "language": "Python", "difficulty": "Medium", "primary_category": "String"},
    ]
    stats = platform_stats(records)
    assert stats["solved"] == 2
    assert stats["difficulty"]["Easy"] == 1
    assert stats["difficulty"]["Medium"] == 1
    assert stats["languages"]["C++"] == 1
    assert stats["languages"]["Python"] == 1


def test_streaks_are_calculated_from_valid_timestamps_only():
    records = [
        {"accepted_at": "2026-08-14T10:00:00+00:00"},
        {"accepted_at": "2026-08-15T10:00:00+00:00"},
        {"accepted_at": "2026-08-16T10:00:00+00:00"},
        {"accepted_at": "45 min ago"},
    ]
    current, best = streak_stats(records, datetime(2026, 8, 16, tzinfo=timezone.utc))
    assert current == 3
    assert best == 3


def test_streak_is_zero_when_latest_activity_is_older_than_yesterday():
    records = [{"accepted_at": "2026-08-14T10:00:00+00:00"}]
    current, best = streak_stats(records, datetime(2026, 8, 16, tzinfo=timezone.utc))
    assert current == 0
    assert best == 1


def test_recent_records_keep_undated_platform_data():
    records = _recent_records(
        {
            "LeetCode": [{"problem_id": "1", "language": "C++", "accepted_at": "2026-08-16T10:00:00+00:00"}],
            "CodeChef": [{"problem_id": "2", "language": "C++", "accepted_at": "45 min ago"}],
        }
    )
    assert [record["problem_id"] for record in records] == ["1", "2"]


def test_hackerrank_committed_metadata_is_discovered():
    records = discover_platform_records()["HackerRank"]
    assert any(record["problem_id"] == "7876" for record in records)


def test_dashboard_contains_required_sections_and_no_solution_code():
    dashboard = render_dashboard()
    assert START_MARKER in dashboard
    assert END_MARKER in dashboard
    assert "Progress Dashboard" in dashboard
    assert "LeetCode" in dashboard
    assert "CodeChef" in dashboard
    assert "HackerRank" in dashboard
    assert "Current Streak" in dashboard
    assert "Best Streak" in dashboard
    assert "Recent Accepted Submissions" in dashboard
    assert "#include <" not in dashboard


def test_platform_cards_show_solved_once_and_use_distinct_accents():
    dashboard = render_dashboard()
    assert "LeetCode · 1 solved" not in dashboard
    assert "1 accepted problem" in dashboard
    assert "border-top:4px solid #f0b90b" in dashboard
    assert "border-top:4px solid #a855f7" in dashboard
    assert "border-top:4px solid #16c60c" in dashboard


def test_dashboard_uses_readable_metric_labels():
    dashboard = render_dashboard()
    assert "Problems Solved" in dashboard
    assert "Current Streak" in dashboard
    assert "Best Streak" in dashboard
    assert dashboard.index("Problems Solved") < dashboard.index("## Platforms")


def test_update_readme_replaces_only_generated_section():
    readme = "# Repo\n\nManual docs\n\n" + START_MARKER + "\nold\n" + END_MARKER + "\n\n## Usage\n"
    dashboard = START_MARKER + "\nnew\n" + END_MARKER
    result = update_readme(readme, dashboard)
    assert "Manual docs" in result
    assert "## Usage" in result
    assert "old" not in result
    assert "new" in result
