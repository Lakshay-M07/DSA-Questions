from pathlib import Path

from scripts.codechef_adapter import parse_problem_metadata, parse_solution_page, parse_submission_list


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


def test_parse_current_codechef_profile_row_with_score_100():
    html = """
    <table><tbody><tr>
      <td>12:30 PM 13/08/26</td>
      <td><a href="/problems/DSACPR39">DSACPR39</a></td>
      <td>(100)</td>
      <td>C++</td>
      <td><a class="centered" href="/viewsolution/1342067959">Explain</a></td>
    </tr></tbody></table>
    """
    submissions = parse_submission_list(html)
    assert len(submissions) == 1
    item = submissions[0]
    assert item.submission_id == "1342067959"
    assert item.problem_id == "DSACPR39"
    assert item.language == "C++"


def test_parse_escaped_recent_user_markup():
    html = r'''<table><tbody><tr><td><a href="/problems/DSACPR38">DSACPR38</a></td><td>(100)</td><td>C++</td><td><a href="/viewsolution/1342054793">Explain</a></td></tr></tbody></table>'''
    submissions = parse_submission_list(html)
    assert len(submissions) == 1
    assert submissions[0].submission_id == "1342054793"
    assert submissions[0].problem_id == "DSACPR38"
    assert submissions[0].language == "C++"


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


def test_parse_problem_metadata_extracts_rating_and_tags():
    html = """
    <html><body>
      <div>Difficulty Rating 850</div>
      <a href="/practice-old/tags/arrays">Arrays</a>
      <a href="/practice-old/tags/implementation">Implementation</a>
    </body></html>
    """
    metadata = parse_problem_metadata(html)
    assert metadata.difficulty_rating == 850
    assert metadata.difficulty == "Easy"
    assert metadata.difficulty_source == "codechef_official_rating_mapping"
    assert metadata.tags == ("Arrays", "Implementation")
