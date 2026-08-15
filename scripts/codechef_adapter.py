"""Authenticated CodeChef web adapter for GitHub Actions."""
from __future__ import annotations

import html
import json
import os
import re
import time
from dataclasses import dataclass
from urllib.parse import quote

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import ElementNotInteractableException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

BASE_URL = "https://www.codechef.com"
LOGIN_URL = f"{BASE_URL}/login"
RECENT_USER_URL = f"{BASE_URL}/recent/user"


class CodeChefAuthError(RuntimeError):
    pass


@dataclass(frozen=True)
class CodeChefRawSubmission:
    submission_id: str
    problem_id: str
    title: str
    language: str
    source_url: str
    accepted_at: str = ""
    status: str = "Accepted"


@dataclass(frozen=True)
class CodeChefProblemMetadata:
    difficulty: str | None = None
    difficulty_source: str | None = None
    difficulty_rating: int | None = None
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class CodeChefSubmissionDetail:
    raw: CodeChefRawSubmission
    source: str
    language: str
    metadata: CodeChefProblemMetadata = CodeChefProblemMetadata()
    title: str = ""


def _text(value: str) -> str:
    return " ".join(value.split())


def _detect_language(text: str) -> str:
    t = text.lower()
    # C++ must be checked before C. Include common C++ syntax that does not
    # necessarily contain the literal string "c++" in the submission page.
    if re.search(r"c\+\+|cpp|gnu\+\+|using\s+namespace\s+std|std::|\bcout\b|\bcin\b|#include\s*<[^>]*(vector|string|iostream|bits/)", t):
        return "C++"
    if re.search(r"javascript|node\.js|nodejs", t):
        return "JavaScript"
    if re.search(r"python|python3", t):
        return "Python"
    if re.search(r"\bjava\b|public\s+static\s+void\s+main", t):
        return "Java"
    if re.search(r"\bc\b|gcc|#include\s*<stdio\.h>", t):
        return "C"
    return "Unknown"


def _extract_problem_id(href: str) -> str:
    m = re.search(r"/problems/([^/?#]+)", href or "")
    return m.group(1) if m else ""


def _extract_time(node) -> str:
    if not node:
        return ""
    for candidate in [node, *node.find_all(True)]:
        for attr in ("datetime", "data-time", "data-timestamp", "title"):
            value = candidate.get(attr)
            if value and re.search(r"\d", str(value)):
                return str(value).strip()
    return ""


def _normalize_embedded_html(value: str) -> str:
    return html.unescape(value.replace(r"\/", "/"))


def _is_accepted_row(row_text: str) -> bool:
    return bool(re.search(r"\bAccepted\b|\(\s*100(?:\.0+)?\s*\)", row_text, re.I))


def parse_submission_list(html_text: str) -> list[CodeChefRawSubmission]:
    soup = BeautifulSoup(_normalize_embedded_html(html_text), "html.parser")
    results: list[CodeChefRawSubmission] = []
    for link in soup.select('a[href*="/viewsolution/"]'):
        href = link.get("href", "")
        m = re.search(r"/viewsolution/(\d+)", href)
        if not m:
            continue
        row = link.find_parent("tr")
        if row is None:
            row = link.parent
            for _ in range(8):
                if row is None:
                    break
                txt = _text(row.get_text(" ", strip=True))
                if row.select_one('a[href*="/problems/"]') or _is_accepted_row(txt):
                    break
                row = row.parent
        row_text = _text(row.get_text(" ", strip=True)) if row else ""
        if not _is_accepted_row(row_text):
            continue
        problem_link = row.select_one('a[href*="/problems/"]') if row else None
        if not problem_link and link.parent:
            problem_link = link.parent.select_one('a[href*="/problems/"]')
        problem_id = _extract_problem_id(problem_link.get("href", "") if problem_link else "")
        if not problem_id:
            continue
        solution_url = href if href.startswith("http") else BASE_URL + href
        results.append(
            CodeChefRawSubmission(
                submission_id=m.group(1),
                problem_id=problem_id,
                title=_text(problem_link.get_text(" ", strip=True)) if problem_link else problem_id,
                language=_detect_language(row_text),
                source_url=solution_url,
                accepted_at=_extract_time(row),
            )
        )
    seen: set[str] = set()
    unique: list[CodeChefRawSubmission] = []
    for item in results:
        if item.submission_id not in seen:
            seen.add(item.submission_id)
            unique.append(item)
    return unique


