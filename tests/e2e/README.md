# SDK E2E Tests

These tests are the expensive live end-to-end lane for the Python SDK.

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

The compatibility fixtures in `conftest.py` are no-op placeholders now. They no longer provide mocked OpenAI, Google Ads, or Meta behavior.

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

## Troubleshooting

### Backend not available

```
pytest.skip: Backend not available at http://localhost:8000
```

**Solution:** Start the backend server:
```bash
cd /Users/elmar/Environments/agent/fastapi
uv run uvicorn main:app --reload --port 8000
```

### Runtime-backed E2E fails

If an E2E test depends on the full runtime path, make sure the backend environment can reach the agent runtime and any required provider credentials.

### Database connection errors

**Solution:** Ensure PostgreSQL is running:
```bash
cd /Users/elmar/Environments/agent/fastapi
docker compose up -d
```

### Import errors for fixtures

**Solution:** Ensure fixtures are properly defined in `fixtures/__init__.py` or imported in `conftest.py`

### Provider credentials not working

**Solution:** Verify environment variables are set:
```bash
echo $ANTHROPIC_API_KEY
echo $COMPOSIO_API_KEY
```

## CI / Workflow Reality

The current repo workflows are:

- `.github/workflows/sdk-ci.yml`
  Runs SDK unit checks plus the deterministic V2 backend and SDK integration lane.
- `.github/workflows/deploy.yml`
  Handles deploy flow.
- `.github/workflows/preview-deploy.yml`
  Handles preview environments.
- `.github/workflows/sync-sdk.yml`
  Handles SDK sync automation.

Important note:

- Ordinary PR CI is deterministic and zero-token.
- This `tests/e2e/` directory is not part of the default PR gate.
- There is no dedicated nightly smoke workflow in the repo today.

## Local CI Simulation

Run the deterministic gate locally:

```bash
cd /Users/elmar/Environments/agent
make check
```

Run only the expensive live lane from `sdk/py/`:

```bash
make test-e2e
make test-smoke
```

## Best Practices

1. **Always clean up** - Delete created instances/runs after tests
2. **Use fixtures** - Don't duplicate setup code
3. **Mock by default** - Only use real APIs for critical smoke tests
4. **Test isolation** - Each test should be independent
5. **Clear assertions** - Make test failures obvious
6. **Fast feedback** - Keep mocked tests under 1 minute total

## Cost Management

**Deterministic CI:** $0
**E2E / smoke:** depends on provider and runtime usage

**To minimize costs:**
- Run smoke tests only when you explicitly need live runtime confidence
- Use test accounts with spending limits
- Keep PR CI deterministic and zero-token

## Questions?

See the main project documentation: `/CLAUDE.md`
