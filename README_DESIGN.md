# README Dashboard Design Notes

The root README is intentionally dashboard-first: progress, platform breakdown, streaks, and recent accepted submissions are shown before repository documentation.

## Design principles

- Dashboard-first hierarchy
- Centered summary presentation
- Platform cards grouped horizontally when GitHub rendering permits
- Compact recent-submission table
- Documentation below the data view
- No JavaScript or external dashboard dependencies

The generated dashboard remains bounded by `DASHBOARD:START` and `DASHBOARD:END` markers so automation can safely refresh it without overwriting the surrounding documentation.
