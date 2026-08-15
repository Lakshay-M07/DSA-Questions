"""Authenticated CodeChef submission reader for GitHub Actions.

This module intentionally performs read-only browser automation. It logs into
CodeChef, reads the user's recent submission list, and opens only Accepted
submission pages to retrieve source code and metadata.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "https://www.codechef.com"
LOGIN_URL = f"{BASE_URL}/login"


@dataclass(frozen=True)
class CodeChefRawSubmission:
    submission_id: str
    problem_id: str
    title: str
    status: str
    language: str
    source_url: str
    submitted_at: str = ""


class CodeChefAuthError(RuntimeError):
    pass


def _text(node) -> str:
    return " ".join(node.get_text(" ", strip=True).split()) if node else ""


def parse_submission_list(html: str) -> list[CodeChefRawSubmission]:
    """Parse submission rows/links without requiring a live browser.

    CodeChef has changed its profile markup over time, so this parser uses
    stable semantic signals (submission/viewsolution links and row text) rather
    than relying on a single generated CSS class.
    """
    soup = BeautifulSoup(html, "html.parser")
    results: list[CodeChefRawSubmission] = []
    seen: set[str] = set()

    for link in soup.select('a[href*="/viewsolution/"]'):
        href = link.get("href", "")
        match = re.search(r"/viewsolution/(\d+)", href)
        if not match:
            continue
        submission_id = match.group(1)
        if submission_id in seen:
            continue
        seen.add(submission_id)

        row = link
        for _ in range(5):
            if row.parent is None:
                break
            row = row.parent
            row_text = _text(row)
            if "Accepted" in row_text or "Wrong Answer" in row_text or "Runtime Error" in row_text:
                break

        row_text = _text(row)
        status = "Accepted" if re.search(r"\bAccepted\b", row_text, re.I) else ""
        if not status:
            # Do not classify unknown rows as accepted.
            continue

        problem_id = ""
        for candidate in row.select('a[href*="/problems/"]'):
            m = re.search(r"/problems/([^/?#]+)", candidate.get("href", ""))
            if m:
                problem_id = m.group(1).upper()
                break
        if not problem_id:
            # Some profile layouts expose a problem code as plain text.
            code_match = re.search(r"\b[A-Z][A-Z0-9_]{2,15}\b", row_text)
            problem_id = code_match.group(0) if code_match else submission_id

        title = _text(link)
        if title.lower() in {"view solution", "solution", "viewsolution"} or not title:
            problem_link = row.select_one('a[href*="/problems/"]')
            title = _text(problem_link) or problem_id

        language = ""
        for lang in ("C++", "C", "Python", "Java", "JavaScript"):
            if re.search(rf"\b{re.escape(lang)}\b", row_text, re.I):
                language = lang
                break

        results.append(
            CodeChefRawSubmission(
                submission_id=submission_id,
                problem_id=problem_id,
                title=title,
                status=status,
                language=language,
                source_url=urljoin(BASE_URL, href),
            )
        )

    return results


def parse_solution_page(html: str) -> tuple[str, str]:
    """Return (source_code, language) from a CodeChef solution page."""
    soup = BeautifulSoup(html, "html.parser")

    # Prefer code/pre blocks; CodeChef has used both pre and textarea/code
    # presentations in different generations of the site.
    candidates = soup.select("pre, code, textarea")
    source = max((_text_preserve(c) for c in candidates), key=len, default="")

    language = ""
    page_text = _text(soup)
    for candidate in ("C++", "C", "Python", "JavaScript", "Java"):
        if re.search(rf"\b{re.escape(candidate)}\b", page_text, re.I):
            language = candidate
            break
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


def _login(driver: webdriver.Chrome, username_or_email: str, password: str) -> None:
    driver.get(LOGIN_URL)
    wait = WebDriverWait(driver, 25)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input")))

    inputs = driver.find_elements(By.CSS_SELECTOR, "input")
    text_inputs = [x for x in inputs if x.get_attribute("type") in (None, "", "text", "email")]
    password_inputs = [x for x in inputs if x.get_attribute("type") == "password"]
    if not text_inputs or not password_inputs:
        raise CodeChefAuthError("Could not locate CodeChef login fields.")

    text_inputs[0].clear()
    text_inputs[0].send_keys(username_or_email)
    password_inputs[0].clear()
    password_inputs[0].send_keys(password)

    # Submit the form rather than depending on a generated button class.
    password_inputs[0].submit()
    time.sleep(3)

    if "/login" in driver.current_url.lower():
        # Give client-side validation/navigation a little more time.
        time.sleep(3)
    if "/login" in driver.current_url.lower():
        raise CodeChefAuthError("CodeChef login was not accepted. Check the credentials.")


def fetch_recent_accepted(limit: int = 20) -> list[CodeChefRawSubmission]:
    """Log in and fetch recent Accepted submissions, including source URLs.

    This is deliberately read-only: no submission, profile, or repository
    mutation is performed.
    """
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
