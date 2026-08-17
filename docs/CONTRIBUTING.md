# Contributing

Keep changes focused on the DSA tracker itself.

## Before changing code

- Preserve the Platform → Language → Category → Difficulty structure.
- Do not commit credentials or platform session values.
- Avoid backfilling historical submissions unless the repository policy is intentionally changed.
- Keep dashboard figures derived from committed repository data.

## Validation

Run the repository test suite with:

```bash
python -m pytest -q
```

For dashboard-only work, also run:

```bash
python -m scripts.dashboard_generator
```

Generated README changes should be limited to the marked dashboard section.
