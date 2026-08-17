"""Generate the repository's static progress dashboard from committed data."""

from __future__ import annotations

import html
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SUBMISSIONS_PATH = ROOT / "data" / "submissions.json"
README_PATH = ROOT / "README.md"
START_MARKER = "<!-- DASHBOARD:START -->"
END_MARKER = "<!-- DASHBOARD:END -->"
PLATFORMS = ("LeetCode", "CodeChef", "HackerRank")
DIFFICULTIES = ("Easy", "Medium", "Hard")
PLATFORM_ACCENTS = {
    "LeetCode": "#f0b90b",
    "CodeChef": "#a855f7",
    "HackerRank": "#16c60c",
}


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


def _hacker_rank_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    hr_root = ROOT / "HackerRank"
    if not hr_root.exists():
        return records

    for readme_path in hr_root.rglob("README.md"):
        try:
            relative = readme_path.relative_to(hr_root).parts
            if len(relative) < 5:
                continue
            language, category, difficulty = relative[:3]
            problem_dir = readme_path.parent.name
            if "-" not in problem_dir:
                continue
            problem_id, title_slug = problem_dir.split("-", 1)
            metadata = readme_path.read_text(encoding="utf-8")
            submitted = re.search(r"^- \*\*Submitted:\*\*\s*(.+)$", metadata, re.MULTILINE)
            title = re.search(r"^#\s+(.+)$", metadata, re.MULTILINE)
            records.append(
                {
                    "platform": "HackerRank",
                    "problem_id": problem_id,
                    "title": title.group(1).strip() if title else title_slug.replace("-", " ").title(),
                    "language": language,
                    "difficulty": difficulty if difficulty in DIFFICULTIES else None,
                    "primary_category": category.replace("-", " ").title(),
                    "accepted_at": submitted.group(1).strip() if submitted else "",
                }
            )
        except OSError:
            continue
    return records


def discover_platform_records() -> dict[str, list[dict[str, Any]]]:
    records: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in load_submissions().values():
        platform = str(record.get("platform") or "").strip()
        if platform in PLATFORMS:
            records[platform].append(record)
    records["HackerRank"].extend(_hacker_rank_records())
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


def platform_stats(records: list[dict[str, Any]]) -> dict[str, Any]:
    unique = _unique_records(records)
    difficulty = Counter(str(r.get("difficulty")) for r in unique if r.get("difficulty") in DIFFICULTIES)
    languages = Counter(str(r.get("language")) for r in unique if r.get("language"))
    categories = Counter(str(r.get("primary_category")) for r in unique if r.get("primary_category"))
    return {"solved": len(unique), "difficulty": difficulty, "languages": languages, "categories": categories, "records": unique}


def _parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.isdigit():
            return datetime.fromtimestamp(int(text), tz=timezone.utc)
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None


def streak_stats(records: list[dict[str, Any]], today: datetime | None = None) -> tuple[int | None, int | None]:
    dates = {parsed.astimezone(timezone.utc).date() for record in records if (parsed := _parse_timestamp(record.get("accepted_at")))}
    if not dates:
        return None, None

    ordered = sorted(dates)
    best = current_run = 1
    for previous, current in zip(ordered, ordered[1:]):
        if (current - previous).days == 1:
            current_run += 1
            best = max(best, current_run)
        else:
            current_run = 1

    now_date = (today or datetime.now(timezone.utc)).astimezone(timezone.utc).date()
    yesterday = now_date.fromordinal(now_date.toordinal() - 1)
    if now_date in dates:
        cursor = now_date
    elif yesterday in dates:
        cursor = yesterday
    else:
        return 0, best

    current = 0
    while cursor in dates:
        current += 1
        cursor = cursor.fromordinal(cursor.toordinal() - 1)
    return current, best


def _format_counter(counter: Counter[str]) -> str:
    if not counter:
        return "—"
    return " · ".join(f"{html.escape(key)} <strong>{value}</strong>" for key, value in counter.most_common())


def _platform_card(platform: str, stats: dict[str, Any]) -> str:
    difficulty = stats["difficulty"]
    accent = PLATFORM_ACCENTS[platform]
    solved = stats["solved"]
    easy = difficulty.get("Easy", 0)
    medium = difficulty.get("Medium", 0)
    hard = difficulty.get("Hard", 0)
    difficulty_text = f"Easy {easy} · Medium {medium} · Hard {hard}"
    return "\n".join(
        [
            f'<td style="width:33.33%;vertical-align:top;padding:8px;border:0;background:transparent;">',
            f'<div style="background:rgba(255,255,255,.02);border-radius:16px;padding:22px 20px;box-shadow:inset 0 0 0 1px rgba(139,148,158,.28);">',
            f'<div style="height:4px;background:{accent};margin:-22px -20px 18px;border-radius:16px 16px 0 0;"></div>',
            f'<div style="font-size:21px;font-weight:700;">{platform}</div>',
            f'<div style="margin-top:4px;font-size:13px;opacity:.65;">{solved} accepted problem{\"s\" if solved != 1 else \"\"}</div>',
            f'<div style="margin-top:16px;font-size:15px;">{difficulty_text}</div>',
            f'<div style="margin-top:16px;font-size:13px;line-height:1.8;"><strong>Languages</strong><br>{_format_counter(stats["languages"])}</div>',
            f'<div style="margin-top:8px;font-size:13px;line-height:1.8;"><strong>Topics</strong><br>{_format_counter(stats["categories"])}</div>',
            '</div>',
            '</td>',
        ]
    )


