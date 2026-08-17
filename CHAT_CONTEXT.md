# DSA-Questions — Complete Chat / Project Context

> **Purpose:** This document records the full project context available from the DSA-Questions development conversation so future work can continue without losing decisions, constraints, implementation details, debugging history, or the reasoning behind the current architecture.
>
> **Repository:** `Lakshay-M07/DSA-Questions`
> **Primary goal:** A GitHub-only DSA submission tracker for LeetCode, CodeChef, and HackerRank using GitHub Actions.
> **Last documented date:** 2026-08-17

---

## 1. Original Project Goal

The project is a GitHub-only DSA submission tracker. The goal is to automatically collect newly accepted DSA submissions from:

- LeetCode
- CodeChef
- HackerRank

The system should use GitHub Actions as the automation layer and store accepted solutions directly in this repository.

The intended architecture is:

```text
LeetCode / CodeChef / HackerRank
              ↓
      GitHub Actions
       every ~20 min
              ↓
      Fetch submissions
              ↓
    Keep only Accepted
              ↓
 Get source + language + metadata
              ↓
       Duplicate check
              ↓
 Difficulty + category
              ↓
       Create commits
              ↓
        DSA-Questions
```

The project is deliberately GitHub-centric. A self-hosted runner was considered for HackerRank but rejected because it was considered too much overhead for this project.

---

## 2. Core Functional Requirements

### Platforms

The tracker supports:

1. LeetCode
2. CodeChef
3. HackerRank

### Languages

The repository is intended to support:

- C
- C++
- Python
- JavaScript
- Java

Language should be auto-detected/normalized by the platform adapter.

### Submission rules

- Track only submissions made from the point the tracker is configured onward.
- Do **not** backfill old solves.
- Only Accepted/final submissions count.
- If 10 new accepted submissions are discovered in one polling window, process all 10.
- Each newly accepted problem/language combination gets its own Git commit.
- Therefore, 10 newly accepted problem/language combinations can produce 10 commits.
- The same problem + same language must never contribute twice, even if the source changes later.
- The same problem + different language counts separately.
- Store the actual submitted source code.
- Do not create duplicate imports on repeated workflow runs.

---

## 3. Physical Repository Structure

The finalized intended physical structure is:

```text
Platform/
└── Language/
    └── Category/
        └── Easy | Medium | Hard/
            └── Question/
                ├── README.md
                └── Question.ext
```

Examples:

```text
LeetCode/C++/Array/Easy/1-two-sum/
├── README.md
└── 1-two-sum.cpp
```

```text
CodeChef/C++/Array/Easy/DSACPR45/
├── README.md
└── DSACPR45.cpp
```

The repository should preserve the hierarchy. GitHub uses `/` because `/` represents nested folders. The later cosmetic discussion was **not** intended to flatten the repository.

---

## 4. README Format for Problems

The user wants individual problem READMEs to resemble a PushMyCode-style problem page while preserving the Platform → Language → Category → Difficulty → Question folder hierarchy.

A typical README contains:

- Problem title
- Platform
- Question ID
- Difficulty
- Category
- Tags where available
- Language
- Submission timestamp
- Question / problem description
- Solution section

The exact README should preserve useful platform problem information and the actual submitted solution context.

---

## 5. Difficulty Requirements

Difficulty must not be blindly defaulted to Medium.

The intended authoritative multi-tier strategy is:

1. Official platform metadata
2. Platform page/API metadata
3. Structured metadata
4. Independent authoritative source
5. Classifier as a final fallback

The system should never blindly assume Medium merely because metadata is unavailable.

### CodeChef difficulty

Research established that CodeChef practice difficulty has numeric ranges approximately corresponding to:

- 0–500: beginner
- 500–1000: beginner/easy logical
- 1000–1400: beginner
- 1400–1600: intermediate
- 1600–1800: intermediate
- 1800–2000: advanced
- 2000–2500: advanced

The CodeChef adapter maps numeric ratings to the repository's three levels:

```text
<= 1000 → Easy
<= 1800 → Medium
> 1800  → Hard
```

The official CodeChef FAQ says every problem has a difficulty rating, and CodeChef discussions indicate that the numeric rating is more useful than simply relying on relative difficulty tags.

---

## 6. Root README Status

The root README previously described LeetCode, CodeChef, and HackerRank as "In progress" while documentation and implementation were being developed.

The actual implementation has since progressed significantly:

- LeetCode: working
- CodeChef: working
- HackerRank: working with browser-session authentication

Dashboard functionality is still not the main focus of this stage.

---

