from __future__ import annotations

import html
import re
from bs4 import BeautifulSoup, Tag


SECTION_HEADINGS = {
    "problem statement", "task", "input", "input format", "output", "output format",
    "constraints", "sample", "sample input", "sample output", "example", "examples", "explanation",
}


def _normalize(value: str) -> str:
    return html.unescape(value.replace(r"\/", "/"))


def _node_to_markdown(node: Tag) -> str:
    # Work on a copy so extracting the statement never mutates the page tree.
    node = BeautifulSoup(str(node), "html.parser")
    for bad in node.select("script,style,noscript,header,footer,nav,button,form,aside"):
        bad.decompose()

    for br in node.find_all("br"):
        br.replace_with("\n")

    for pre in node.find_all("pre"):
        code = pre.get_text("\n", strip=False).strip()
        pre.replace_with(f"\n```\n{code}\n```\n")

    for code in node.find_all("code"):
        if code.parent and code.parent.name == "pre":
            continue
        value = code.get_text(" ", strip=True)
        code.replace_with(f"`{value}`")

    for strong in node.find_all(["strong", "b"]):
        value = strong.get_text(" ", strip=True)
        strong.replace_with(f"**{value}**")

    for em in node.find_all(["em", "i"]):
        value = em.get_text(" ", strip=True)
        em.replace_with(f"*{value}*")

    for li in node.find_all("li"):
        value = li.get_text(" ", strip=True)
        li.clear()
        li.append("- " + value)

    text = node.get_text("\n", strip=False)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    out: list[str] = []
    for line in lines:
        if line or (out and out[-1]):
            out.append(line)

    text = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()

    formatted: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower() in SECTION_HEADINGS:
            if formatted and formatted[-1] != "":
                formatted.append("")
            formatted.append(f"### {stripped}")
        else:
            formatted.append(line)

    return re.sub(r"\n{3,}", "\n\n", "\n".join(formatted)).strip()


def extract_problem_description(html_text: str, title: str = "") -> str:
    """Extract the rendered CodeChef problem statement as Markdown-friendly text.

    CodeChef has used multiple problem-page layouts, so this intentionally checks
    both explicit problem-statement containers and rendered main/article sections.
    """
    soup = BeautifulSoup(_normalize(html_text), "html.parser")
    selectors = [
        "#problem-statement", ".problem-statement", "[id*='problem-statement']",
        "[class*='problem-statement']", "[id*='problem_statement']", "[class*='problem_statement']",
        "[data-testid*='problem-statement']", "[data-testid*='problemStatement']",
        "[class*='problem-description']", "[class*='problemDescription']",
    ]

    candidates: list[tuple[float, str]] = []
    for selector in selectors:
        for node in soup.select(selector):
            text = _node_to_markdown(node)
            if len(text) >= 100:
                candidates.append((3.0, text))

    if not candidates:
        for node in soup.find_all(["main", "article", "section"]):
            text = _node_to_markdown(node)
            if len(text) < 100:
                continue
            low = text.lower()
            markers = sum(low.count(x) for x in ("input", "output", "constraints", "sample", "explanation", "task"))
            chrome = sum(low.count(x) for x in ("login", "sign up", "practice", "compete", "leaderboard", "discuss"))
            if markers >= 2:
                candidates.append((markers * 2 - chrome / 3, text))

    if not candidates:
        return ""

    candidates.sort(key=lambda item: (item[0], min(len(item[1]), 12000)), reverse=True)
    text = candidates[0][1]

    if title:
        lines = text.splitlines()
        if lines and re.sub(r"[^a-z0-9]+", "", lines[0].lower()) == re.sub(r"[^a-z0-9]+", "", title.lower()):
            text = "\n".join(lines[1:]).strip()

    return text


def _language_fence(language: str) -> str:
    return {
        "C++": "cpp",
        "C": "c",
        "Python": "python",
        "JavaScript": "javascript",
        "Java": "java",
    }.get(language, "")


def build_problem_readme(submission, source: str, description: str) -> str:
    tags = ", ".join(submission.tags) if submission.tags else "None"
    statement = description or "Problem statement could not be extracted from CodeChef on this run."
    code = source.rstrip()
    return f"""# {submission.title or submission.problem_id}

**Question ID:** `{submission.problem_id}`  
**Difficulty:** {submission.difficulty or 'Unknown'}  
**Category:** {submission.primary_category or 'Other'}  
**Tags:** {tags}  
**Language:** {submission.language}  
**Submitted:** {submission.accepted_at or 'Unknown'}

## Problem

{statement}

## Solution

```{_language_fence(submission.language)}
{code}
```
"""
