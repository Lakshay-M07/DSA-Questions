import os
import re

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.hackerrank.com"
LOGIN_PAGE = f"{BASE_URL}/auth/login"
REST_LOGIN = f"{BASE_URL}/rest/auth/login"
SUBMISSIONS_URL = f"{BASE_URL}/rest/contests/master/submissions/?offset=0&limit=1000"
SUBMISSIONS_PAGE = f"{BASE_URL}/submissions/all"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
}


def main():
    login = os.environ.get("HACKERRANK_EMAIL")
    password = os.environ.get("HACKERRANK_PASSWORD")
    if not login or not password:
        raise SystemExit("HackerRank credentials are missing.")

    session = requests.Session()
    session.headers.update(HEADERS)

    print("Opening current HackerRank Community login page...")
    page = session.get(LOGIN_PAGE, timeout=30)
    print("LOGIN PAGE STATUS:", page.status_code)
    if page.status_code != 200:
        raise RuntimeError(f"Current HackerRank login page returned HTTP {page.status_code}.")

    soup = BeautifulSoup(page.text, "html.parser")
    csrf = None
    meta = soup.find("meta", attrs={"id": "csrf-token"})
    if meta:
        csrf = meta.get("content")
    if not csrf:
        match = re.search(r'csrf[_-]?token["\']?\s*[:=]\s*["\']([^"\']+)', page.text, re.I)
        if match:
            csrf = match.group(1)

    login_headers = {"Referer": LOGIN_PAGE}
    if csrf:
        login_headers["x-csrf-token"] = csrf
        print("CSRF token found on current login page.")
    else:
        print("No CSRF token exposed in the current login HTML; continuing without one.")

    print("Testing HackerRank Community REST authentication...")
    response = session.post(
        REST_LOGIN,
        data={
            "login": login,
            "password": password,
            "remember_me": "false",
            "fallback": "true",
        },
        headers=login_headers,
        timeout=30,
        allow_redirects=False,
    )

    print("REST LOGIN STATUS:", response.status_code)
    print("REST LOGIN CONTENT-TYPE:", response.headers.get("content-type"))
    if response.status_code not in (200, 201, 202):
        raise RuntimeError(f"HackerRank REST authentication was not accepted (HTTP {response.status_code}).")

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("HackerRank REST login did not return JSON.") from exc

    returned_csrf = payload.get("csrf_token")
    if returned_csrf:
        session.headers["x-csrf-token"] = returned_csrf
        print("Authenticated REST session returned a CSRF token.")

    cookie_names = sorted(cookie.name for cookie in session.cookies)
    print("Authenticated session established; cookie names:", ", ".join(cookie_names))

    identity_payload = None
    for identity_path in ("/rest/auth/session", "/rest/auth/user", "/rest/users/current"):
        identity = session.get(BASE_URL + identity_path, timeout=30)
        if identity.status_code != 200:
            continue
        try:
            candidate = identity.json()
        except ValueError:
            continue
        if isinstance(candidate, dict):
            identity_payload = candidate
            print("IDENTITY ENDPOINT:", identity_path)
            break

    if identity_payload is None:
        print("IDENTITY CHECK: no supported current-user endpoint returned JSON; continuing.")
    else:
        def find_identity(value):
            if isinstance(value, dict):
                for key in ("username", "username_slug", "handle", "user_name", "name"):
                    candidate = value.get(key)
                    if isinstance(candidate, str) and candidate.strip():
                        return candidate.strip()
                for child in value.values():
                    found = find_identity(child)
                    if found:
                        return found
            elif isinstance(value, list):
                for child in value:
                    found = find_identity(child)
                    if found:
                        return found
            return None

        identity_name = find_identity(identity_payload)
        print("AUTHENTICATED ACCOUNT USERNAME:", identity_name or "not exposed")

    print("Testing authenticated personal submissions endpoint...")
    submissions = session.get(SUBMISSIONS_URL, timeout=30)
    print("SUBMISSIONS STATUS:", submissions.status_code)
    print("SUBMISSIONS CONTENT-TYPE:", submissions.headers.get("content-type"))
    if submissions.status_code != 200:
        raise RuntimeError(f"Authenticated HackerRank submissions endpoint returned HTTP {submissions.status_code}.")

    data = submissions.json()
    models = data.get("models") if isinstance(data, dict) else None
    if not isinstance(models, list):
        raise RuntimeError("HackerRank submissions response has no 'models' list.")

    accepted = sum(item.get("status") == "Accepted" for item in models if isinstance(item, dict))
    print(f"Submission records returned: {len(models)}")
    print(f"Accepted records in returned page: {accepted}")

    if models:
        print("The REST endpoint returned submission records; the adapter can consume them.")
        return

    print("REST endpoint returned zero records; probing the authenticated submissions web page...")
    page = session.get(SUBMISSIONS_PAGE, timeout=30)
    print("SUBMISSIONS PAGE STATUS:", page.status_code)
    print("SUBMISSIONS PAGE CONTENT-TYPE:", page.headers.get("content-type"))
    print("SUBMISSIONS PAGE HTML BYTES:", len(page.content))
    page_soup = BeautifulSoup(page.text, "html.parser")
    submission_links = page_soup.select('a[href*="/submissions/"]')
    challenge_links = page_soup.select('a[href*="/challenges/"]')
    print(f"Submission links found in page HTML: {len(submission_links)}")
    print(f"Challenge links found in page HTML: {len(challenge_links)}")
    print(f"Script tags on submissions page: {len(page_soup.find_all('script'))}")
    print("Authenticated HackerRank REST access succeeded; discovery probe completed.")


if __name__ == "__main__":
    main()