# 7. Main GitHub Actions Workflow

File:

```text
.github/workflows/sync-submissions.yml
```

Workflow name:

```text
Sync Accepted DSA Submissions
```

Normal triggers:

```yaml
schedule:
  - cron: '7,27,47 * * * *'
workflow_dispatch:
```

This corresponds to approximately every 20 minutes.

Temporary push triggers were used during development/testing but were removed. The normal production triggers are the schedule and manual `workflow_dispatch`.

Permissions:

```yaml
permissions:
  contents: write
```

Concurrency:

```text
Group: dsa-submission-sync
cancel-in-progress: false
```

Runner:

```text
ubuntu-latest
```

Timeout:

```text
15 minutes
```

The workflow checks out the repository with full history (`fetch-depth: 0`), installs Python 3.12, installs `requirements.txt`, configures Git, performs platform authentication checks, runs tests, and executes the synchronization runners.

Git identity used by the workflow:

```text
Name: Lakshay-M07
Email: 222706893+Lakshay-M07@users.noreply.github.com
```

The main runner pushes after synchronization so migration-only commits are also pushed even when no new submissions are found.

---

# 8. Dependencies

The project requirements include:

```text
beautifulsoup4==4.13.4
pytest==8.4.1
selenium==4.34.2
requests
```

`requests` was added for the HackerRank REST/session implementation.

---

# 9. LeetCode Implementation

Main wrapper:

```text
scripts/leetcode_sync_runner.py
```

LeetCode output path:

```text
LeetCode/<Language>/<Category>/<Difficulty>/<problem_id>-<slug>/<problem_id>-<slug>.ext
```

For a new LeetCode submission the runner:

1. Slugifies the problem title.
2. Fetches official problem content using authenticated GraphQL.
3. Uses the GraphQL query:

```graphql
query questionContent($titleSlug: String!) {
  question(titleSlug: $titleSlug) {
    title
    content
  }
}
```

4. Converts HTML content into Markdown/text using the existing `problem_readme._node_to_markdown` functionality.
5. Creates the README.
6. Stores the actual submitted source.
7. Commits README + source + submission state together.

The LeetCode account had zero questions/submissions at the beginning of this project, so no LeetCode baseline was needed.

LeetCode authentication smoke testing worked.

A full wrapper test passed after fixing a module import issue involving the CodeChef adapter.

A real LeetCode example exists in the repository:

```text
LeetCode/C++/Array/Easy/1-two-sum/
```

with commit message similar to:

```text
feat: add LeetCode - Two Sum (C++)
```

---

# 10. CodeChef Implementation

Relevant files include:

```text
scripts/codechef_adapter.py
scripts/sync_runner.py
data/codechef_baseline.json
```

### CodeChef secrets

The implementation uses repository secrets:

```text
CODECHEF_USERNAME
CODECHEF_PASSWORD
```

These are sensitive and must never be printed or requested in chat.

### Browser automation

CodeChef uses Selenium with headless Chrome because the required authenticated pages/source could not reliably be obtained through simple unauthenticated HTTP requests.

### Login

The login implementation was made robust against hidden inputs by locating the visible username/email/password fields.

### Accepted submission parsing

CodeChef submission parsing originally had several issues that were fixed:

- C++ was initially detected incorrectly as C.
- CodeChef represents full accepted submissions using `(100)` in some views, so acceptance detection was updated to handle both `Accepted` and `(100)`.
- Submission links use `/viewsolution/`.
- The parser locates the nearest `<tr>` and extracts the problem link from `/problems/`.
- Problem IDs are extracted from the problem link.
- Language and accepted time are extracted from the row.

### Important HTML parsing bug

An especially important bug occurred because `html.unescape()` was applied too early.

C++ source containing:

```cpp
#include <iostream>
```

could be interpreted by BeautifulSoup as HTML after unescaping, causing source extraction to lose content.

The fix was to avoid blindly calling `html.unescape()` before BeautifulSoup parses the source.

### Source extraction

Source extraction supports several source editor representations, including:

- `<pre>`
- `<code>`
- `<textarea>`
- Ace
- CodeMirror
- Monaco
- source-code classes
- iframes

### Problem metadata

The CodeChef adapter extracts:

- difficulty rating
- tags
- title
- description

If the main page no longer exposes the complete statement, a meta-description fallback is used.

A title fallback was added because some older records had a bad title. The title can be derived from the page/meta description.

### CodeChef classifier

The existing `_codechef_classifier` is reused for category/metadata fallback behavior.

### Final CodeChef path

A known finalized example is:

