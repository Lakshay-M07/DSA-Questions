from scripts.dashboard_generator import render_dashboard


def test_dashboard_visual_hierarchy():
    dashboard = render_dashboard()
    assert dashboard.index("Progress Dashboard") < dashboard.index("Platforms")
    assert dashboard.index("Platforms") < dashboard.index("Recent Accepted Submissions")
    assert "<details" not in dashboard
    assert "LeetCode · 1 solved" not in dashboard
    assert "**1** solved" in dashboard
    assert "**Easy** 1 · **Medium** 0 · **Hard** 0" in dashboard
    assert "| Platform | Problem | Language | Difficulty | Topic |" in dashboard


def test_dashboard_platform_sections_are_separated():
    dashboard = render_dashboard()
    separators = [line for line in dashboard.splitlines() if line.strip() == "---"]
    assert len(separators) == 2
    first_separator = dashboard.index("\n---\n")
    second_separator = dashboard.index("\n---\n", first_separator + 1)
    assert dashboard.index("LeetCode") < first_separator < dashboard.index("CodeChef")
    assert dashboard.index("CodeChef") < second_separator < dashboard.index("HackerRank")


def test_dashboard_uses_safe_html_structure():
    dashboard = render_dashboard()
    assert "display:flex" not in dashboard
    assert "<table style=" not in dashboard
    assert "<tbody>" not in dashboard
