# Repository Automation

The repository uses GitHub Actions to synchronize accepted DSA submissions and refresh the root progress dashboard.

## Sync cadence

The main synchronization workflow runs on a roughly 20-minute schedule and can also be started manually.

## Data flow

1. Authenticate against the configured platforms using GitHub Actions secrets.
2. Discover eligible accepted submissions.
3. Deduplicate by platform, problem, and language.
4. Store accepted source and metadata in the repository.
5. Regenerate the root README dashboard from committed data.
6. Commit the README only when the generated dashboard changes.

## Safety rules

Credentials stay in GitHub Actions secrets. Dashboard generation reads committed repository state and does not use an external database or hosted service.