```text
CodeChef/C++/Array/Easy/DSACPR45/
├── README.md
└── DSACPR45.cpp
```

Known metadata:

```text
Title: Sum of Array elements
Problem ID: DSACPR45
Language: C++
Difficulty: Easy
Primary category: Array
Tags: ["Array"]
Solution path: CodeChef/C++/Array/Easy/DSACPR45/DSACPR45.cpp
```

### CodeChef baseline

The user explicitly wanted existing CodeChef solves excluded.

File:

```text
data/codechef_baseline.json
```

The baseline contains existing keys such as:

```text
codechef::DSACPR37::C++
codechef::DSACPR38::C++
codechef::DSACPR39::C++
```

The baseline stores only keys, not old source code.

DSACPR38 was intentionally not imported.

### CodeChef testing history

Several regressions were found and fixed:

1. Parser incorrectly detected C++ as C.
2. Login selected a hidden input instead of the visible field.
3. Accepted submissions appeared as `(100)` rather than literal `Accepted`.
4. Source extraction returned zero because of the accepted representation and HTML parsing.
5. Early HTML unescaping corrupted C++ source.
6. Import/module execution failed when scripts were run in different ways.
7. Migration commits were not pushed when there were no new submissions.
8. Title fallback regex required correction.
9. Metadata/category migration required correction.

The full-system CodeChef regression suite reached a green state with 12 tests passing during development.

---

# 11. CodeChef Sync Runner

File:

```text
scripts/sync_runner.py
```

The runner wraps the existing synchronization behavior.

It includes a root `sys.path` fix for script/module mode.

It preserves CodeChef-specific README/path behavior while leaving non-CodeChef behavior untouched.

At the bottom, the runner uses:

```python
if __name__ == "__main__":
    sync.main()
    sync._git("push")
```

This ensures migration-only changes are pushed even when no newly accepted submission is imported.

The current DSACPR45 record is preserved in the sync state.

---

# 12. HackerRank Account State

At the start of HackerRank integration, the account had zero HackerRank solved questions/submissions that needed to be backfilled.

Therefore:

- No HackerRank baseline was required.
- No old HackerRank solutions were intended to be imported.
- The first accepted submission after integration was treated as a new submission.

The HackerRank profile used during development was:

```text
https://www.hackerrank.com/profile/lakshay_mohata
```

The login method is email + password when using the fallback authentication path.

---

# 13. HackerRank Authentication Research

Current HackerRank Community login pages were found to be active and support email/username + password.

Relevant pages investigated included:

```text
https://www.hackerrank.com/auth/login
https://www.hackerrank.com/auth/login/new
```

HackerRank documentation currently focuses on enterprise/work APIs, which are not equivalent to a personal Community submission-history API.

Because of that, the personal Community submission API had to be empirically investigated.

Historical research found a 2019 Code Review script that used:

```text
POST https://www.hackerrank.com/rest/auth/login
```

with:

```text
login
password
```

and then accessed:

```text
GET https://www.hackerrank.com/rest/contests/master/submissions/?offset=0&limit=1000
```

Historical individual submission URLs followed the form:

```text
https://www.hackerrank.com/rest/contests/master/challenges/{slug}/submissions/{id}
```

Historical submission JSON contained information such as:

- code
- language
- name
- track
- difficulty

However, the current Community API behavior is different enough that historical endpoints could not simply be assumed to work.

---

# 14. HackerRank Selenium Failure

The first HackerRank implementation attempted browser automation with Selenium.

GitHub Actions was blocked by HackerRank/Akamai before the login form was accessible.

The observed response was effectively:

```text
Login title: Access Denied
Login URL: https://www.hackerrank.com/login.html
Visible body text:
Access Denied
You don't have permission to access "http://www.hackerrank.com/login.html" from this server.
Reference #18....
```

This demonstrated that browser automation from GitHub-hosted runners was blocked at the infrastructure/security layer.

Because of this, the project moved away from the Selenium approach for HackerRank.

---

# 15. HackerRank REST Authentication

The HackerRank adapter moved to `requests.Session()` and the Community REST login flow.

Main adapter:

```text
scripts/hackerrank_adapter.py
```

Main sync wrapper:

```text
scripts/hackerrank_sync_runner.py
```

The REST login endpoint is:

```text
https://www.hackerrank.com/rest/auth/login
```

The current login request uses approximately:

```python
{
    "login": email,
    "password": password,
    "remember_me": "false",
    "fallback": "true",
}
```

The client first opens the login page and attempts to obtain a CSRF token from metadata/HTML if one is exposed, then uses the authenticated session/cookies for subsequent requests.

