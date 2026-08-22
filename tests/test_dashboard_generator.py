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
    assert START_MARKER not in dashboard
    assert END_MARKER not in dashboard
    assert "Progress Dashboard" in dashboard
    assert "LeetCode" in dashboard
    assert "CodeChef" in dashboard
    assert "HackerRank" in dashboard
    assert "Current streak" in dashboard
    assert "Best streak" in dashboard
    assert "Recent Accepted Submissions" in dashboard
    assert "#include <" not in dashboard


def test_platform_sections_show_solved_once_and_use_distinct_markers():
    dashboard = render_dashboard()
    assert "LeetCode · 1 solved" not in dashboard
    assert "**1** solved" in dashboard
    assert "### 🟨 LeetCode" in dashboard
    assert "### 🟪 CodeChef" in dashboard
    assert "### 🟩 HackerRank" in dashboard


def test_dashboard_uses_readable_metric_labels():
    dashboard = render_dashboard()
    assert "Total Progress" in dashboard
    assert "Current streak" in dashboard
    assert "Best streak" in dashboard
    assert dashboard.index("Total Progress") < dashboard.index("## Platforms")


def test_update_readme_replaces_only_generated_section():
    readme = "# Repo\n\nManual docs\n\n" + START_MARKER + "\nold\n" + END_MARKER + "\n\n## Usage\n"
    dashboard = "new\n"
    result = update_readme(readme, dashboard)
    assert "Manual docs" in result
    assert "## Usage" in result
    assert "old" not in result
    assert "new" in result
    assert result.count(START_MARKER) == 1
    assert result.count(END_MARKER) == 1


def test_rendered_dashboard_is_stable_when_reapplied():
    dashboard = render_dashboard()
    readme = "# Repo\n\n" + START_MARKER + "\n" + dashboard.rstrip() + "\n" + END_MARKER + "\n\n## Usage\n"
    assert update_readme(readme, dashboard) == readme
