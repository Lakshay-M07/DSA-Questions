"""Read-only LeetCode authentication smoke test for GitHub Actions."""

from __future__ import annotations

import json
import os
import sys
import urllib.request

ENDPOINT = "https://leetcode.com/graphql"

QUERY = """
query {
  userStatus {
    isSignedIn
    username
  }
}
"""


def main() -> int:
    session = os.environ.get("LEETCODE_SESSION")
    csrf = os.environ.get("LEETCODE_CSRF_TOKEN")

    if not session or not csrf:
        print("LeetCode authentication secrets are not available to this workflow.")
        return 1

    payload = json.dumps({"query": QUERY}).encode("utf-8")
    request = urllib.request.Request(
        ENDPOINT,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": "https://leetcode.com",
            "Referer": "https://leetcode.com/",
            "x-csrftoken": csrf,
            "Cookie": f"LEETCODE_SESSION={session}; csrftoken={csrf}",
            "User-Agent": "Mozilla/5.0 GitHubActions-DsaQuestions/1.0",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
    except Exception as exc:
        print(f"LeetCode GraphQL request failed: {type(exc).__name__}")
        return 1

    if result.get("errors"):
        print("LeetCode GraphQL returned an error.")
        return 1

    status = (result.get("data") or {}).get("userStatus") or {}
    if not status.get("isSignedIn"):
        print("LeetCode authentication was rejected.")
        return 1

    username = status.get("username") or "unknown"
    print(f"LeetCode authentication successful for username: {username}")
    print("Read-only authentication test passed; no submissions were imported or changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
