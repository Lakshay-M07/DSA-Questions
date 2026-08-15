# DSA Questions

Automatically tracks accepted DSA submissions from **LeetCode, CodeChef, and HackerRank** using GitHub Actions.

## How it works

- GitHub Actions checks the supported platforms approximately every 20 minutes.
- Only accepted submissions are eligible.
- A submission is uniquely identified by **platform + problem + language**.
- Re-submitting the same problem in the same language does not create another record.
- The submitted source code is stored in the repository.
- Difficulty and official tags are preserved as metadata; a primary category is used for the folder hierarchy so solutions are not duplicated across tag folders.
- The README will contain the generated progress dashboard once the platform adapters are enabled.

## Repository structure

```text
Platform/
└── Language/
    └── Category/
        └── Easy | Medium | Hard/
            └── Question.ext
```

## Automation status

| Platform | Adapter | Status |
|---|---|---|
| LeetCode | Authenticated submission sync | In progress |
| CodeChef | Authenticated submission sync | In progress |
| HackerRank | Authenticated submission sync | In progress |

> Platform credentials are stored as GitHub Actions Secrets and are never committed to this repository.
