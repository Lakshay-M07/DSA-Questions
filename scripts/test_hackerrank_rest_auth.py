import os

from scripts.hackerrank_adapter import HackerRankClient, parse_submission


def main():
    session_id = os.environ.get("HACKERRANK_SESSION_ID")
    email = os.environ.get("HACKERRANK_EMAIL")
    password = os.environ.get("HACKERRANK_PASSWORD")

    if not session_id and (not email or not password):
        raise SystemExit(
            "HACKERRANK_SESSION_ID or HACKERRANK_EMAIL/HACKERRANK_PASSWORD secrets are required."
        )

    auth_mode = "browser session cookie" if session_id else "email/password fallback"
    print(f"Testing HackerRank authentication using {auth_mode}...")

    client = HackerRankClient(email, password, session_id=session_id)
    records = client.fetch_submissions(limit=1000)
    accepted = [parsed for parsed in (parse_submission(record) for record in records) if parsed]

    print(f"Submission records returned: {len(records)}")
    print(f"Accepted records returned: {len(accepted)}")

    for submission in accepted:
        print(
            "Accepted submission: "
            f"{submission.problem_id} / {submission.title} / {submission.language} / {submission.submission_id}"
        )

    if session_id:
        print("HACKERRANK_SESSION_ID authentication path is working.")
    else:
        print("HackerRank email/password fallback authentication path is working.")

    print("HackerRank read-only authentication/submission test passed.")


if __name__ == "__main__":
    main()
