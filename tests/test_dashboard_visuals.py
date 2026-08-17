from scripts.dashboard_generator import render_dashboard


def test_dashboard_visual_hierarchy():
    dashboard = render_dashboard()
    assert dashboard.index("DSA Progress Dashboard") < dashboard.index("Platforms")
    assert dashboard.index("Platforms") < dashboard.index("Recent Accepted Submissions")
    assert "<details" not in dashboard
    assert "LeetCode · 1 solved" not in dashboard
    assert "1 accepted problem" in dashboard
    assert "Easy 1 · Medium 0 · Hard 0" in dashboard
