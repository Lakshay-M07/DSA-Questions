"""Authenticated CodeChef web adapter for GitHub Actions."""
from __future__ import annotations

import os
import re
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

def _text(value: str) -> str:
    return " ".join(value.split())

def _detect_language(text: str) -> str:
    t = text.lower()
    if re.search(r"c\+\+|cpp|gnu\+\+", t): return "C++"
    if re.search(r"javascript|node\.js|nodejs", t): return "JavaScript"
    if re.search(r"python|python3", t): return "Python"
    if re.search(r"java", t): return "Java"
    if re.search(r"\bc\b|gcc", t): return "C"
    return "Unknown"

def _extract_problem_id(href: str) -> str:
    m = re.search(r"/problems/([^/?#]+)", href or "")
    return m.group(1) if m else ""

def _extract_time(node) -> str:
    if not node: return ""
    for candidate in [node, *node.find_all(True)]:
        for attr in ("datetime", "data-time", "data-timestamp", "title"):
            value = candidate.get(attr)
            if value and re.search(r"\d", str(value)): return str(value).strip()
    return ""

def _normalize_embedded_html(html: str) -> str:
    return html.replace(r"\/", "/")

def _is_accepted_row(row_text: str) -> bool:
    return bool(re.search(r"\bAccepted\b|\(\s*100(?:\.0+)?\s*\)", row_text, re.I))

def parse_submission_list(html: str) -> list[CodeChefRawSubmission]:
    soup = BeautifulSoup(_normalize_embedded_html(html), "html.parser")
    results = []
    for link in soup.select('a[href*="/viewsolution/"]'):
        href = link.get("href", "")
        m = re.search(r"/viewsolution/(\d+)", href)
        if not m: continue
        row = link.find_parent("tr")
        if row is None:
            row = link.parent
            for _ in range(8):
                if row is None: break
                txt = _text(row.get_text(" ", strip=True))
                if row.select_one('a[href*="/problems/"]') or _is_accepted_row(txt): break
                row = row.parent
        row_text = _text(row.get_text(" ", strip=True)) if row else ""
        if not _is_accepted_row(row_text): continue
        problem_link = row.select_one('a[href*="/problems/"]') if row else None
        if not problem_link and link.parent:
            problem_link = link.parent.select_one('a[href*="/problems/"]')
        problem_id = _extract_problem_id(problem_link.get("href", "") if problem_link else "")
        if not problem_id: continue
        solution_url = href if href.startswith("http") else BASE_URL + href
        results.append(CodeChefRawSubmission(
            submission_id=m.group(1), problem_id=problem_id,
            title=_text(problem_link.get_text(" ", strip=True)) if problem_link else problem_id,
            language=_detect_language(row_text), source_url=solution_url,
            accepted_at=_extract_time(row)))
    seen = set(); unique = []
    for item in results:
        if item.submission_id not in seen:
            seen.add(item.submission_id); unique.append(item)
    return unique

def _text_preserve(node) -> str:
    if not node: return ""
    return node.get_text("", strip=False).replace("\r\n", "\n").strip()

