# Maintenance Notes

This file records small repository-maintenance notes that are useful when reviewing the automation and its generated dashboard.

- Dashboard data should remain derived from committed repository state.
- Platform credentials belong in GitHub Actions Secrets, not repository files.
- Generated README content is bounded by the dashboard markers.
