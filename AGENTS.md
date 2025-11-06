# Repository Guidelines

## Project Structure & Module Organization

The SDK lives in `m8tes/` with domain modules such as `auth/`, `cli/`, `services/`, and shared helpers in `utils/`. HTTP clients and exceptions sit in `m8tes/http/` and `m8tes/exceptions.py`. Tests mirror the package under `tests/` with `unit/`, `integration/`, and reusable fixtures in `tests/utils/`. Tooling metadata and dependencies are defined in `pyproject.toml`; automation lives in the root `Makefile`.

## Build, Test, and Development Commands

Use `make install` (or `pip install -e ".[dev]") to prepare a local environment. `make test`runs the full pytest suite, while`make test-unit`scopes to fast mocks and`make test-integration`executes external-service checks. Run`make check`before pushing to execute format, lint, type, and test gates. Package releases flow through`make build`followed by`make publish` once credentials are configured.

## Coding Style & Naming Conventions

Code is formatted with Black and Ruff using a 100 character line limit; run `make format` to auto-fix. Adhere to type hints (`mypy` runs in strict optional mode) and prefer descriptive docstrings for public APIs. Use `snake_case` for functions and variables, `PascalCase` for classes, and keep CLI command names aligned with existing verbs (e.g., `mate run`). Keep imports sorted by Ruff's defaults.

## Testing Guidelines

Write tests with pytest, keeping unit coverage under `tests/unit/test_<feature>.py` and integration scenarios in `tests/integration/test_<service>.py`. Mark slower or external calls with the configured markers (`@pytest.mark.integration`, `@pytest.mark.slow`) so they can be excluded locally. Target meaningful coverage and validate new public methods with streaming and auth fixtures. Generate coverage locally with `make test-cov`.

## Commit & Pull Request Guidelines

Recent history favors short, imperative subject lines (`fix client basepath`, `improve keychain retrieval`); follow that pattern, keep subjects under 72 characters, and expand context in the body if needed. Reference GitHub issues when applicable. Pull requests should describe intent, list the commands run, document API or CLI changes, and include screenshots or logs for UX-facing updates. Request review from a maintainer and wait for CI `make check` parity before merging.

## Security & Configuration Tips

Never hard-code API keys; use the `M8TES_API_KEY` and `M8TES_BASE_URL` environment variables or `.env` files managed via `python-dotenv`/`keyring`. Confirm regenerated credentials locally via `m8tes auth status` and avoid committing credential artifacts.

## Engineering Best Practices

- Anchor changes in tests first—write or extend failing pytest cases before altering SDK code so API shifts surface immediately.
- Keep implementations simple and readable—build to the immediate requirements, avoid speculative abstractions, and lean on expressive naming, thin wrappers, and obvious control flow instead of clever tricks.
- Balance startup velocity with quality: skip premature optimization or over-engineered patterns that obscure intent or slow iteration.
- Refactor continuously; once tests pass, revisit the code to collapse duplication, clarify abstractions, and simplify public surfaces.

## Teammates Best Practices

- Mirror backend shapes exactly—update `m8tes/services/` serializers alongside any API change and regenerate fixtures so the CLI stays truthful.
- Keep CLI commands thin: parameter parsing lives in `m8tes/cli/commands/`, business logic stays in services, and shared utilities go through `m8tes/utils/` for reuse.
- Exercise new behaviours with unit tests around serializers plus integration tests that hit the live API using the recorded fixtures in `tests/utils/`.
- Refresh `--help` text, usage examples, and README snippets whenever you add or rename commands so discoverability remains high.
- When publishing, tag the corresponding backend commit and bump the SDK version with a CHANGELOG entry describing any agent-facing changes.
