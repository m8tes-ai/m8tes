# m8tes Python SDK Tests

The SDK test suite is layered on purpose. Fast local tests stay cheap, and the full deterministic V2 parity gate runs only when you ask for it.

## Test Layers

- `tests/unit/`
  Request building, response parsing, pagination, exceptions, helpers, and CLI behavior. These tests mock HTTP and are the default `pytest` target because `pyproject.toml` excludes `integration`, `e2e`, and `smoke` by default.
- `tests/integration/`
  Real-backend integration coverage. `test_v2_integration.py` is the main V2 public-surface suite and exercises the SDK against a live FastAPI app at `http://localhost:8000` unless `E2E_BACKEND_URL` is set.
- `tests/e2e/`
  Expensive full-stack flows. These are mainly legacy `instances` / CLI journeys and rely on a working runtime plus real provider credentials.
- `tests/utils/`
  Shared assertions, factories, and HTTP mocking helpers.

## High-Value Files

- `tests/unit/test_v2_resources.py`
  Core V2 resource request/response coverage.
- `tests/unit/test_v2_auth.py`
  `client.auth` coverage.
- `tests/unit/test_v2_users.py`
  `client.users` coverage.
- `tests/unit/test_v2_settings.py`
  `client.settings` coverage.
- `tests/integration/test_v2_integration.py`
  Real backend parity for the V2 SDK surface.

## Commands

Run from `sdk/py/`.

```bash
# Fast local loop
make test
make test-unit
make test-cov

# Real backend integration
make test-v2-integration
make test-integration          # all integration tests except runtime-marked ones
make test-integration-full     # all integration tests, including runtime-marked ones

# Full-stack / live lanes
make test-e2e
make test-smoke
```

From the repo root:

```bash
make check      # full deterministic repo gate, including V2 integration
make check-v2   # V2-only deterministic backend + SDK gate
```

## Backend Requirements For Integration

The V2 integration suite expects a live FastAPI backend:

```bash
cd /Users/elmar/Environments/agent/fastapi
uv run uvicorn main:app --reload --port 8000
```

Override the backend target with:

```bash
E2E_BACKEND_URL=http://localhost:8001 make test-v2-integration
```

If you want the SDK integration suite to fail instead of skip when the backend catalog is too small, set:

```bash
E2E_REQUIRE_TEST_CATALOG=1 make test-v2-integration
```

The root `make check-v2` target sets this automatically after seeding a minimal test catalog.

## Markers

- `unit`
  Pure SDK tests with mocked dependencies.
- `integration`
  Real-backend SDK tests.
- `runtime`
  Integration tests that need the full agent execution/runtime path.
- `e2e`
  Expensive full-stack flows.
- `smoke`
  Smallest live-confidence subset. Not part of the deterministic PR gate.

## Writing New Tests

- Add request/serialization coverage to unit tests first.
- Add or extend `tests/integration/test_v2_integration.py` when the public V2 SDK workflow changes.
- Use `responses` for unit tests; avoid real network calls outside the integration and E2E layers.
- Prefer explicit happy-path and failure-path coverage for each public helper.

## Extending the Test Suite

- Extend `tests/unit/` first when the change is mostly request/response contract work.
- Extend `tests/integration/test_v2_integration.py` when a public V2 workflow changes.
- Add `tests/e2e/` coverage only when the full runtime or CLI stack must be exercised.
- Keep PR validation deterministic. Provider-backed checks belong outside the default gate.

This suite is meant to give fast local feedback plus one deterministic V2 parity gate before merge.
