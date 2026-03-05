# Contributing

## Setup

```bash
git clone https://github.com/m8tes/m8tes-python
cd m8tes-python
make install
```

## Development workflow

We use TDD. Write a failing test first, then implement.

```bash
make check          # lint + type-check + unit tests (run before every PR)
make test-unit      # fast unit tests only
make test-integration  # requires backend at localhost:8000
```

## Submitting a PR

- Tests must pass: `make check`
- Add a `CHANGELOG.md` entry describing what changed
- Bump the version in `pyproject.toml` (patch / minor / major following semver)
- Keep the PR description short: what changed, why, and how to verify it

## Reporting bugs

Use the [bug report template](https://github.com/m8tes/m8tes-python/issues/new?template=bug_report.md).

## Requesting features

Use the [feature request template](https://github.com/m8tes/m8tes-python/issues/new?template=feature_request.md).