The session is maintained using `requests.Session()`.

The submissions endpoint used is:

```text
https://www.hackerrank.com/rest/contests/master/submissions/
```

The client expects a JSON response containing a `models` list.

Individual submission source is fetched from:

```text
/rest/contests/master/challenges/{slug}/submissions/{submission_id}
```

Challenge metadata is fetched from:

```text
/rest/contests/master/challenges/{slug}
```

---

# 16. HackerRank REST Discovery Problem

The authenticated REST login worked, but the personal submissions endpoint initially returned:

```text
HTTP 200
Submission records returned: 0
Accepted records in returned page: 0
```

The authenticated submissions web page also returned only a small login/cookie shell and no submission links.

Several query/filter variants and user-scoped routes were investigated. They either returned zero records or 404 responses.

Therefore, the REST email/password route could prove authentication but could not reliably discover the user's current personal submission history.

This was the reason for introducing the browser-session-cookie approach.

---

# 17. HackerRank Session Secret Decision

The user explicitly chose the browser-session approach instead of a self-hosted runner because the self-hosted option was considered not worth the operational complexity.

The chosen secret is:

```text
HACKERRANK_SESSION_ID
```

It contains the value of HackerRank's authenticated `_hrank_session` browser cookie.

The secret was added directly to the GitHub repository's Actions secrets.

**Important:** The session value must never be pasted into chat, source code, logs, or commits.

### How it was conceptually obtained

The user can obtain it from the browser while logged into HackerRank using browser developer tools:

```text
DevTools
→ Application / Storage
→ Cookies
→ https://www.hackerrank.com
→ _hrank_session
→ Value
```

The value is then placed directly into:

```text
GitHub repository
→ Settings
→ Secrets and variables
→ Actions
→ New repository secret
```

with the name:

```text
HACKERRANK_SESSION_ID
```

The value is never supposed to be sent through chat.

---

# 18. HackerRank Session Authentication Risks Discussed

The following risks were discussed:

1. The session can expire.
2. Logging out or account changes can invalidate it.
3. The session cookie is effectively an authentication credential.
4. GitHub Secrets protects it, but it must never be logged.
5. HackerRank anti-bot/security systems could invalidate sessions due to environment/IP changes.
6. The session may need periodic refresh.

The main advantage is that this approach avoids maintaining a self-hosted runner.

---

# 19. HackerRank Adapter Details

The adapter defines:

```text
BASE_URL = https://www.hackerrank.com
LOGIN_URL = https://www.hackerrank.com/auth/login
REST_LOGIN_URL = https://www.hackerrank.com/rest/auth/login
SUBMISSIONS_URL = https://www.hackerrank.com/rest/contests/master/submissions/
```

It supports:

- email/password authentication fallback
- browser session cookie authentication
- submission parsing
- source extraction
- challenge metadata extraction
- language normalization
- difficulty normalization
- category/tag extraction

### Language normalization

The adapter recognizes mappings including:

```text
C / c              → C / .c
C++ / cpp / cxx    → C++ / .cpp
Python / python3   → Python / .py
pypy3 / pypy       → Python / .py
Java               → Java / .java
JavaScript / js    → JavaScript / .js
Kotlin             → Kotlin
Ruby               → Ruby
Go                 → Go
Rust               → Rust
```

The `pypy3 → Python` correction was important because HackerRank reported the language as `pypy3`, but the repository should organize it under the requested Python language category and use a `.py` extension.

### Source extraction

The source extractor recursively searches nested JSON for fields such as:

```text
code
source
source_code
solution
code_content
```

### Model unwrapping

The adapter handles HackerRank's current nested response shape such as:

```json
{
  "model": {
    "...": "..."
  }
}
```

### Problem metadata

The adapter extracts:

- title
- difficulty
- category
- tags
- description

It handles metadata fields such as:

```text
difficulty_name
difficulty
difficultyName
category
track
domain
tags
tag_names
topics
description
problem_statement
body
content
```

For category dictionaries, it prefers fields such as:

```text
track_name
name
label
slug
```

Difficulty is normalized case-insensitively to:

```text
Easy
Medium
Hard
```

---

# 20. HackerRank Submission Parser

The parser accepts only:

```text
status == Accepted
```

It supports both current nested records and historical flatter shapes.

A current-style record can look conceptually like:

```json
{
  "id": "...",
  "status": "Accepted",
  "language": "cpp",
  "challenge": {
    "id": "...",
    "slug": "solve-me-first",
    "name": "Solve Me First"
  }
}
```

