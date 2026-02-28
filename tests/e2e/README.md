# SDK E2E Tests

These tests are the expensive, live end-to-end lane for the Python SDK.

Current stack:

```text
Python SDK -> FastAPI backend -> agent runtime -> model/tool providers
```

Important scope note:

- `tests/integration/test_v2_integration.py` is the main V2 SDK parity suite.
- `tests/e2e/` is mostly legacy `instances` / CLI coverage and full runtime journeys.
- E2E here uses real runtime behavior and real provider calls. It is not the fast default test lane.

## Requirements

1. FastAPI backend running locally.
2. Database and any required backend services available.
3. Real provider/runtime credentials configured for the backend environment.

Start the backend from the repo root:

```bash
cd /Users/elmar/Environments/agent/fastapi
uv run uvicorn main:app --reload --port 8000
```

The default backend URL is `http://localhost:8000`. Override it with `E2E_BACKEND_URL` if needed.

## Commands

Run from `sdk/py/`.

```bash
# All E2E tests except smoke-marked ones
make test-e2e

# Smallest live-confidence subset
make test-smoke
```

Direct pytest equivalents:

```bash
uv run pytest tests/e2e/ -v -m "e2e and not smoke"
uv run pytest tests/e2e/ -v -m smoke
```

## Cost / Reliability

- `@pytest.mark.e2e`
  Uses the real runtime path and can fail because of provider credentials, external services, or sandbox/runtime issues.
- `@pytest.mark.smoke`
  Smallest live subset. Use before release or when validating infra/provider changes.

The compatibility fixtures in `conftest.py` are no-op placeholders now; they no longer provide mocked OpenAI/Google Ads/Meta behavior.

## Directory Layout

```text
tests/e2e/
├── conftest.py
├── fixtures/
├── test_agent_execution.py
├── test_cli.py
├── test_complete_journey.py
└── README.md
```

## When To Add Tests Here

- Add a test here only when the change must exercise the full runtime or CLI stack.
- If you are changing the V2 SDK request/response contract, prefer unit tests plus `tests/integration/test_v2_integration.py`.
- Keep smoke coverage narrow and deterministic enough to be useful before releases.
    run = instance.execute_task("Test message")

    # Verify results
    assert run.id is not None

    # Clean up
    instance.delete()
```

### Smoke Test Template

```python
@pytest.mark.smoke
@pytest.mark.e2e
def test_real_api_integration(
    authenticated_sdk_client,
    backend_server,
    agent_worker,
    skip_if_no_real_apis,  # Auto-skip if not using real APIs
):
    """SMOKE TEST: Uses real OpenAI API."""
    # Test with real API
    instance = authenticated_sdk_client.instances.create(
        name="Real API Test",
        tools=["run_gaql_query"],
        instructions="Use real AI",
    )

    run = instance.execute_task("Real query")

    # Verify real responses
    usage = run.get_usage()
    assert usage["total_tokens"] > 0

    # Clean up
    instance.delete()
```

## Troubleshooting

### Backend not available

```
pytest.skip: Backend server not available at http://localhost:5000
```

**Solution:** Start the backend server:
```bash
cd ../../../backend && flask run
```

### Worker not available

```
pytest.skip: Agent worker not available at http://localhost:8787
```

**Solution:** Start the worker:
```bash
cd ../../../cloudflare/m8tes-agent && npm run dev
```

### Database connection errors

**Solution:** Ensure PostgreSQL is running:
```bash
cd ../../../backend && docker compose up -d
```

### Import errors for fixtures

**Solution:** Ensure fixtures are properly defined in `fixtures/__init__.py` or imported in `conftest.py`

### Real API credentials not working

**Solution:** Verify environment variables are set:
```bash
echo $OPENAI_API_KEY
echo $GOOGLE_ADS_DEVELOPER_TOKEN
```

## CI/CD Integration

### Automated Testing Strategy

**Pull Requests:**
- ✅ Unit tests run on all PRs (all Python versions)
- ✅ Linting, formatting, type checking
- ✅ Code coverage must be ≥ 80%
- ❌ E2E tests NOT run (to avoid service startup overhead)

**Main Branch:**
- ✅ All PR checks
- ✅ Integration tests (with backend)
- ✅ E2E tests with mocked external APIs
- ✅ Build and package distribution

**Scheduled (Nightly):**
- ✅ Smoke tests with REAL external APIs
- 💰 Costs ~$0.10-0.50 per run
- 📧 Creates GitHub issue if tests fail

**Pre-Release (Tags):**
- ✅ All main branch checks
- ✅ Smoke tests with real APIs
- ✅ Full integration verification

### GitHub Actions Workflows

The SDK includes three CI/CD workflows:

**1. `.github/workflows/ci.yml` - Main CI Pipeline**
- Runs on: Every PR + push to main
- Jobs: test (unit), security, integration, e2e, build, publish
- E2E job only runs on main branch

**2. `.github/workflows/smoke-tests.yml` - Real API Tests**
- Runs on: Nightly schedule (2 AM UTC), manual trigger, release tags
- Uses real OpenAI and Google Ads APIs
- Creates issues on failure
- Tracks API costs

**3. Monorepo CI** (optional, at root level)
- Detects changed components
- Runs component-specific tests
- Coordinates cross-component E2E tests

### Required Secrets

Configure these in GitHub repository settings:

**For Integration Tests:**
- `TEST_API_KEY` - Test user API key
- `TEST_BASE_URL` - Test backend URL

**For Smoke Tests:**
- `OPENAI_API_KEY` - Real OpenAI API key
- `GOOGLE_ADS_DEVELOPER_TOKEN` - Google Ads dev token
- `GOOGLE_ADS_CLIENT_ID` - OAuth client ID
- `GOOGLE_ADS_CLIENT_SECRET` - OAuth client secret
- `GOOGLE_ADS_REFRESH_TOKEN` - OAuth refresh token
- `GOOGLE_ADS_TEST_CUSTOMER_ID` - Test customer ID

### Local CI Simulation

Run exactly what CI runs locally:

```bash
# Unit tests (what runs on PRs)
make ci-test

# E2E tests (what runs on main)
# First, start services
make ci-e2e

# Smoke tests (what runs nightly)
make test-smoke
```

### CI Badge

Add this to README.md:

```markdown
![CI Status](https://github.com/your-org/your-repo/workflows/CI%2FCD%20Pipeline/badge.svg)
![Smoke Tests](https://github.com/your-org/your-repo/workflows/Smoke%20Tests/badge.svg)
```

## Best Practices

1. **Always clean up** - Delete created instances/runs after tests
2. **Use fixtures** - Don't duplicate setup code
3. **Mock by default** - Only use real APIs for critical smoke tests
4. **Test isolation** - Each test should be independent
5. **Clear assertions** - Make test failures obvious
6. **Fast feedback** - Keep mocked tests under 1 minute total

## Cost Management

**Mocked E2E tests:** $0 (free)
**Smoke tests:** ~$0.10-0.50 per run

**To minimize costs:**
- Run smoke tests only before releases
- Use test accounts with spending limits
- Run mocked tests in CI/CD
- Schedule smoke tests (nightly, not per-commit)

## Questions?

See the main project documentation: `/CLAUDE.md`
