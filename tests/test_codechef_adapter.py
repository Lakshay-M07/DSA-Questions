from pathlib import Path

from scripts.codechef_adapter import parse_solution_page, parse_submission_list


FIXTURE = Path(__file__).parent / "fixtures" / "codechef_submissions.html"


def test_parse_submission_list_keeps_only_accepted():
    submissions = parse_submission_list(FIXTURE.read_text(encoding="utf-8"))
    assert len(submissions) == 1
    item = submissions[0]
    assert item.submission_id == "123456789"
    assert item.problem_id == "TEST123"
    assert item.status == "Accepted"
    assert item.language == "Python"
    assert item.source_url.endswith("/viewsolution/123456789")


def test_parse_solution_page_extracts_source_and_language():
    html = """
    <html><body><div>Language: C++</div>
    <pre>#include &lt;iostream&gt;\nint main() { return 0; }</pre>
    </body></html>
    """
    source, language = parse_solution_page(html)
    assert "#include <iostream>" in source
    assert "int main()" in source
    assert language == "C++"
