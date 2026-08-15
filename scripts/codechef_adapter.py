"""CodeChef web adapter used by the GitHub Actions sync job.

All browser automation runs inside GitHub Actions. The adapter only reads
accepted submissions, submitted source, and public problem metadata.
"""

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
    if re.search(r"c\+\+|cpp|gnu\+\+", t):
        return "C++"
    if re.search(r"javascript|node\.js|nodejs", t):
        return "JavaScript"
    if re.search(r"python|python3", t):
        return "Python"
    if re.search(r"java", t):
        return "Java"
    if re.search(r"\bc\b|gcc", t):
        return "C"
    return "Unknown"


def _extract_problem_id(href: str) -> str:
    match = re.search(r"/problems/([^/?#]+)", href or "")
    return match.group(1) if match else ""


def _extract_time(node) -> str:
    if not node:
        return ""
    for candidate in [node, *node.find_all(True)]:
        for attr in ("datetime", "data-time", "data-timestamp", "title"):
            value = candidate.get(attr)
            if value and re.search(r"\d", str(value)):
                return str(value).strip()
    return ""


def parse_submission_list(html: str) -> list[CodeChefRawSubmission]:
    """Parse a CodeChef profile/recent-submissions page for Accepted rows."""
    soup = BeautifulSoup(html, "html.parser")
    results: list[CodeChefRawSubmission] = []

    for link in soup.select('a[href*="/viewsolution/"]'):
        solution_href = link.get("href", "")
        match = re.search(r"/viewsolution/(\d+)", solution_href)
        if not match:
            continue
        submission_id = match.group(1)

        node = link
        row_text = ""
        for _ in range(7):
            if not node:
                break
            candidate = _text(node.get_text(" ", strip=True))
            if re.search(r"\b(Accepted|Wrong Answer|Runtime Error|Compilation Error)\b", candidate, re.I):
                row_text = candidate
                break
            node = node.parent

        if not re.search(r"\bAccepted\b", row_text, re.I):
            continue

        problem_link = None
        if node:
            problem_link = node.select_one('a[href*="/problems/"]')
        if not problem_link:
            parent = link.find_parent()
            problem_link = parent.select_one('a[href*="/problems/"]') if parent else None

        problem_href = problem_link.get("href", "") if problem_link else ""
        problem_id = _extract_problem_id(problem_href)
        title = _text(problem_link.get_text(" ", strip=True)) if problem_link else problem_id
        language = _detect_language(row_text)
        accepted_at = _extract_time(node)

        source_url = solution_href if solution_href.startswith("http") else f"{BASE_URL}{solution_href}"
        results.append(CodeChefRawSubmission(
            submission_id=submission_id,
            problem_id=problem_id,
            title=title,
            language=language,
            source_url=source_url,
            accepted_at=accepted_at,
        ))

    seen: set[str] = set()
    unique: list[CodeChefRawSubmission] = []
    for item in results:
        if item.submission_id not in seen:
            seen.add(item.submission_id)
            unique.append(item)
    return unique


def parse_solution_page(html: str) -> tuple[str, str]:
    """Return (source_code, language) from a CodeChef solution page."""
    soup = BeautifulSoup(html, "html.parser")
    candidates = soup.select("pre, code, textarea")
    source = max((_text_preserve(c) for c in candidates), key=len, default="")
    language = _detect_language(_text(soup))
    return source, language


def _text_preserve(node) -> str:
    if not node:
        return ""
    return node.get_text("", strip=False).replace("\r\n", "\n").strip()


def _difficulty_from_rating(rating: int | None) -> tuple[str | None, str | None]:
    if rating is None:
        return None, None
    if rating <= 1000:
        return "Easy", "codechef_official_rating_mapping"
    if rating <= 1800:
        return "Medium", "codechef_official_rating_mapping"
    return "Hard", "codechef_official_rating_mapping"


def parse_problem_metadata(html: str) -> CodeChefProblemMetadata:
    soup = BeautifulSoup(html, "html.parser")
    page_text = _text(soup.get_text(" ", strip=True))
    rating = None
    patterns = (
        r"difficulty\s*rating[^0-9]{0,20}(\d{2,4})",
        r"difficultyRating[^0-9]{0,20}(\d{2,4})",
        r"\"difficulty\"\s*[:=]\s*\"?(\d{2,4})",
    )
    for pattern in patterns:
        match = re.search(pattern, page_text, re.I)
        if match:
            rating = int(match.group(1))
            break

    tags: list[str] = []
    for link in soup.select('a[href*="/tags/"]'):
        label = _text(link.get_text(" ", strip=True))
        if label and len(label) <= 60 and label.lower() not in {x.lower() for x in tags}:
            tags.append(label)

    difficulty, source = _difficulty_from_rating(rating)
    return CodeChefProblemMetadata(
        difficulty=difficulty,
        difficulty_source=source,
        difficulty_rating=rating,
        tags=tuple(tags),
    )


def build_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1440,1200")
    options.add_argument("--disable-gpu")
    return webdriver.Chrome(options=options)


def _first_visible_interactable(elements):
    for element in elements:
        try:
            if element.is_displayed() and element.is_enabled():
                return element
        except Exception:
            continue
    return None


