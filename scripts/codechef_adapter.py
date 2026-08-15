"""CodeChef web adapter used by the GitHub Actions sync job."""

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


def _normalize_embedded_html(html: str) -> str:
    """Normalize CodeChef's escaped HTML response from /recent/user."""
    return html.replace(r"\/", "/")


def _is_accepted_row(row_text: str) -> bool:
    """Recognize both old 'Accepted' labels and current CodeChef '(100)' rows."""
    if re.search(r"\bAccepted\b", row_text, re.I):
        return True
    return bool(re.search(r"\(\s*100(?:\.0+)?\s*\)", row_text))


def parse_submission_list(html: str) -> list[CodeChefRawSubmission]:
    """Parse CodeChef profile or /recent/user markup for accepted submissions."""
    soup = BeautifulSoup(_normalize_embedded_html(html), "html.parser")
    results: list[CodeChefRawSubmission] = []

    for link in soup.select('a[href*="/viewsolution/"]'):
        solution_href = link.get("href", "")
        match = re.search(r"/viewsolution/(\d+)", solution_href)
        if not match:
            continue
        submission_id = match.group(1)

        row = link.find_parent("tr")
        if row is None:
            row = link.parent
            for _ in range(6):
                if row is None:
                    break
                candidate_text = _text(row.get_text(" ", strip=True))
                if row.select_one('a[href*="/problems/"]') or _is_accepted_row(candidate_text):
                    break
                row = row.parent

        row_text = _text(row.get_text(" ", strip=True)) if row else ""
        if not _is_accepted_row(row_text):
            continue

        problem_link = row.select_one('a[href*="/problems/"]') if row else None
        if not problem_link:
            parent = link.parent
            problem_link = parent.select_one('a[href*="/problems/"]') if parent else None

        problem_href = problem_link.get("href", "") if problem_link else ""
        problem_id = _extract_problem_id(problem_href)
        title = _text(problem_link.get_text(" ", strip=True)) if problem_link else problem_id
        language = _detect_language(row_text)
        accepted_at = _extract_time(row)
        source_url = solution_href if solution_href.startswith("http") else f"{BASE_URL}{solution_href}"

        if not problem_id:
            continue

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
    # Pass actual text to _detect_language; passing the BeautifulSoup object to
    # _text is incorrect because _text expects a string.
    page_text = soup.get_text(" ", strip=True)
    language = _detect_language(_text(page_text))
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

    inputs = visible_inputs()
    username_input = _first_visible_interactable([
        x for x in inputs if any(token in input_description(x).lower() for token in ("username", "email", "login"))
    ])
    if username_input is None and inputs:
        username_input = inputs[0]

    password_input = _first_visible_interactable([
        x for x in inputs if (x.get_attribute("type") or "").lower() == "password"
    ])

    if username_input is None:
        raise CodeChefAuthError("Could not find a visible CodeChef username/email input")
    if password_input is None:
        raise CodeChefAuthError("Could not find a visible CodeChef password input")

    username_input.clear()
    username_input.send_keys(username_or_email)
    password_input.clear()
    password_input.send_keys(password)

    buttons = driver.find_elements(By.CSS_SELECTOR, "button, input[type='submit']")
    login_button = _first_visible_interactable([
        b for b in buttons if re.search(r"log\s*in|sign\s*in", _text(b.text or ""), re.I)
    ])
    if login_button:
        login_button.click()
    else:
        password_input.submit()

    try:
        wait.until(lambda d: "/login" not in d.current_url.lower())
    except TimeoutException as exc:
        raise CodeChefAuthError("CodeChef login did not complete; credentials may be invalid or the login page changed") from exc


def fetch_recent_accepted(username: str | None = None, limit: int = 100) -> list[CodeChefSubmissionDetail]:
    username = username or os.environ.get("CODECHEF_USERNAME", "")
    password = os.environ.get("CODECHEF_PASSWORD", "")
    if not username or not password:
        raise CodeChefAuthError("CODECHEF_USERNAME and CODECHEF_PASSWORD are required")

    driver = build_driver()
    try:
        _login(driver, username, password)
        driver.get(f"{BASE_URL}/users/{quote(username)}")
        WebDriverWait(driver, 35).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        submissions = parse_submission_list(driver.page_source)[:limit]

        details: list[CodeChefSubmissionDetail] = []
        for raw in submissions:
            driver.get(raw.source_url)
            WebDriverWait(driver, 35).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            source, language = parse_solution_page(driver.page_source)
            if language == "Unknown":
                language = raw.language
            details.append(CodeChefSubmissionDetail(raw=raw, source=source, language=language))
        return details
    finally:
        driver.quit()
