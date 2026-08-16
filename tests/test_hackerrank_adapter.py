from scripts.hackerrank_adapter import (
    extract_problem_metadata,
    extract_source,
    normalize_language,
    parse_submission,
    slugify,
)


def test_accepted_submission_is_normalized():
    result = parse_submission({
        "id": 12345,
        "challenge_id": 42,
        "challenge_slug": "solve-me-first",
        "challenge_name": "Solve Me First",
        "language": "C++",
        "status": "Accepted",
        "created_at": 1700000000,
    })
    assert result is not None
    assert result.submission_id == "12345"
    assert result.problem_id == "42"
    assert result.language == "C++"
    assert result.extension == ".cpp"


def test_non_accepted_submission_is_ignored():
    assert parse_submission({"id": 1, "challenge_slug": "x", "language": "Python", "status": "Wrong Answer"}) is None


def test_language_detection():
    assert normalize_language("Python 3") == ("Python", ".py")
    assert normalize_language("C++") == ("C++", ".cpp")
    assert normalize_language("JavaScript") == ("JavaScript", ".js")


def test_source_extraction_handles_nested_current_or_legacy_shape():
    payload = {"submission": {"code": "#include <iostream>\nint main() {}"}}
    assert extract_source(payload) == "#include <iostream>\nint main() {}"


def test_metadata_extraction():
    title, difficulty, category, tags, description = extract_problem_metadata({
        "name": "Arrays",
        "difficulty": {"name": "Easy"},
        "track": {"name": "Data Structures"},
        "tags": [{"name": "Array"}, {"name": "Implementation"}],
        "description": "<p>Work with <b>arrays</b>.</p>",
    })
    assert title == "Arrays"
    assert difficulty == "Easy"
    assert category == "Data Structures"
    assert tags == ("Array", "Implementation")
    assert description == "Work with\narrays."


def test_slugify():
    assert slugify("Solve Me First!") == "solve-me-first"