def _recent_records(platform_records: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows = [{**record, "platform": platform} for platform, records in platform_records.items() for record in _unique_records(records)]
    dated = [row for row in rows if _parse_timestamp(row.get("accepted_at"))]
    undated = [row for row in rows if not _parse_timestamp(row.get("accepted_at"))]
    dated.sort(key=lambda row: _parse_timestamp(row.get("accepted_at")) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return dated + undated


def _recent_table(platform_records: dict[str, list[dict[str, Any]]]) -> str:
    rows = [
        '<table style="width:100%;">',
        '<thead><tr><th align="left">Platform</th><th align="left">Problem</th><th align="left">Language</th><th align="left">Difficulty</th><th align="left">Topic</th></tr></thead>',
        '<tbody>',
    ]
    for record in _recent_records(platform_records):
        rows.append(
            "<tr>"
            f"<td><strong>{html.escape(str(record.get('platform', '—')))}</strong></td>"
            f"<td>{html.escape(str(record.get('title', '—')))}</td>"
            f"<td>{html.escape(str(record.get('language', '—')))}</td>"
            f"<td>{html.escape(str(record.get('difficulty') or '—'))}</td>"
            f"<td>{html.escape(str(record.get('primary_category') or '—'))}</td>"
            "</tr>"
        )
    if len(rows) == 3:
        rows.append('<tr><td>—</td><td>No committed submission data yet</td><td>—</td><td>—</td><td>—</td></tr>')
    rows.append('</tbody></table>')
    return "\n".join(rows)


def _summary_stat(value: int | str, label: str) -> str:
    return (
        '<div style="text-align:center;min-width:110px;padding:4px 10px;">'
        f'<div style="font-size:13px;opacity:.68;">{label}</div>'
        f'<div style="font-size:26px;font-weight:700;margin-top:3px;">{value}</div>'
        '</div>'
    )


def render_dashboard() -> str:
    platform_records = discover_platform_records()
    stats = {platform: platform_stats(platform_records.get(platform, [])) for platform in PLATFORMS}
    all_records = [record for records in platform_records.values() for record in _unique_records(records)]
    total = len({(str(r.get("platform")), str(r.get("problem_id")), str(r.get("language"))) for r in all_records})
    all_difficulty = Counter()
    for item in stats.values():
        all_difficulty.update(item["difficulty"])
    current_streak, best_streak = streak_stats(all_records)
    current_text = "—" if current_streak is None else str(current_streak)
    best_text = "—" if best_streak is None else str(best_streak)

    return "\n".join(
        [
            START_MARKER,
            '<div align="center">',
            '<h1 style="margin-bottom:8px;">📊 DSA Progress Dashboard</h1>',
            '<p><strong>LeetCode · CodeChef · HackerRank</strong></p>',
            '<p style="opacity:.68;">Accepted solutions tracked automatically from this repository.</p>',
            '<div style="margin-top:24px;display:flex;justify-content:center;gap:16px;flex-wrap:wrap;">',
            _summary_stat(total, "Problems"),
            _summary_stat(all_difficulty.get("Easy", 0), "Easy"),
            _summary_stat(all_difficulty.get("Medium", 0), "Medium"),
            _summary_stat(all_difficulty.get("Hard", 0), "Hard"),
            _summary_stat(current_text, "Current streak"),
            _summary_stat(best_text, "Best streak"),
            '</div>',
            '</div>',
            '',
            '<div style="margin-top:28px;">',
            '<h2>Platforms</h2>',
            '<table style="width:100%;border:0;background:transparent;"><tr>',
            *(_platform_card(platform, stats[platform]) for platform in PLATFORMS),
            '</tr></table>',
            '</div>',
            '',
            '<div style="margin-top:20px;">',
            '<h2>Recent Accepted Submissions</h2>',
            _recent_table(platform_records),
            '</div>',
            '',
            END_MARKER,
        ]
    ).strip() + "\n"


def update_readme(readme: str, dashboard: str) -> str:
    has_start = START_MARKER in readme
    has_end = END_MARKER in readme
    if has_start or has_end:
        if not (has_start and has_end):
            raise ValueError("README dashboard markers are incomplete")
        pattern = re.compile(re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER), re.S)
        return pattern.sub(dashboard.strip(), readme, count=1)
    return readme.rstrip() + "\n\n" + dashboard


def generate_readme() -> str:
    current = README_PATH.read_text(encoding="utf-8") if README_PATH.exists() else ""
    return update_readme(current, render_dashboard())


def main() -> int:
    current = README_PATH.read_text(encoding="utf-8") if README_PATH.exists() else ""
    generated = generate_readme()
    if generated != current:
        README_PATH.write_text(generated, encoding="utf-8")
        print("Dashboard updated.")
    else:
        print("Dashboard unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
