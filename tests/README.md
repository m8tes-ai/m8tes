# m8tes Python SDK Tests

The SDK test suite is intentionally layered. Default `pytest` runs stay fast and local, while V2 parity and live-runtime confidence live in explicit opt-in suites.

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

# Full-stack / paid lanes
make test-e2e
make test-smoke
```

From the repo root, `make check-v2` runs the backend V2 integration suite plus the SDK V2 integration suite.

## Backend Requirements For Integration

The V2 integration suite expects a live FastAPI backend:

```bash
cd /Users/elmar/Environments/agent/fastapi
uv run uvicorn main:app --reload --port 8000
```

Override the target with:

```bash
E2E_BACKEND_URL=http://localhost:8001 make test-v2-integration
```

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
  Smallest paid live-confidence subset.

## Writing New Tests

- Add request/serialization coverage to unit tests first.
- Add or extend `tests/integration/test_v2_integration.py` when the public V2 SDK workflow changes.
- Use `responses` for unit tests; avoid real network calls outside the integration and E2E layers.
- Prefer explicit happy-path and failure-path coverage for each public helper.

# Markers
pytest -m unit                           # Only unit tests
pytest -m "unit and not slow"           # Unit tests, exclude slow
pytest -m integration                    # Only integration tests
pytest -m auth                          # Only auth tests

# Performance
pytest --durations=10                    # Show 10 slowest tests
pytest --maxfail=3                       # Stop after 3 failures

# Specific tests
pytest tests/unit/test_client.py         # Specific file
pytest tests/unit/test_client.py::TestM8tesClient::test_init  # Specific test
pytest -k "test_agent"                   # Tests matching pattern
```

## Extending the Test Suite

As the SDK grows, you can easily add:

1. **More test categories**: Add new markers and test directories
2. **API integration tests**: Test against real API endpoints (staging)
3. **Performance tests**: Measure SDK performance characteristics
4. **End-to-end tests**: Test complete user workflows
5. **Mock service**: Create local mock server for complex integration tests

## Best Practices

1. **Test behavior, not implementation**: Focus on what the SDK should do
2. **Use descriptive test names**: `test_create_agent_with_invalid_tools_raises_validation_error`
3. **One assertion per test**: Keep tests focused and easy to debug
4. **Mock external dependencies**: Keep unit tests isolated and fast
5. **Test error conditions**: Don't just test the happy path
6. **Use factories**: Consistent, maintainable test data
7. **Clean up after tests**: Use fixtures that handle setup/teardown

This test suite provides a solid foundation for developing and maintaining the m8tes Python SDK with confidence!