Problem ID selection prefers:

1. explicit challenge/problem ID
2. nested challenge ID
3. slug

Title selection prefers the nested challenge name/title.

Source is not backfilled from old submissions unless it is part of a newly discovered accepted submission flow.

---

# 21. HackerRank Session Integration

Optional session support was added to the HackerRank sync runner and adapter.

If:

```text
HACKERRANK_SESSION_ID
```

exists, the implementation is intended to use it as the HackerRank `_hrank_session` cookie and skip the password login route.

If the session secret is absent, email/password remains the fallback.

The main workflow is intended to provide:

```text
HACKERRANK_SESSION_ID
```

to the HackerRank authentication/sync steps.

The adapter tests were green after this integration. One recorded adapter test run was green with the commit message:

```text
Use optional HackerRank session secret in sync runner
```

The associated run was:

```text
Test HackerRank Adapter
run #6
status: completed
conclusion: success
run id: 31962543132
```

---

# 22. First HackerRank Accepted Submission

The user made a new HackerRank accepted submission after the tracker was configured.

Problem:

```text
Say "Hello, World!" With Python
```

Question ID:

```text
7876
```

HackerRank reported the language as:

```text
pypy3
```

The accepted submission was successfully discovered using the browser-session path and imported into the repository.

The submission timestamp recorded in the README was:

```text
2026-08-16T17:12:46+00:00
```

The README showed:

```text
Platform: HackerRank
Question ID: 7876
Difficulty: Easy
Category: ai
Language: pypy3
Submitted: 2026-08-16T17:12:46+00:00
```

The problem statement included examples such as:

```python
print("Hello, World!")
```

and a string variable example.

---

# 23. HackerRank Commit Error

The first actual HackerRank sync successfully discovered the accepted submission and attempted to commit it, but the workflow failed at Git commit creation.

The error was:

```text
error: pathspec 'Add HackerRank: Say "Hello, World!" With Python (pypy3)' did not match any file(s) known to git
```

The traceback showed the commit command was effectively constructed as:

```text
git commit 'Add HackerRank: Say "Hello, World!" With Python (pypy3)'
```

instead of using the required `-m` option.

The result was:

```text
subprocess.CalledProcessError
Command returned non-zero exit status 1
```

The bug was fixed so the commit command properly supplies the message using `-m`.

A README filename/path issue was also corrected during that cleanup.

---

# 24. Incorrect HackerRank `pypy3` Path

After the commit issue was fixed, the submission was imported but the initial language normalization incorrectly treated `pypy3` as an unknown language.

The repository temporarily contained:

```text
HackerRank/pypy3/ai/Easy/7876-say-hello-world-with-python/
```

with a source file similar to:

```text
7876-say-hello-world-with-python.txt
```

This was identified as incorrect.

The language normalization was then corrected so:

```text
pypy3 → Python → .py
```

The existing import was migrated to:

```text
HackerRank/Python/ai/Easy/7876-say-hello-world-with-python/
```

with:

```text
7876-say-hello-world-with-python.py
README.md
```

The duplicate state was corrected from:

```text
hackerrank::7876::pypy3
```

to:

```text
hackerrank::7876::Python
```

so the migration does not become a second logical submission.

---

# 25. HackerRank Category `ai`

The current HackerRank metadata returned a category value of:

```text
ai
```

The user does not want this category to appear in the physical HackerRank path because it is not useful for this particular problem and makes the hierarchy look inconsistent.

The user proposed a cosmetic cleanup so the path becomes:

```text
HackerRank/Python/Easy/7876-say-hello-world-with-python/
```

instead of:

```text
HackerRank/Python/ai/Easy/7876-say-hello-world-with-python/
```

The user specifically said this should be a **minor change** and did not want major architecture changes.

---

# 26. Discussion About Removing Slashes

The user asked whether the GitHub display could look cleaner by removing the category `ai` and removing slashes.

Important clarification:

GitHub uses `/` to represent folder hierarchy. Removing every slash literally would destroy the intended folder structure.

The safe approach discussed is to keep the physical hierarchy:

```text
HackerRank/
└── Python/
    └── Easy/
        └── Question/
```

and simply remove the unwanted `ai` category from HackerRank paths.

Therefore the desired clean HackerRank structure is:

```text
HackerRank/
└── Python/
    └── Easy/
        └── 7876-say-hello-world-with-python/
            ├── README.md
            └── 7876-say-hello-world-with-python.py
```

No change has yet been made for this cosmetic category cleanup in the context of the latest planning discussion unless explicitly implemented later.

---

