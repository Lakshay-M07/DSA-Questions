"""CodeChef web adapter used by the GitHub Actions sync job.

This module intentionally keeps all browser automation inside GitHub Actions.
It never submits code; it only reads the user's recent submissions and their
solution pages after authentication.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Iterable

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import ElementNotInteractableException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

BASE_URL = "https://www.codechef.com"
LOGIN_URL = f"{BASE_URL}/login"


class CodeChefAuthError(RuntimeError):
    pass


@dataclass(frozen=True)
class CodeChefRawSubmission:
    submission_id: str
    problem_id: str
    title: str
    language: str
    source_url: str
    status: str = "Accepted"


@dataclass(frozen=True)
class CodeChefSubmissionDetail:
    raw: CodeChefRawSubmission
    source: str
    language: str


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


def parse_submission_list(html: str) -> list[CodeChefRawSubmission]:
    """Parse a CodeChef profile/submissions page for Accepted rows."""
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
        for _ in range(6):
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
            problem_link = link.find_parent().select_one('a[href*="/problems/"]') if link.find_parent() else None

        problem_href = problem_link.get("href", "") if problem_link else ""
        problem_id = _extract_problem_id(problem_href)
        title = _text(problem_link.get_text(" ", strip=True)) if problem_link else problem_id
        language = _detect_language(row_text)

        source_url = solution_href if solution_href.startswith("http") else f"{BASE_URL}{solution_href}"
        results.append(
            CodeChefRawSubmission(
                submission_id=submission_id,
                problem_id=problem_id,
                title=title,
                language=language,
                source_url=source_url,
            )
        )

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
        return [
            x for x in driver.find_elements(By.CSS_SELECTOR, "input")
            if x.is_displayed() and x.is_enabled()
        ]

    def input_description(x):
        return " | ".join(
            str(x.get_attribute(name) or "")
            for name in ("type", "name", "id", "placeholder", "aria-label", "autocomplete")
        )

    def find_username():
        candidates = visible_inputs()
        ranked = []
        for x in candidates:
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
        return _first_visible_interactable(
            [x for x in visible_inputs() if x.get_attribute("type") == "password"]
        )

    try:
        username = wait.until(lambda d: find_username())
        password_input = wait.until(lambda d: find_password())
    except TimeoutException as exc:
        visible = [input_description(x) for x in visible_inputs()]
        title = driver.title
        url = driver.current_url
        raise CodeChefAuthError(
            "Could not locate the CodeChef login fields. "
            f"URL={url!r}, title={title!r}, visible_inputs={visible!r}"
        ) from exc

    try:
        username.click()
        username.clear()
        username.send_keys(username_or_email)
        password_input.click()
        password_input.clear()
        password_input.send_keys(password)
    except ElementNotInteractableException as exc:
        raise CodeChefAuthError("CodeChef login fields were found but could not be interacted with.") from exc

    buttons = driver.find_elements(By.CSS_SELECTOR, "button, input[type='submit']")
    login_button = None
    for button in buttons:
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
        raise CodeChefAuthError(
            "CodeChef login did not navigate away from /login. "
            "Credentials may be invalid or CodeChef may require an additional verification step."
        ) from exc


def fetch_recent_accepted(limit: int = 20) -> list[CodeChefRawSubmission]:
    """Log in and fetch recent Accepted submissions, including source URLs."""
    username = os.environ.get("CODECHEF_USERNAME")
    password = os.environ.get("CODECHEF_PASSWORD")
    if not username or not password:
        raise CodeChefAuthError("CODECHEF_USERNAME/CODECHEF_PASSWORD are not set.")

    driver = build_driver()
    try:
        _login(driver, username, password)
        driver.get(f"{BASE_URL}/users/{username}")
        WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        submissions = parse_submission_list(driver.page_source)
        return submissions[:limit]
    finally:
        driver.quit()


def fetch_recent_accepted_details(limit: int = 20) -> list[CodeChefSubmissionDetail]:
    """Fetch recent Accepted submissions and read their submitted source code."""
    username = os.environ.get("CODECHEF_USERNAME")
    password = os.environ.get("CODECHEF_PASSWORD")
    if not username or not password:
        raise CodeChefAuthError("CODECHEF_USERNAME/CODECHEF_PASSWORD are not set.")

    driver = build_driver()
    try:
        _login(driver, username, password)
        driver.get(f"{BASE_URL}/users/{username}")
        WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        submissions = parse_submission_list(driver.page_source)[:limit]

        details: list[CodeChefSubmissionDetail] = []
        for item in submissions:
            driver.get(item.source_url)
            WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            source, page_language = parse_solution_page(driver.page_source)
            language = page_language if page_language != "Unknown" else item.language
            if not source:
                raise CodeChefAuthError(
                    f"Could not extract source code from CodeChef submission {item.submission_id}."
                )
            details.append(
                CodeChefSubmissionDetail(raw=item, source=source, language=language)
            )
        return details
    finally:
        driver.quit()
