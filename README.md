# DSA Questions

A GitHub-native archive for accepted Data Structures & Algorithms submissions from **LeetCode, CodeChef, and HackerRank**.

The repository is intentionally automated: GitHub Actions periodically checks the configured platforms, imports eligible accepted submissions, stores the source in a consistent structure, and refreshes the dashboard below.

## 🚀 How to use this repository

### Browse solutions

Solutions are organized by platform, language, category, and difficulty:

```text
Platform/
└── Language/
    └── Category/
        └── Easy | Medium | Hard/
            └── Problem/
                ├── solution.ext
                └── README.md
```

Use the repository tree to study problems by **platform, language, topic, or difficulty**. The README dashboard is generated automatically from committed repository data.

### Automation

- Accepted submissions are synchronized through GitHub Actions.
- A submission is tracked by **platform + problem + language** so duplicate imports are avoided.
- Existing repository contents remain the authoritative source for dashboard totals.
- Platform credentials are stored only as GitHub Actions Secrets and are never committed.
- The dashboard generator updates only its marked section and commits the README only when meaningful dashboard data changes.

## 🧭 Repository goals

- Keep accepted DSA work organized and easy to review.
- Make progress across multiple coding platforms visible at a glance.
- Preserve useful problem metadata such as difficulty, language, and category.
- Keep the entire system GitHub-native without a separate database or hosted dashboard.

<!-- DASHBOARD:START -->
<!-- DASHBOARD:END -->