def _text_preserve(node) -> str:
    if not node:
        return ""
    return node.get_text("", strip=False).replace("\r\n", "\n").strip()


def _source_candidates_from_soup(soup: BeautifulSoup) -> list[str]:
    selectors = [
        "pre", "pre code", "textarea", ".CodeMirror-code", ".CodeMirror-code pre",
        ".ace_text-layer", ".ace_content", ".monaco-editor .view-lines", ".monaco-editor",
        "[data-testid*='code']", "[class*='source-code']", "[class*='source_code']",
        "[class*='code-content']", "[class*='code_content']", "[class*='highlight']",
    ]
    candidates: list[str] = []
    seen: set[str] = set()
    for selector in selectors:
        for node in soup.select(selector):
            value = _text_preserve(node)
            if len(value) < 10 or value in seen:
                continue
            seen.add(value)
            candidates.append(value)
    return candidates


def _choose_source(candidates: list[str]) -> str:
    if not candidates:
        return ""

    def score(value: str) -> tuple[int, int]:
        lines = value.splitlines()
        markers = sum(
            1
            for line in lines
            if re.search(
                r"(#include|#define|using\s+namespace|int\s+main|void\s+main|public\s+static|import\s+|from\s+\w+\s+import|def\s+\w+|console\.log|System\.out|return\b|\{\s*$|;\s*$)",
                line,
            )
        )
        ui_words = len(
            re.findall(r"\b(submit|solution|problem|contest|codechef|login|accepted|language)\b", value, re.I)
        )
        return markers * 100 - ui_words * 5, len(value)

    return max(candidates, key=score)


def _extract_source_from_rendered_driver(driver) -> str:
    def candidates() -> list[str]:
        soup = BeautifulSoup(driver.page_source, "html.parser")
        values = _source_candidates_from_soup(soup)
        try:
            values.extend(
                driver.execute_script(
                    """
                    const selectors = ['pre','pre code','textarea','.CodeMirror-code','.CodeMirror-code pre',
                      '.ace_text-layer','.ace_content','.monaco-editor .view-lines','.monaco-editor',
                      '[data-testid*=\"code\"]','[class*=\"source-code\"]','[class*=\"source_code\"]',
                      '[class*=\"code-content\"]','[class*=\"code_content\"]','[class*=\"highlight\"]'];
                    const out=[];
                    for (const selector of selectors) for (const el of document.querySelectorAll(selector)) {
                      const text=el.value || el.innerText || el.textContent || '';
                      if (text && text.trim().length >= 10) out.push(text);
                    }
                    return out;
                    """
                )
                or []
            )
        except Exception:
            pass
        return [str(x).strip() for x in values if str(x).strip()]

    source = _choose_source(candidates())
    if source:
        return source
    for frame in driver.find_elements(By.TAG_NAME, "iframe"):
        try:
            driver.switch_to.frame(frame)
            source = _choose_source(candidates())
            driver.switch_to.default_content()
            if source:
                return source
        except Exception:
            try:
                driver.switch_to.default_content()
            except Exception:
                pass
    return ""


def parse_solution_page(html_text: str) -> tuple[str, str]:
    soup = BeautifulSoup(_normalize_embedded_html(html_text), "html.parser")
    source = _choose_source(_source_candidates_from_soup(soup))
    page_text = soup.get_text(" ", strip=True)
    return source, _detect_language(_text(page_text))


def _difficulty_from_rating(rating: int | None):
    if rating is None:
        return None, None
    if rating <= 1000:
        return "Easy", "codechef_official_rating_mapping"
    if rating <= 1800:
        return "Medium", "codechef_official_rating_mapping"
    return "Hard", "codechef_official_rating_mapping"


