import http.cookiejar
import json
import os
import re
import urllib.parse
import urllib.request

from bs4 import BeautifulSoup

BASE_URL = "https://www.hackerrank.com"
LOGIN_PAGE = f"{BASE_URL}/auth/login"
REST_LOGIN = f"{BASE_URL}/rest/auth/login"
SUBMISSIONS_URL = f"{BASE_URL}/rest/contests/master/submissions/?offset=0&limit=10"

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36"


def request(opener, url, data=None, headers=None):
    body = None if data is None else urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, headers=headers or {}, method="POST" if data is not None else "GET")
    return opener.open(req, timeout=30)


def main():
    login = os.environ.get("HACKERRANK_EMAIL")
    password = os.environ.get("HACKERRANK_PASSWORD")
    if not login or not password:
        raise SystemExit("HackerRank credentials are missing.")

    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    base_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json,text/plain,*/*",
    }

    print("Opening current HackerRank Community login page...")
    page = request(opener, LOGIN_PAGE, headers=base_headers)
    page_text = page.read().decode("utf-8", errors="replace")
    print("LOGIN PAGE STATUS:", page.status)
    if page.status != 200:
        raise RuntimeError(f"Current HackerRank login page returned HTTP {page.status}.")

    soup = BeautifulSoup(page_text, "html.parser")
    csrf = None
    meta = soup.find("meta", attrs={"id": "csrf-token"})
    if meta:
        csrf = meta.get("content")
    if not csrf:
        match = re.search(r'csrf[_-]?token["\']?\s*[:=]\s*["\']([^"\']+)', page_text, re.I)
        if match:
            csrf = match.group(1)

    login_headers = dict(base_headers)
    login_headers["Content-Type"] = "application/x-www-form-urlencoded"
    login_headers["Referer"] = LOGIN_PAGE
    if csrf:
        login_headers["x-csrf-token"] = csrf
        print("CSRF token found on current login page.")
    else:
        print("No CSRF token exposed in current login HTML; continuing without one.")

    print("Testing HackerRank Community REST authentication...")
    try:
        response = request(
            opener,
            REST_LOGIN,
            data={"login": login, "password": password, "remember_me": "false", "fallback": "true"},
            headers=login_headers,
        )
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HackerRank REST authentication returned HTTP {exc.code}.") from exc

    print("REST LOGIN STATUS:", response.status)
    response_text = response.read().decode("utf-8", errors="replace")
    try:
        payload = json.loads(response_text)
    except ValueError as exc:
        raise RuntimeError("HackerRank REST login did not return JSON.") from exc

    returned_csrf = payload.get("csrf_token")
    if returned_csrf:
        base_headers["x-csrf-token"] = returned_csrf
        print("Authenticated REST session returned a CSRF token.")

    print("Authenticated session established; cookie names:", ", ".join(sorted(c.name for c in jar)))

    print("Testing authenticated personal submissions endpoint...")
    submissions = request(opener, SUBMISSIONS_URL, headers=base_headers)
    submissions_text = submissions.read().decode("utf-8", errors="replace")
    print("SUBMISSIONS STATUS:", submissions.status)
    try:
        data = json.loads(submissions_text)
    except ValueError as exc:
        raise RuntimeError("HackerRank submissions endpoint did not return JSON.") from exc

    models = data.get("models")
    if not isinstance(models, list):
        raise RuntimeError("HackerRank submissions response has no 'models' list.")

    accepted = sum(item.get("status") == "Accepted" for item in models if isinstance(item, dict))
    print(f"Submission records returned: {len(models)}")
    print(f"Accepted records in returned page: {accepted}")
    print("Authenticated HackerRank REST submission access test passed.")


if __name__ == "__main__":
    main()