# 27. Safe Plan for the HackerRank Cosmetic Cleanup

The user asked for a plan before implementation.

The agreed safe plan was:

### Step 1 — Change only HackerRank path generation

Do not change authentication, API fetching, duplicate detection, source extraction, or submission-processing architecture.

Only modify HackerRank folder-generation behavior so the `ai` category is not included.

Desired:

```text
HackerRank/Python/Easy/Question
```

instead of:

```text
HackerRank/Python/ai/Easy/Question
```

### Step 2 — Preserve the hierarchy

Do not flatten the repository. `/` remains because it represents folders.

### Step 3 — Safely migrate the existing submission

Move:

```text
HackerRank/Python/ai/Easy/7876-say-hello-world-with-python/
```

to:

```text
HackerRank/Python/Easy/7876-say-hello-world-with-python/
```

Do not unnecessarily regenerate the source or README.

### Step 4 — Preserve duplicate tracking

Keep the logical key:

```text
hackerrank::7876::Python
```

This must remain the same so the migration is not interpreted as a new solve.

### Step 5 — Add regression tests

Test at minimum:

```text
pypy3 → Python → .py
```

and:

```text
HackerRank metadata category = ai
→ category omitted from physical path
```

Also verify that LeetCode and CodeChef paths remain unchanged.

### Step 6 — Run sync

After the change, the normal sync should discover the existing accepted submission but report it as already imported rather than creating a duplicate.

Expected behavior conceptually:

```text
Accepted submission found
7876 + Python already imported
0 newly imported
```

No second logical solution should be created.

---

# 28. HackerRank Authentication Test Import Error

A separate read-only HackerRank test was updated to use the new session secret, but initially failed before it could test authentication.

The error was:

```text
ModuleNotFoundError: No module named 'scripts'
```

The workflow was executing:

```bash
python scripts/test_hackerrank_rest_auth.py
```

while the script contained:

```python
from scripts.hackerrank_adapter import HackerRankClient, parse_submission
```

When Python directly executes a file inside `scripts/`, the import path can point at `scripts/` instead of the repository root, so the top-level `scripts` package is not necessarily resolvable.

This was recognized as the same type of integration mistake that had previously appeared while combining the LeetCode and CodeChef runners.

The fix was deliberately made in two places:

1. The test script was made robust by explicitly adding the repository root to `sys.path`.
2. The GitHub Actions workflow was changed to run the test as a module:

```bash
python -m scripts.test_hackerrank_rest_auth
```

The test script now uses:

```python
session_id = os.environ.get("HACKERRANK_SESSION_ID")
email = os.environ.get("HACKERRANK_EMAIL")
password = os.environ.get("HACKERRANK_PASSWORD")
```

and selects:

```text
browser session cookie
```

when `HACKERRANK_SESSION_ID` is available, otherwise it falls back to email/password.

It prints:

```text
Testing HackerRank authentication using browser session cookie...
```

when the session secret is used.

The script reports the number of records and accepted records and prints accepted submissions in the form:

```text
problem_id / title / language / submission_id
```

It does not modify the account.

---

# 29. Important HackerRank Test Workflow Details

The read-only workflow is:

```text
.github/workflows/test-hackerrank-rest-auth.yml
```

It:

1. Runs manually using `workflow_dispatch`.
2. Checks out the repository.
3. Sets up Python 3.12.
4. Installs requirements.
5. Exposes these secrets as environment variables:

```text
HACKERRANK_SESSION_ID
HACKERRANK_EMAIL
HACKERRANK_PASSWORD
```

6. Runs:

```bash
python -m scripts.test_hackerrank_rest_auth
```

The test is read-only.

---

# 30. Earlier Read-Only HackerRank Test Result

Before the session-secret test path was fully corrected, the email/password REST authentication test successfully established an authenticated session but returned zero personal submission records.

Representative output included:

```text
LOGIN PAGE STATUS: 200
REST LOGIN STATUS: 200
REST LOGIN CONTENT-TYPE: application/json; charset=utf-8
Authenticated REST session returned a CSRF token.
Authenticated session established.
SUBMISSIONS STATUS: 200
SUBMISSIONS CONTENT-TYPE: application/json; charset=utf-8
Submission records returned: 0
Accepted records in returned page: 0
```

The authenticated submissions web page also returned HTTP 200 but only a very small HTML shell, with:

```text
SUBMISSIONS PAGE HTML BYTES: 350
Submission links found in page HTML: 0
Challenge links found in page HTML: 0
Script tags on submissions page: 0
```