def _find_rating(raw_html: str, page_text: str) -> int | None:
    sources = [_normalize_embedded_html(raw_html), page_text]
    patterns = [
        r"difficultyRating\s*[:=]\s*[\"']?(\d{2,4})",
        r"difficulty[_-]?rating\s*[:=]\s*[\"']?(\d{2,4})",
        r"problemDifficultyRating\s*[:=]\s*[\"']?(\d{2,4})",
        r"\"rating\"\s*:\s*(\d{2,4})",
        r"difficulty\s*rating[^0-9]{0,40}(\d{2,4})",
    ]
    for source in sources:
        for pattern in patterns:
            match = re.search(pattern, source, re.I)
            if match:
                value = int(match.group(1))
                if 0 <= value <= 5000:
                    return value
    return None


def _extract_tags(soup: BeautifulSoup, raw_html: str) -> tuple[str, ...]:
    tags: list[str] = []
    for link in soup.select('a[href*="/tags/"]'):
        label = _text(link.get_text(" ", strip=True))
        if label and len(label) <= 60 and label.lower() not in {x.lower() for x in tags}:
            tags.append(label)
    # Some CodeChef pages expose tags only inside JSON/escaped page data.
    for match in re.findall(r"/tags/([A-Za-z0-9_-]+)", _normalize_embedded_html(raw_html)):
        label = match.replace("-", " ").replace("_", " ").strip()
        if label and label.lower() not in {x.lower() for x in tags}:
            tags.append(label.title())
    return tuple(tags)


def parse_problem_metadata(html_text: str) -> CodeChefProblemMetadata:
    normalized = _normalize_embedded_html(html_text)
    soup = BeautifulSoup(normalized, "html.parser")
    page_text = _text(soup.get_text(" ", strip=True))
    rating = _find_rating(normalized, page_text)
    tags = _extract_tags(soup, normalized)
    difficulty, source = _difficulty_from_rating(rating)
    return CodeChefProblemMetadata(difficulty, source, rating, tags)


def extract_problem_title(html_text: str, fallback: str) -> str:
    soup = BeautifulSoup(_normalize_embedded_html(html_text), "html.parser")
    for selector in ("h1", "h2", "meta[property='og:title']", "title"):
        node = soup.select_one(selector)
        if not node:
            continue
        value = node.get("content") if node.name == "meta" else node.get_text(" ", strip=True)
        value = _text(value or "")
        value = re.sub(r"\s*[|–-]\s*CodeChef.*$", "", value, flags=re.I).strip()
        if value and value.lower() not in {"codechef", "problem"}:
            return value
    return fallback


def build_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1440,1200")
    options.add_argument("--disable-gpu")
    return webdriver.Chrome(options=options)


def _credentials():
    username = os.environ.get("CODECHEF_USERNAME")
    password = os.environ.get("CODECHEF_PASSWORD")
    if not username or not password:
        raise CodeChefAuthError("CODECHEF_USERNAME/CODECHEF_PASSWORD are not set.")
    return username, password


def _first_visible(elements):
    for x in elements:
        try:
            if x.is_displayed() and x.is_enabled():
                return x
        except Exception:
            pass
    return None


def _login(driver, username, password):
    driver.get(LOGIN_URL)
    wait = WebDriverWait(driver, 35)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    def visible_inputs():
        return [x for x in driver.find_elements(By.CSS_SELECTOR, "input") if x.is_displayed() and x.is_enabled()]

    def desc(x):
        return " ".join(str(x.get_attribute(a) or "") for a in ("type", "name", "id", "placeholder", "aria-label", "autocomplete")).lower()

    def username_field():
        ranked = []
        for x in visible_inputs():
            if (x.get_attribute("type") or "").lower() == "password":
                continue
            a = desc(x)
            score = (10 if "username" in a else 0) + (8 if "email" in a else 0) + (5 if "login" in a else 0) + (10 if x.get_attribute("autocomplete") in ("username", "email") else 0)
            ranked.append((score, x))
        ranked.sort(key=lambda z: z[0], reverse=True)
        return ranked[0][1] if ranked and ranked[0][0] else None

    try:
        user = wait.until(lambda d: username_field())
        pw = wait.until(lambda d: _first_visible([x for x in visible_inputs() if (x.get_attribute("type") or "").lower() == "password"]))
    except TimeoutException as exc:
        raise CodeChefAuthError(f"Could not locate CodeChef login fields. URL={driver.current_url!r}, title={driver.title!r}") from exc
    try:
        user.click(); user.clear(); user.send_keys(username)
        pw.click(); pw.clear(); pw.send_keys(password)
    except ElementNotInteractableException as exc:
        raise CodeChefAuthError("CodeChef login fields could not be interacted with") from exc
    buttons = driver.find_elements(By.CSS_SELECTOR, "button, input[type='submit']")
    button = _first_visible([b for b in buttons if re.search(r"log\s*in|sign\s*in", _text(b.text or b.get_attribute("value") or ""), re.I)])
    if button:
        button.click()
    else:
        pw.submit()
    try:
        wait.until(lambda d: "/login" not in d.current_url.lower())
    except TimeoutException as exc:
        raise CodeChefAuthError("CodeChef login did not complete") from exc


