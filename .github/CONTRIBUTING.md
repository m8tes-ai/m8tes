# Contributing

Thanks for helping make the m8tes SDK better.

**We don't currently accept external pull requests.** This repo is synced from our
internal monorepo, so changes land through our own pipeline. The fastest path to a
fix is a well-reproduced issue — we review weekly.

## Reporting bugs

Use the [bug report template](https://github.com/m8tes-ai/m8tes/issues/new?template=bug_report.md).
The more precisely we can reproduce it, the faster it ships:

- SDK version (`pip show m8tes`), Python version, OS
- The smallest snippet that triggers it
- What you expected vs. what happened (include the full traceback and, for API
  errors, `request_id` from the exception)

## Requesting features

Use the [feature request template](https://github.com/m8tes-ai/m8tes/issues/new?template=feature_request.md).
Say what you're trying to build — the use case matters more than the proposed API.

## Running the tests locally

Useful for pinning down a bug before you report it:

```bash
git clone https://github.com/m8tes-ai/m8tes
cd m8tes
make install       # install via uv
make test-unit     # fast, fully offline
make check         # lint + type-check + unit tests
```

(`make test-integration` needs a live m8tes backend and is maintainers-only.)

## Anything else

Security issues: see [SECURITY.md](../SECURITY.md) — never a public issue.
Everything else: **support@m8tes.ai**.
