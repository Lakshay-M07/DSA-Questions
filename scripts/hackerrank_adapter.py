import html
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.hackerrank.com"
LOGIN_PAGE = f"{BASE_URL}/auth/login"
REST_LOGIN = f"{BASE_URL}/rest/auth/login"
SUBMISSIONS_URL = f"{BASE_URL}/rest/contests/master/submissions/"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36", "Accept": "application/json,text/plain,*/*"}
LANGUAGE_EXTENSIONS = {"c": ("C", ".c"), "c++": ("C++", ".cpp"), "cpp": ("C++", ".cpp"), "cxx": ("C++", ".cpp"), "python": ("Python", ".py"), "python3": ("Python", ".py"), "python 3": ("Python", ".py"), "pypy": ("Python", ".py"), "pypy3": ("Python", ".py"), "java": ("Java", ".java"), "javascript": ("JavaScript", ".js"), "js": ("JavaScript", ".js")}
DIFFICULTY_WORDS = {"easy": "Easy", "medium": "Medium", "hard": "Hard"}

@dataclass(frozen=True)
class HackerRankSubmission:
    submission_id: str
    problem_id: str
    slug: str
    title: str
    language: str
    extension: str
    status: str
    submitted_at: str | None
    source: str | None = None
    difficulty: str | None = None
    category: str | None = None
    tags: tuple[str, ...] = ()
    description: str | None = None

class HackerRankClient:
    """Read-only HackerRank Community client.

    If HACKERRANK_SESSION_ID is supplied, it is used as the browser's
    authenticated _hrank_session cookie and password login is skipped.
    """
    def __init__(self, email: str | None = None, password: str | None = None, session: requests.Session | None = None, session_id: str | None = None):
        self.email, self.password = email, password
        self.session = session or requests.Session()
        self.session.headers.update(HEADERS)
        self.session_id = session_id
        self._authenticated = False
        if session_id:
            self.session.cookies.set("_hrank_session", session_id, domain=".hackerrank.com", path="/")
            self._authenticated = True

    def authenticate(self) -> None:
        if self._authenticated:
            return
        if not self.email or not self.password:
            raise RuntimeError("HackerRank credentials are missing")
        page = self.session.get(LOGIN_PAGE, timeout=30)
        page.raise_for_status()
        soup = BeautifulSoup(page.text, "html.parser")
        csrf = None
        meta = soup.find("meta", attrs={"id": "csrf-token"})
        if meta: csrf = meta.get("content")
        if not csrf:
            match = re.search(r'csrf[_-]?token["\']?\s*[:=]\s*["\']([^"\']+)', page.text, re.I)
            csrf = match.group(1) if match else None
        headers = {"Referer": LOGIN_PAGE}
        if csrf: headers["x-csrf-token"] = csrf
        response = self.session.post(REST_LOGIN, data={"login": self.email, "password": self.password, "remember_me": "false", "fallback": "true"}, headers=headers, timeout=30, allow_redirects=False)
        if response.status_code not in (200, 201, 202): raise RuntimeError(f"HackerRank authentication failed: HTTP {response.status_code}")
        try: payload = response.json()
        except ValueError as exc: raise RuntimeError("HackerRank authentication did not return JSON") from exc
        if payload.get("csrf_token"): self.session.headers["x-csrf-token"] = payload["csrf_token"]
        self._authenticated = True

    def _get(self, url: str, **params: Any) -> Any:
        if not self._authenticated: self.authenticate()
        response = self.session.get(url, params=params or None, timeout=30)
        if response.status_code != 200: raise RuntimeError(f"HackerRank REST request failed: HTTP {response.status_code} {response.url}")
        try: return response.json()
        except ValueError as exc: raise RuntimeError(f"HackerRank REST endpoint returned non-JSON data: {response.url}") from exc

    def fetch_submissions(self, limit: int = 1000) -> list[dict[str, Any]]:
        data = self._get(SUBMISSIONS_URL, offset=0, limit=limit)
        models = data.get("models") if isinstance(data, dict) else None
        if not isinstance(models, list): raise RuntimeError("HackerRank submissions response does not contain a models list")
        return [x for x in models if isinstance(x, dict)]

    def fetch_submission_source(self, slug: str, submission_id: str) -> dict[str, Any]:
        url = f"{BASE_URL}/rest/contests/master/challenges/{quote(slug, safe='')}/submissions/{quote(str(submission_id), safe='')}"
        return self._get(url)

    def fetch_challenge(self, slug: str) -> dict[str, Any]:
        url = f"{BASE_URL}/rest/contests/master/challenges/{quote(slug, safe='')}"
        data = self._get(url)
        return data if isinstance(data, dict) else {}

def normalize_language(value: Any) -> tuple[str, str]:
    text = re.sub(r"\s+", " ", str(value or "").strip().lower())
    exact = LANGUAGE_EXTENSIONS.get(text)
    if exact: return exact
    for key in sorted(LANGUAGE_EXTENSIONS, key=len, reverse=True):
        if key in text: return LANGUAGE_EXTENSIONS[key]
    if "kotlin" in text: return "Kotlin", ".kt"
    if "ruby" in text: return "Ruby", ".rb"
    if text == "go" or text.startswith("go "): return "Go", ".go"
    if "rust" in text: return "Rust", ".rs"
    return str(value or "Unknown"), ".txt"

def first_value(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if item.get(key) not in (None, ""): return item[key]
    return None

def slugify(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower() or "question"

def clean_text(value: Any) -> str | None:
    if value is None: return None
    if isinstance(value, str):
        text = BeautifulSoup(html.unescape(value), "html.parser").get_text("\n", strip=True)
        text = re.sub(r"\s+([.,!?;:])", r"\1", text)
        return text or None
    return str(value)

def _model(data: dict[str, Any]) -> dict[str, Any]:
    value = data.get("model")
    return value if isinstance(value, dict) else data

def extract_source(data: Any) -> str | None:
    preferred = {"code", "source", "source_code", "solution", "code_content"}
    def walk(value: Any) -> str | None:
        if isinstance(value, dict):
            for key in preferred:
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip(): return html.unescape(candidate).strip()
            for child in value.values():
                found = walk(child)
                if found: return found
        elif isinstance(value, list):
            for child in value:
                found = walk(child)
                if found: return found
        return None
    return walk(data)

def extract_problem_metadata(data: dict[str, Any]) -> tuple[str | None, str | None, str | None, tuple[str, ...], str | None]:
    data = _model(data)
    title = first_value(data, "name", "title", "challenge_name")
    difficulty = first_value(data, "difficulty_name", "difficulty", "difficultyName")
    category = first_value(data, "category", "track", "domain")
    tags = first_value(data, "tags", "tag_names", "topics") or []
    description = first_value(data, "description", "problem_statement", "body", "content")
    if isinstance(difficulty, dict): difficulty = first_value(difficulty, "name", "label", "value", "level")
    if difficulty: difficulty = DIFFICULTY_WORDS.get(str(difficulty).strip().lower(), str(difficulty))
    if isinstance(category, dict): category = first_value(category, "track_name", "name", "label", "slug")
    if isinstance(tags, str): tags = [x.strip() for x in re.split(r"[,|]", tags) if x.strip()]
    elif not isinstance(tags, list): tags = []
    tags = tuple(str(x.get("name", x) if isinstance(x, dict) else x) for x in tags)
    return (str(title) if title else None, str(difficulty) if difficulty else None, str(category) if category else None, tags, clean_text(description))

def parse_submission(record: dict[str, Any]) -> HackerRankSubmission | None:
    if str(record.get("status", "")).strip().lower() != "accepted": return None
    challenge = record.get("challenge") if isinstance(record.get("challenge"), dict) else {}
    submission_id = first_value(record, "id", "submission_id", "submissionId")
    slug = first_value(record, "challenge_slug", "slug", "challengeSlug", "slug_name") or first_value(challenge, "slug", "challenge_slug")
    title = first_value(record, "challenge_name", "name", "title", "challengeName") or first_value(challenge, "name", "title")
    language_raw = first_value(record, "language", "language_name", "languageName")
    if submission_id is None or slug is None: return None
    language, extension = normalize_language(language_raw)
    submitted_at = first_value(record, "created_at", "createdAt", "submitted_at", "submittedAt", "time")
    if isinstance(submitted_at, (int, float)): submitted_at = datetime.fromtimestamp(submitted_at, tz=timezone.utc).isoformat()
    problem_id = first_value(record, "challenge_id", "challengeId", "problem_id", "problemId") or first_value(challenge, "id", "challenge_id") or slug
    return HackerRankSubmission(submission_id=str(submission_id), problem_id=str(problem_id), slug=str(slug), title=str(title or slug.replace("-", " ").title()), language=language, extension=extension, status="Accepted", submitted_at=str(submitted_at) if submitted_at else None)