def _load_profile_submissions(driver, username: str, limit: int) -> list[CodeChefRawSubmission]:
    url = f"{BASE_URL}/users/{quote(username)}"
    for attempt in range(3):
        driver.get(url)
        WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        try:
            WebDriverWait(driver, 12).until(lambda d: len(d.find_elements(By.CSS_SELECTOR, 'a[href*="/viewsolution/"]')) > 0)
        except TimeoutException:
            pass
        items = parse_submission_list(driver.page_source)
        if items:
            return items[:limit]
        if attempt < 2:
            time.sleep(2)
    return []


def fetch_recent_accepted(limit: int = 20) -> list[CodeChefRawSubmission]:
    username, password = _credentials()
    driver = build_driver()
    try:
        _login(driver, username, password)
        return _load_profile_submissions(driver, username, limit)
    finally:
        driver.quit()


def fetch_recent_accepted_details(limit: int = 20) -> list[CodeChefSubmissionDetail]:
    username, password = _credentials()
    driver = build_driver()
    try:
        _login(driver, username, password)
        submissions = _load_profile_submissions(driver, username, limit)
        details: list[CodeChefSubmissionDetail] = []
        for raw in submissions:
            driver.get(raw.source_url)
            WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            source = ""
            for _ in range(10):
                source = _extract_source_from_rendered_driver(driver)
                if source:
                    break
                time.sleep(1.5)
            if not source:
                raise CodeChefAuthError(f"Could not extract source code from submission {raw.submission_id}; url={driver.current_url!r}")

            # The submission table is authoritative for the selected compiler.
            # Never downgrade C++ to C merely because the source contains C-like syntax.
            language = raw.language if raw.language != "Unknown" else _detect_language(source)
            if language == "C" and _detect_language(source) == "C++":
                language = "C++"

            driver.get(f"{BASE_URL}/problems/{quote(raw.problem_id)}")
            WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            problem_html = driver.page_source
            metadata = parse_problem_metadata(problem_html)
            title = extract_problem_title(problem_html, raw.title or raw.problem_id)
            details.append(CodeChefSubmissionDetail(raw, source, language, metadata, title))
        return details
    finally:
        driver.quit()


def fetch_all_accepted_keys(max_pages: int = 100) -> set[str]:
    """Return existing accepted problem/language keys only; never persist source."""
    username, password = _credentials()
    driver = build_driver()
    keys: set[str] = set()
    seen: set[str] = set()
    try:
        _login(driver, username, password)
        for page in range(max_pages):
            driver.get(f"{RECENT_USER_URL}?user_handle={quote(username)}&page={page}")
            WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            items = parse_submission_list(driver.page_source)
            new = [x for x in items if x.submission_id not in seen]
            if not new:
                break
            for item in new:
                seen.add(item.submission_id)
                lang = item.language
                if lang == "Unknown":
                    driver.get(item.source_url)
                    WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                    for _ in range(10):
                        source = _extract_source_from_rendered_driver(driver)
                        if source:
                            lang = _detect_language(source)
                            break
                        time.sleep(1.0)
                if lang == "C" and source if False else False:
                    pass
                if lang != "Unknown":
                    keys.add(f"codechef::{item.problem_id}::{lang.lower()}")
        if not keys:
            for item in _load_profile_submissions(driver, username, max_pages):
                if item.language != "Unknown":
                    keys.add(f"codechef::{item.problem_id}::{item.language.lower()}")
        return keys
    finally:
        driver.quit()