This did not mean the user's account had no submissions; it meant the particular email/password REST discovery route was not exposing the personal history in the current HackerRank implementation.

The browser-session path subsequently proved capable of importing the user's newly accepted submission.

---

# 31. Existing HackerRank Tests and Workflows

The repository contains HackerRank-specific test workflows including:

```text
.github/workflows/test-hackerrank-adapter.yml
.github/workflows/test-hackerrank-auth.yml
.github/workflows/test-hackerrank-client-live.yml
.github/workflows/test-hackerrank-rest-auth.yml
.github/workflows/test-hackerrank-rest.yml
```

The project should avoid proliferating redundant diagnostics once the stable workflow is established. Existing diagnostic workflows are historical development tools unless explicitly retained for maintenance.

---

# 32. HackerRank Adapter Regression Tests

The HackerRank adapter test suite reached a green state with 9 tests during development.

It covered parser behavior, metadata handling, and related adapter functionality.

A later regression was specifically added for language normalization so that:

```text
pypy3
```

is treated as:

```text
Python
.py
```

---

# 33. Important Git Commit Behavior

The project intentionally creates a separate commit for each newly accepted problem/language combination.

Example:

```text
Add HackerRank: Say "Hello, World!" With Python (pypy3)
```

The first attempt failed because `git commit -m` was not constructed correctly. This was fixed.

The commit system must continue to ensure that:

- migration-only changes can be pushed
- duplicate accepted submissions do not create duplicate commits
- separate new accepted problem/language combinations remain separate commits

---

# 34. Duplicate Key Model

The logical identity of a solved problem is based on:

```text
platform + problem_id + language
```

For HackerRank, the current key for the first imported submission is:

```text
hackerrank::7876::Python
```

This is important because the platform may report the implementation language as `pypy3`, while the repository's normalized language is Python.

The key must remain normalized and stable.

Changing the physical path must not change the logical identity.

---

# 35. No Backfill Policy

A major project requirement is that old submissions should not be imported automatically.

The user explicitly stated that existing CodeChef solves should not be added.

The CodeChef baseline mechanism exists specifically to prevent historical solves from becoming new repository imports.

HackerRank had zero historical solves requiring baseline handling at the time of integration, so the first new accepted submission could be imported normally.

LeetCode also had zero prior submissions when integrated.

---

# 36. User Experience Requirements

The user prefers:

- exact instructions
- concrete commands
- minimal unnecessary changes
- testing before major modifications
- no unnecessary architecture changes
- no repeated requests to recreate secrets
- no requests to paste sensitive credentials into chat
- confirmation before cosmetic/structural changes when the project is already stable

The user became frustrated when the same basic script/module integration issue appeared more than once. Future changes should therefore explicitly compare new implementations against already-working LeetCode/CodeChef patterns before committing.

---

# 37. Sensitive Information Rules

Never include or expose actual values of:

```text
CODECHEF_PASSWORD
HACKERRANK_PASSWORD
HACKERRANK_SESSION_ID
```

Never ask the user to paste these secrets into chat.

Use GitHub Actions Secrets directly.

The `_hrank_session` cookie is effectively an authentication credential and must be treated as sensitive.

---

# 38. Current Known-Good State

At the point this document was created, the following high-level state had been achieved:

### LeetCode

- Authentication works.
- Sync architecture works.
- Official problem content retrieval works.
- Example Two Sum C++ solution exists.
- Duplicate logic works.

### CodeChef

- Authentication works.
- Selenium source extraction works.
- Accepted parsing works.
- Difficulty mapping works.
- Baseline works.
- Finalized folder structure works.
- Existing solves are excluded.
- DSACPR45 was successfully migrated to the finalized structure.

### HackerRank

- Browser-session secret is configured.
- Session-based authentication is integrated into the sync path.
- Newly accepted submission discovery works.
- Source extraction works for the imported problem.
- README generation works.
- Commit creation works after fixing the missing `-m` flag.
- `pypy3` normalization has been fixed to Python.
- Duplicate state uses `hackerrank::7876::Python`.
- The existing submission is already in the repository.
- The remaining cosmetic goal is to remove the unwanted `ai` category from the physical HackerRank path while keeping the hierarchy.

---

# 39. Current HackerRank Example

The current imported problem is:

```text
Say "Hello, World!" With Python
```

ID:

```text
7876
```

Normalized language:

```text
Python
```

Difficulty:

```text
Easy
```

Current category returned by HackerRank metadata:

```text
ai
```

Desired physical path after cosmetic cleanup:

```text
HackerRank/Python/Easy/7876-say-hello-world-with-python/
```