def _login(driver: webdriver.Chrome, username_or_email: str, password: str) -> None:
    driver.get(LOGIN_URL)
    wait = WebDriverWait(driver, 35)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    def visible_inputs():
        return [x for x in driver.find_elements(By.CSS_SELECTOR, "input") if x.is_displayed() and x.is_enabled()]

    def input_description(x):
        return " | ".join(str(x.get_attribute(name) or "") for name in ("type", "name", "id", "placeholder", "aria-label", "autocomplete"))

    def find_username():
        ranked = []
        for x in visible_inputs():
            attrs = input_description(x).lower()
            if x.get_attribute("type") == "password":
                continue
            score = 0
            if "username" in attrs:
                score += 10
            if "email" in attrs:
                score += 8
            if "login" in attrs:
                score += 5
            if x.get_attribute("autocomplete") in ("username", "email"):
                score += 10
            ranked.append((score, x))
        ranked.sort(key=lambda pair: pair[0], reverse=True)
        return ranked[0][1] if ranked and ranked[0][0] > 0 else None

    def find_password():
        return _first_visible_interactable([x for x in visible_inputs() if x.get_attribute("type") == "password"])

    try:
        username = wait.until(lambda d: find_username())
        password_input = wait.until(lambda d: find_password())
    except TimeoutException as exc:
        visible = [input_description(x) for x in visible_inputs()]
        raise CodeChefAuthError(f"Could not locate the CodeChef login fields. URL={driver.current_url!r}, title={driver.title!r}, visible_inputs={visible!r}") from exc

    try:
        username.click(); username.clear(); username.send_keys(username_or_email)
        password_input.click(); password_input.clear(); password_input.send_keys(password)
    except ElementNotInteractableException as exc:
        raise CodeChefAuthError("CodeChef login fields were found but could not be interacted with.") from exc

    login_button = None
    for button in driver.find_elements(By.CSS_SELECTOR, "button, input[type='submit']"):
        try:
            label = _text(button.text or button.get_attribute("value") or button.get_attribute("aria-label") or "")
            if button.is_displayed() and button.is_enabled() and re.search(r"^log\s*in$|^login$", label, re.I):
                login_button = button
                break
        except Exception:
            continue

    if login_button:
        login_button.click()
    else:
        password_input.submit()

    try:
        wait.until(lambda d: "/login" not in d.current_url.lower())
    except TimeoutException as exc:
        raise CodeChefAuthError("CodeChef login did not navigate away from /login. Credentials may be invalid or CodeChef may require an additional verification step.") from exc


def _credentials() -> tuple[str, str]:
    username = os.environ.get("CODECHEF_USERNAME")
    password = os.environ.get("CODECHEF_PASSWORD")
    if not username or not password:
        raise CodeChefAuthError("CODECHEF_USERNAME/CODECHEF_PASSWORD are not set.")
    return username, password


def fetch_recent_accepted(limit: int = 20) -> list[CodeChefRawSubmission]:
    username, password = _credentials()
    driver = build_driver()
    try:
        _login(driver, username, password)
        driver.get(f"{BASE_URL}/users/{username}")
        WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        return parse_submission_list(driver.page_source)[:limit]
    finally:
        driver.quit()


def fetch_recent_accepted_details(limit: int = 20) -> list[CodeChefSubmissionDetail]:
    username, password = _credentials()
    driver = build_driver()
    try:
        _login(driver, username, password)
        driver.get(f"{BASE_URL}/users/{username}")
        WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        submissions = parse_submission_list(driver.page_source)[:limit]
        return _fetch_details_with_driver(driver, submissions)
    finally:
        driver.quit()


def _fetch_details_with_driver(driver: webdriver.Chrome, submissions: list[CodeChefRawSubmission]) -> list[CodeChefSubmissionDetail]:
    details: list[CodeChefSubmissionDetail] = []
    for item in submissions:
        driver.get(item.source_url)
        WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        source, page_language = parse_solution_page(driver.page_source)
        language = page_language if page_language != "Unknown" else item.language
        if not source:
            raise CodeChefAuthError(f"Could not extract source code from CodeChef submission {item.submission_id}.")
        driver.get(f"{BASE_URL}/problems/{quote(item.problem_id)}")
        WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        metadata = parse_problem_metadata(driver.page_source)
        details.append(CodeChefSubmissionDetail(raw=item, source=source, language=language, metadata=metadata))
    return details


def fetch_all_accepted_keys(max_pages: int = 100) -> set[str]:
    """Read accepted submissions for the account without downloading source code.

    CodeChef's authenticated user profile is the same source used by the
    successful recent-submissions/source tests. We paginate that profile and
    use the recent/user endpoint only as a fallback if the profile returns no
    submission rows. This avoids creating a false empty baseline when the
    recent/user page has changed its HTML/API rendering.
    """
    username, password = _credentials()
    driver = build_driver()
    try:
        _login(driver, username, password)
        keys: set[str] = set()
        seen_submission_ids: set[str] = set()

        # Primary source: authenticated profile, which is already proven to
        # work for the CodeChef source-extraction workflow.
        for page in range(max_pages):
            url = f"{BASE_URL}/users/{quote(username)}"
            if page:
                url += f"?page={page}"
            driver.get(url)
            WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            items = parse_submission_list(driver.page_source)
            new_items = [x for x in items if x.submission_id not in seen_submission_ids]
            if not new_items:
                break
            for item in new_items:
                seen_submission_ids.add(item.submission_id)
                if item.problem_id and item.language:
                    keys.add(f"codechef::{item.problem_id}::{item.language.lower()}")

        # Safety fallback: if the profile yielded nothing, try CodeChef's
        # recent/user view rather than accepting an empty baseline.
        if not keys:
            for page in range(max_pages):
                url = f"{RECENT_USER_URL}?user_handle={quote(username)}&page={page}"
                driver.get(url)
                WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                items = parse_submission_list(driver.page_source)
                new_items = [x for x in items if x.submission_id not in seen_submission_ids]
                if not new_items:
                    break
                for item in new_items:
                    seen_submission_ids.add(item.submission_id)
                    if item.problem_id and item.language:
                        keys.add(f"codechef::{item.problem_id}::{item.language.lower()}")
        return keys
    finally:
        driver.quit()