def parse_solution_page(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    source = max((_text_preserve(x) for x in soup.select("pre, code, textarea")), key=len, default="")
    # _text accepts strings; BeautifulSoup objects must be converted explicitly.
    page_text = soup.get_text(" ", strip=True)
    return source, _detect_language(_text(page_text))

def _difficulty_from_rating(rating: int | None):
    if rating is None: return None, None
    if rating <= 1000: return "Easy", "codechef_official_rating_mapping"
    if rating <= 1800: return "Medium", "codechef_official_rating_mapping"
    return "Hard", "codechef_official_rating_mapping"

def parse_problem_metadata(html: str) -> CodeChefProblemMetadata:
    soup = BeautifulSoup(html, "html.parser")
    page_text = _text(soup.get_text(" ", strip=True))
    rating = None
    for pattern in (r"difficulty\s*rating[^0-9]{0,20}(\d{2,4})", r"difficultyRating[^0-9]{0,20}(\d{2,4})", r"\"difficulty\"\s*[:=]\s*\"?(\d{2,4})"):
        m = re.search(pattern, page_text, re.I)
        if m: rating = int(m.group(1)); break
    tags = []
    for link in soup.select('a[href*="/tags/"]'):
        label = _text(link.get_text(" ", strip=True))
        if label and len(label) <= 60 and label.lower() not in {x.lower() for x in tags}: tags.append(label)
    difficulty, source = _difficulty_from_rating(rating)
    return CodeChefProblemMetadata(difficulty, source, rating, tuple(tags))

def build_driver():
    options = Options()
    options.add_argument("--headless=new"); options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage"); options.add_argument("--window-size=1440,1200")
    options.add_argument("--disable-gpu")
    return webdriver.Chrome(options=options)

def _credentials():
    username, password = os.environ.get("CODECHEF_USERNAME"), os.environ.get("CODECHEF_PASSWORD")
    if not username or not password: raise CodeChefAuthError("CODECHEF_USERNAME/CODECHEF_PASSWORD are not set.")
    return username, password

def _first_visible(elements):
    for x in elements:
        try:
            if x.is_displayed() and x.is_enabled(): return x
        except Exception: pass
    return None

def _login(driver, username, password):
    driver.get(LOGIN_URL)
    wait = WebDriverWait(driver, 35)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    def visible_inputs(): return [x for x in driver.find_elements(By.CSS_SELECTOR, "input") if x.is_displayed() and x.is_enabled()]
    def desc(x): return " ".join(str(x.get_attribute(a) or "") for a in ("type","name","id","placeholder","aria-label","autocomplete")).lower()
    def username_field():
        ranked=[]
        for x in visible_inputs():
            if (x.get_attribute("type") or "").lower()=="password": continue
            a=desc(x); score=(10 if "username" in a else 0)+(8 if "email" in a else 0)+(5 if "login" in a else 0)+(10 if x.get_attribute("autocomplete") in ("username","email") else 0)
            ranked.append((score,x))
        ranked.sort(key=lambda z:z[0], reverse=True)
        return ranked[0][1] if ranked and ranked[0][0] else None
    try:
        user = wait.until(lambda d: username_field())
        pw = wait.until(lambda d: _first_visible([x for x in visible_inputs() if (x.get_attribute("type") or "").lower()=="password"]))
    except TimeoutException as exc:
        raise CodeChefAuthError(f"Could not locate CodeChef login fields. URL={driver.current_url!r}, title={driver.title!r}") from exc
    try:
        user.click(); user.clear(); user.send_keys(username)
        pw.click(); pw.clear(); pw.send_keys(password)
    except ElementNotInteractableException as exc:
        raise CodeChefAuthError("CodeChef login fields could not be interacted with") from exc
    buttons = driver.find_elements(By.CSS_SELECTOR, "button, input[type='submit']")
    button = _first_visible([b for b in buttons if re.search(r"log\s*in|sign\s*in", _text(b.text or b.get_attribute("value") or ""), re.I)])
    if button: button.click()
    else: pw.submit()
    try: wait.until(lambda d: "/login" not in d.current_url.lower())
    except TimeoutException as exc: raise CodeChefAuthError("CodeChef login did not complete") from exc

def fetch_recent_accepted(limit: int = 20) -> list[CodeChefRawSubmission]:
    username, password = _credentials(); driver = build_driver()
    try:
        _login(driver, username, password); driver.get(f"{BASE_URL}/users/{quote(username)}")
        WebDriverWait(driver,25).until(EC.presence_of_element_located((By.TAG_NAME,"body")))
        return parse_submission_list(driver.page_source)[:limit]
    finally: driver.quit()

def fetch_recent_accepted_details(limit: int = 20) -> list[CodeChefSubmissionDetail]:
    username, password = _credentials(); driver = build_driver()
    try:
        _login(driver, username, password); driver.get(f"{BASE_URL}/users/{quote(username)}")
        WebDriverWait(driver,25).until(EC.presence_of_element_located((By.TAG_NAME,"body")))
        submissions=parse_submission_list(driver.page_source)[:limit]; details=[]
        for raw in submissions:
            driver.get(raw.source_url); WebDriverWait(driver,25).until(EC.presence_of_element_located((By.TAG_NAME,"body")))
            source, lang=parse_solution_page(driver.page_source)
            if lang=="Unknown": lang=raw.language
            if not source: raise CodeChefAuthError(f"Could not extract source code from submission {raw.submission_id}")
            driver.get(f"{BASE_URL}/problems/{quote(raw.problem_id)}")
            WebDriverWait(driver,25).until(EC.presence_of_element_located((By.TAG_NAME,"body")))
            details.append(CodeChefSubmissionDetail(raw, source, lang, parse_problem_metadata(driver.page_source)))
        return details
    finally: driver.quit()

def fetch_all_accepted_keys(max_pages: int = 100) -> set[str]:
    """Return existing accepted problem/language keys only; never persist source."""
    username, password = _credentials(); driver = build_driver(); keys=set(); seen=set()
    try:
        _login(driver, username, password)
        for page in range(max_pages):
            driver.get(f"{RECENT_USER_URL}?user_handle={quote(username)}&page={page}")
            WebDriverWait(driver,25).until(EC.presence_of_element_located((By.TAG_NAME,"body")))
            items=parse_submission_list(driver.page_source)
            new=[x for x in items if x.submission_id not in seen]
            if not new: break
            for item in new:
                seen.add(item.submission_id); lang=item.language
                if lang=="Unknown":
                    driver.get(item.source_url); WebDriverWait(driver,25).until(EC.presence_of_element_located((By.TAG_NAME,"body")))
                    _,lang=parse_solution_page(driver.page_source)
                if lang!="Unknown": keys.add(f"codechef::{item.problem_id}::{lang.lower()}")
        # The paginated feed is authoritative for older rows; profile is a useful
        # fallback because CodeChef sometimes changes the recent-feed markup.
        if not keys:
            driver.get(f"{BASE_URL}/users/{quote(username)}")
            WebDriverWait(driver,25).until(EC.presence_of_element_located((By.TAG_NAME,"body")))
            for item in parse_submission_list(driver.page_source):
                lang=item.language
                if lang!="Unknown": keys.add(f"codechef::{item.problem_id}::{lang.lower()}")
        return keys
    finally: driver.quit()