Desired files:

```text
README.md
7876-say-hello-world-with-python.py
```

---

# 40. What Must NOT Be Accidentally Changed

During future cleanup, do not unnecessarily modify:

- LeetCode authentication
- LeetCode GraphQL retrieval
- CodeChef Selenium login
- CodeChef source extraction
- CodeChef baseline behavior
- HackerRank session authentication
- HackerRank source extraction
- HackerRank accepted filtering
- duplicate identity keys
- Git commit-per-submission behavior
- no-backfill policy
- GitHub Actions schedule
- repository permissions
- secrets
- the actual submitted source code

Any cosmetic path change should be isolated to HackerRank path/category generation and the safe migration of already-imported HackerRank folders.

---

# 41. Recommended Next Implementation Step

If the user explicitly approves the previously discussed cosmetic cleanup, implement only:

```text
HackerRank/<Language>/<Difficulty>/<Question>
```

instead of:

```text
HackerRank/<Language>/<Category>/<Difficulty>/<Question>
```

for HackerRank.

Then:

1. Add/update a HackerRank path regression test.
2. Confirm LeetCode/CodeChef path tests remain unchanged.
3. Move the existing 7876 directory from the `ai` path to the category-free path.
4. Keep `hackerrank::7876::Python` unchanged.
5. Run the adapter/unit tests.
6. Run the read-only HackerRank session test.
7. Run the main sync.
8. Verify that the already-imported 7876 solution is not duplicated.
9. Verify that the repository contains the clean path.

No other architecture should be changed.

---

# 42. Timeline of Major Debugging Events

## Phase A — LeetCode

- Built the initial LeetCode sync architecture.
- Added authenticated GraphQL problem-content retrieval.
- Added README generation.
- Added source storage.
- Confirmed the account had no old LeetCode submissions, so no baseline was needed.
- Fixed a module import issue involving the CodeChef adapter by registering the adapter in `sys.modules` for the historical top-level import.
- Full wrapper test passed.

## Phase B — CodeChef

- Researched CodeChef login and difficulty metadata.
- Implemented Selenium login.
- Fixed hidden input selection.
- Implemented accepted submission parsing.
- Fixed C++ language detection.
- Fixed `(100)` accepted/full-score representation.
- Implemented source extraction.
- Discovered premature `html.unescape()` corrupted C++ `<iostream>` source.
- Fixed HTML/source parsing.
- Added CodeChef baseline.
- Tested baseline fetching.
- Added problem description extraction.
- Added title fallback.
- Added difficulty/category migration.
- Fixed migration push behavior.
- Finalized DSACPR45 path.
- Regression suite became green.

## Phase C — HackerRank research

- Tested current HackerRank login.
- Attempted Selenium.
- GitHub Actions was blocked by Akamai with Access Denied.
- Researched historical Community REST endpoints.
- Implemented requests-based REST authentication.
- Confirmed authentication but found current personal submissions endpoint returned zero records.
- Tested multiple query/filter/user-scoped approaches.
- Determined that a browser session cookie was the most practical remaining approach.

## Phase D — HackerRank session integration

- Added `HACKERRANK_SESSION_ID` support.
- User created the secret.
- Main sync successfully found the accepted HackerRank submission.
- First commit failed because the Git command lacked `-m`.
- Fixed commit command.
- Submission was imported.
- Found that `pypy3` was incorrectly treated as a new language.
- Fixed `pypy3 → Python → .py`.
- Migrated the existing submission state to `hackerrank::7876::Python`.
- Discussed removing the unwanted `ai` category from the physical HackerRank path.

## Phase E — Read-only test cleanup

- Updated the HackerRank read-only test to prefer the session secret.
- It initially failed with:

```text
ModuleNotFoundError: No module named 'scripts'
```

- Fixed the script import path and changed the workflow to module execution:

```bash
python -m scripts.test_hackerrank_rest_auth
```

- The user then confirmed the overall system was working.

---

# 43. Final Principle for Future Work

**Do not destabilize a working system for cosmetic changes.**

When modifying this repository:

1. Inspect the existing implementation first.
2. Reuse established patterns from the working LeetCode/CodeChef integrations.
3. Keep changes narrowly scoped.
4. Add regression tests before/with behavior changes.
5. Preserve logical duplicate keys when moving files.
6. Never backfill old submissions unless explicitly requested.
7. Never expose secrets.
8. Test authentication separately from sync.
9. Test sync separately from migration.
10. Verify the final Git tree after every migration.

The project is now at the stage where **small, controlled changes are preferable to architectural rewrites**.
