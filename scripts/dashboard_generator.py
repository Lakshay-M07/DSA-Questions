"""Generate the repository's static progress dashboard from committed data."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SUBMISSIONS_PATH = ROOT / "data" / "submissions.json"
README_PATH = ROOT / "README.md"

START_MARKER = "<!-- DASHBOARD:START -->"
END_MARKER = "<!-- DASHBOARD:END -->"
PLATFORMS = ("LeetCode", "CodeChef", "HackerRank")


def _load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def load_submissions() -> dict[str, dict[str, Any]]:
    data = _load_json(SUBMISSIONS_PATH, {})
    if not isinstance(data, dict):
        raise ValueError("data/submissions.json must contain an object")
    return {str(key): value for key, value in data.items() if isinstance(value, dict)}


def _discover_platform_records() -> dict[str, list[dict[str, Any]]]:
    records = defaultdict(list)
    for record in load_submissions().values():
        platform = str(record.get("platform") or "").strip()
        if platform in PLATFORMS:
            records[platform].append(record)

    # HackerRank is currently tracked outside data/submissions.json, so only
    # count a committed submission when a problem source file exists. This
    # avoids inventing metadata from the dedupe state alone.
    hr_root = ROOT / "HackerRank"
    if hr_root.exists():
        for source_path in hr_root.rglob("*"):
            if not source_path.is_file() or source_path.name == "README.md":
                continue
            parts = source_path.relative_to(hr_root).parts
            if len(parts) < 4:
                continue
            language, category, difficulty = parts[:3]
            problem_dir = source_path.parent.name
            if not re.match(r"^[^-]+-.+", problem_dir):
                continue
            problem_id, title_slug = problem_dir.split("-", 1)
            records["HackerRank"].append(
                {
                    "platform": "HackerRank",
                    "problem_id": problem_id,
                    "title": title_slug.replace("-", " ").title(),
                    "language": language,
                    "difficulty": difficulty if difficulty in {"Easy", "Medium", "Hard"} else None,
                    "primary_category": category.replace("-", " ").title(),
                    "accepted_at": "",
                }
            )

    return records


def _unique_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, Any]] = []
    for record in records:
        key = (str(record.get("problem_id") or ""), str(record.get("language") or ""))
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
    return unique


def _platform_stats(records: list[dict[str, Any]]) -> dict[str, Any]:
    unique = _unique_records(records)
    difficulty = Counter(str(r.get("difficulty")) for r in unique if r.get("difficulty") in {"Easy", "Medium", "Hard"})
    languages = Counter(str(r.get("language")) for r in unique if r.get("language"))
    categories = Counter(str(r.get("primary_category")) for r in unique if r.get("primary_category"))
    return {
        "solved": len(unique),
        "difficulty": difficulty,
        "languages": languages,
        "categories": categories,
        "records": unique,
    }


def _progress_bar(value: int, total: int, width: int = 10) -> str:
    if total <= 0:
        return "░" * width
    filled = round(width * value / total)
    return "█" * filled + "░" * (width - filled)


def _logo(platform: str) -> str:
    return {"LeetCode": "🟨", "CodeChef": "🟪", "HackerRank": "🟩"}[platform]


def _format_counter(counter: Counter[str]) -> str:
    if not counter:
        return "—"
    return " · ".join(f"{key}: **{value}**" for key, value in counter.most_common())


def _platform_card(platform: str, stats: dict[str, Any]) -> str:
    solved = stats["solved"]
    difficulty = stats["difficulty"]
    languages = stats["languages"]
    categories = stats["categories"]
    difficulty_parts = " · ".join(
        f"**{level}** {difficulty.get(level, 0)}" for level in ("Easy", "Medium", "Hard")
    )
    return "\n".join(
        [
            f"### {_logo(platform)} {platform}",
            "",
            f"**{solved}** solved",
            "",
            f"{difficulty_parts}",
            "",
            f"**Languages:** {_format_counter(languages)}",
            "",
            f"**Categories:** {_format_counter(categories)}",
        ]
    )


def _recent_records(platform_records: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for platform, records in platform_records.items():
        for record in records:
            rows.append({**record, "platform": platform})
    with_date = [row for row in rows if str(row.get("accepted_at") or "").strip()]
    if with_date:
        with_date.sort(key=lambda row: str(row.get("accepted_at") or ""), reverse=True)
        return with_date
    return rows


def render_dashboard() -> str:
    platform_records = _discover_platform_records()
    stats = {platform: _platform_stats(platform_records.get(platform, [])) for platform in PLATFORMS}
    total = sum(item["solved"] for item in stats.values())

    all_difficulty = Counter()
    for item in stats.values():
        all_difficulty.update(item["difficulty"])

    recent = _recent_records(platform_records)
    recent_lines = [
        "| Platform | Problem | Language | Difficulty | Category |",
        "|---|---|---|---|---|",
    ]
    for record in recent:
        recent_lines.append(
            "| {platform} | {title} | {language} | {difficulty} | {category} |".format(
                platform=record.get("platform", "—"),
                title=record.get("title", "—"),
                language=record.get("language", "—"),
                difficulty=record.get("difficulty") or "—",
                category=record.get("primary_category") or "—",
            )
        )
    if len(recent_lines) == 2:
        recent_lines.append("| — | No committed submission data yet | — | — | — |")

    cards = []
    for platform in PLATFORMS:
        cards.append(_platform_card(platform, stats[platform]))

    lines = [
        START_MARKER,
        "## 📊 Progress Dashboard",
        "",
        f"### Total Progress — **{total} problems solved**",
        "",
        f"**Easy** {all_difficulty.get('Easy', 0)} · **Medium** {all_difficulty.get('Medium', 0)} · **Hard** {all_difficulty.get('Hard', 0)}",
        "",
        "### Platforms",
        "",
        "\n\n---\n\n".join(cards),
        "",
        "### Recent Accepted Submissions",
        "",
        *recent_lines,
        "",
        END_MARKER,
    ]
    return "\n".join(lines).strip() + "\n"


def update_readme(readme: str, dashboard: str) -> str:
    if START_MARKER in readme or END_MARKER in readme:
        if START_MARKER not in readme or END_MARKER not in readme:
            raise ValueError("README dashboard markers are incomplete")
        pattern = re.compile(re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER), re.S)
        return pattern.sub(dashboard.strip(), readme, count=1)

    return readme.rstrip() + "\n\n" + dashboard


def generate_readme() -> str:
    current = README_PATH.read_text(encoding="utf-8") if README_PATH.exists() else ""
    return update_readme(current, render_dashboard())


def main() -> int:
    generated = generate_readme()
    current = README_PATH.read_text(encoding="utf-8") if README_PATH.exists() else ""
    if generated != current:
        README_PATH.write_text(generated, encoding="utf-8")
        print("Dashboard updated.")
        return 0
    print("Dashboard unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
