import os

import requests

BASE_URL = "https://www.hackerrank.com"
LOGIN_URL = f"{BASE_URL}/auth/login"
REST_LOGIN = f"{BASE_URL}/rest/auth/login"
SUBMISSIONS_URL = f"{BASE_URL}/rest/contests/master/submissions/?offset=0&limit=1000"
HACKERRANK_USERNAME = "lakshay_mohata"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
}


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


def summarize_json(value):
    if isinstance(value, dict):
        return sorted(value.keys())
    if isinstance(value, list):
        return f"list[{len(value)}]"
    return type(value).__name__


def main():
    login = os.environ.get("HACKERRANK_EMAIL")
    password = os.environ.get("HACKERRANK_PASSWORD")
    if not login or not password:
        raise SystemExit("HackerRank credentials are missing.")

    session = requests.Session()
    session.headers.update(HEADERS)

    print("Opening current HackerRank Community login page...")
    page = session.get(LOGIN_URL, timeout=30)
    print("LOGIN PAGE STATUS:", page.status_code)
    if page.status_code != 200:
        raise RuntimeError(f"Current HackerRank login page returned HTTP {page.status_code}.")

    print("Testing HackerRank Community REST authentication...")
    response = session.post(
        REST_LOGIN,
        data={
            "login": login,
            "password": password,
            "remember_me": "false",
            "fallback": "true",
        },
        headers={"Referer": LOGIN_URL},
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

    returned_csrf = payload.get("csrf_token") if isinstance(payload, dict) else None
    if returned_csrf:
        session.headers["x-csrf-token"] = returned_csrf
        print("Authenticated REST session returned a CSRF token.")

    # Read-only identity check. Never print email, password, tokens, or cookies.
    identity = None
    for path in ("/rest/auth/session", "/rest/auth/user", "/rest/users/current"):
        result = session.get(BASE_URL + path, timeout=30)
        if result.status_code != 200:
            continue
        try:
            candidate = result.json()
        except ValueError:
            continue
        if isinstance(candidate, (dict, list)):
            identity = candidate
            print("IDENTITY ENDPOINT:", path)
            break

    print("AUTHENTICATED ACCOUNT USERNAME:", find_identity(identity or payload) or "not exposed")

    # Probe the known public profile REST resource and likely user-scoped submission routes.
    print(f"Probing HackerRank profile for @{HACKERRANK_USERNAME}...")
    profile_url = f"{BASE_URL}/rest/contests/master/hackers/{HACKERRANK_USERNAME}/profile"
    profile = session.get(profile_url, timeout=30)
    print("PROFILE STATUS:", profile.status_code)
    print("PROFILE CONTENT-TYPE:", profile.headers.get("content-type"))
    if profile.status_code == 200:
        try:
            profile_data = profile.json()
            print("PROFILE JSON SHAPE:", summarize_json(profile_data))
            profile_model = profile_data.get("model") if isinstance(profile_data, dict) else None
            if isinstance(profile_model, dict):
                print("PROFILE MODEL KEYS:", ", ".join(sorted(profile_model.keys())))
        except ValueError:
            print("PROFILE RESPONSE: non-JSON")

    candidate_paths = [
        f"/rest/contests/master/hackers/{HACKERRANK_USERNAME}/submissions/?offset=0&limit=1000",
        f"/rest/contests/master/hackers/{HACKERRANK_USERNAME}/submissions",
        f"/rest/contests/master/hackers/{HACKERRANK_USERNAME}/solved_challenges",
        f"/rest/contests/master/hackers/{HACKERRANK_USERNAME}/challenges",
    ]
    for path in candidate_paths:
        result = session.get(BASE_URL + path, timeout=30)
        print(f"USER ROUTE {path} -> HTTP {result.status_code}")
        if result.status_code != 200:
            continue
        try:
            data = result.json()
        except ValueError:
            print("  JSON: no")
            continue
        print("  JSON SHAPE:", summarize_json(data))
        if isinstance(data, dict):
            models = data.get("models")
            if isinstance(models, list):
                accepted = sum(item.get("status") == "Accepted" for item in models if isinstance(item, dict))
                print(f"  MODELS: {len(models)}; ACCEPTED: {accepted}")

    print("Testing authenticated personal submissions endpoint...")
    submissions = session.get(SUBMISSIONS_URL, timeout=30)
    print("SUBMISSIONS STATUS:", submissions.status_code)
    print("SUBMISSIONS CONTENT-TYPE:", submissions.headers.get("content-type"))
    if submissions.status_code != 200:
        raise RuntimeError(f"Authenticated HackerRank submissions endpoint returned HTTP {submissions.status_code}.")

    try:
        data = submissions.json()
    except ValueError as exc:
        raise RuntimeError("HackerRank submissions endpoint did not return JSON.") from exc

    models = data.get("models") if isinstance(data, dict) else None
    if not isinstance(models, list):
        raise RuntimeError("HackerRank submissions response has no 'models' list.")

    accepted = sum(item.get("status") == "Accepted" for item in models if isinstance(item, dict))
    print(f"Submission records returned: {len(models)}")
    print(f"Accepted records in returned page: {accepted}")
    print("HackerRank read-only authentication/submissions discovery test passed.")


if __name__ == "__main__":
    main()
