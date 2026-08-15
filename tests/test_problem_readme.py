from types import SimpleNamespace

from scripts.problem_readme import build_problem_readme, extract_problem_description


def test_extract_problem_description_from_statement_container():
    html = """
    <main>
      <div class="problem-statement">
        <h1>Declaring string arrays</h1>
        <p>To declare an array containing numbers, we do this</p>
        <pre>int num[5] = {1, 2, 3, 4, 5};</pre>
        <h2>Task</h2>
        <p>Create an array of the first 4 months of the year.</p>
        <h2>Input</h2>
        <p>There is no input.</p>
        <h2>Output</h2>
        <p>Print the third month.</p>
      </div>
    </main>
    """
    result = extract_problem_description(html, "Declaring string arrays")
    assert "To declare an array containing numbers" in result
    assert "```" in result
    assert "### Task" in result
    assert "### Input" in result
    assert "### Output" in result
    assert "Declaring string arrays" not in result.splitlines()[0:1]


def test_build_problem_readme_contains_question_and_solution():
    submission = SimpleNamespace(
        title="Declaring string arrays",
        problem_id="DSACPR38",
        difficulty="Easy",
        primary_category="Array",
        tags=("Arrays", "Basic Programming Concepts"),
        language="C++",
        accepted_at="2026-08-13T06:52:08Z",
    )
    readme = build_problem_readme(
        submission,
        '#include <iostream>\nint main() { return 0; }',
        "Create an array of the first four months of the year.",
    )
    assert "# Declaring string arrays" in readme
    assert "**Question ID:** `DSACPR38`" in readme
    assert "## Problem" in readme
    assert "Create an array of the first four months" in readme
    assert "## Solution" in readme
    assert "```cpp" in readme
