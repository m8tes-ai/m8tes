# E2E Testing Guide

End-to-end tests for the m8tes.ai SDK. These tests verify the complete stack:

```
Python SDK → Flask Backend → Cloudflare Worker → Agent Execution → Tools
```

## 🎯 Hybrid Testing Strategy

**Default: Mocked External APIs**
- ✅ Fast (30 seconds)
- ✅ Free (no API costs)
- ✅ Reliable (no external dependencies)
- ✅ Tests full internal stack

**Optional: Real External APIs**
- ⚠️ Slow (5-10 minutes)
- 💰 Costs money (OpenAI, Google Ads)
- ⚠️ Requires test accounts
- ✅ Validates real integrations

## Prerequisites

### 1. Start Backend Server

```bash
cd ../../../backend
docker compose up -d  # Start PostgreSQL + Redis
flask run             # Start Flask server on port 5000
```

Verify: `curl http://localhost:5000/health` should return `200 OK`

### 2. Start Agent Worker

```bash
cd ../../../cloudflare/m8tes-agent
npm run dev  # Start worker on port 8787
```

Verify: `curl http://localhost:8787/health` should return `200 OK`

### 3. Install SDK Dev Dependencies

```bash
cd ../../sdk/py
pip install -e ".[dev]"
```

## Running E2E Tests

### Default: Mocked External APIs

```bash
# Run all E2E tests (excludes smoke tests)
make test-e2e

# Or with pytest directly
pytest tests/e2e/ -v -m "e2e and not smoke"
```

**What's tested:**
- ✅ User registration & authentication
- ✅ Agent instance creation
- ✅ Task execution through worker
- ✅ Chat mode conversations
- ✅ Streaming events
- ✅ Tool execution (with mocked responses)
- ✅ Error handling

**What's mocked:**
- OpenAI API responses
- Google Ads API responses
- Meta Ads API responses

### Smoke Tests: Real External APIs

**⚠️ WARNING: This costs real money! Use sparingly.**

```bash
# Set up environment
export E2E_USE_REAL_APIS=true
export OPENAI_API_KEY=sk-your-real-key
export GOOGLE_ADS_DEVELOPER_TOKEN=your-dev-token
export GOOGLE_ADS_TEST_CUSTOMER_ID=123-456-7890

# Run smoke tests
make test-smoke

# Or with pytest directly
E2E_USE_REAL_APIS=true pytest tests/e2e/ -v -m smoke
```

**Requirements:**
- ✅ Valid OpenAI API key (will charge your account)
- ✅ Google Ads test account (sandbox or test MCC)
- ✅ Meta Ads test account (optional)

**Expected costs:**
- OpenAI: ~$0.10-0.50 per test run
- Google Ads: Free (test account)
- Meta Ads: Free (test account)

## Configuration

### Environment Variables

**E2E Test Configuration:**

```bash
# Backend URL (default: http://localhost:5000)
E2E_BACKEND_URL=http://localhost:5000

# Worker URL (default: http://localhost:8787)
E2E_WORKER_URL=http://localhost:8787

# Use real APIs instead of mocks (default: false)
E2E_USE_REAL_APIS=false
```

**Real API Credentials (for smoke tests):**

```bash
# OpenAI
OPENAI_API_KEY=sk-your-real-key

# Google Ads
GOOGLE_ADS_DEVELOPER_TOKEN=your-dev-token
GOOGLE_ADS_TEST_CUSTOMER_ID=123-456-7890
GOOGLE_ADS_CLIENT_ID=your-client-id
GOOGLE_ADS_CLIENT_SECRET=your-client-secret

# Meta Ads (optional)
META_APP_ID=your-app-id
META_APP_SECRET=your-app-secret
META_TEST_ACCESS_TOKEN=your-test-token
```

### Configuration Files

**`.env.test` (default - mocked APIs):**

```bash
# Copy this for local development
E2E_USE_REAL_APIS=false
E2E_BACKEND_URL=http://localhost:5000
E2E_WORKER_URL=http://localhost:8787
```

**`.env.smoke` (real APIs):**

```bash
# Copy this and add real credentials
E2E_USE_REAL_APIS=true
OPENAI_API_KEY=sk-your-key-here
GOOGLE_ADS_DEVELOPER_TOKEN=your-token-here
# ... other credentials
```

## Test Structure

```
tests/e2e/
├── conftest.py                    # E2E fixtures & configuration
├── fixtures/
│   ├── openai_responses.py        # Mocked OpenAI responses
│   ├── google_ads_responses.py    # Mocked Google Ads responses
│   └── meta_ads_responses.py      # Mocked Meta Ads responses
├── test_complete_journey.py       # Full user journey tests
├── test_agent_execution.py        # Agent execution tests
├── test_cli.py                    # CLI E2E tests
└── README.md                      # This file
```

## Available Fixtures

### Service Fixtures

- `backend_server` - Verifies backend is running
- `agent_worker` - Verifies worker is running
- `test_user` - Creates test user with credentials
- `authenticated_sdk_client` - SDK client ready to use

### Mocking Fixtures

- `openai_mocker` - Mocks OpenAI API (or passthrough if `USE_REAL_APIS=true`)
- `google_ads_mocker` - Mocks Google Ads API (or passthrough)
- `meta_ads_mocker` - Mocks Meta Ads API (or passthrough)

### Utility Fixtures

- `skip_if_no_real_apis` - Skip test if not using real APIs
- `wait_for_run_completion()` - Helper to wait for async runs
- `capture_streaming_events()` - Helper to collect stream events

## Writing E2E Tests

### Basic Test Template

```python
import pytest

@pytest.mark.e2e
def test_my_feature(
    authenticated_sdk_client,
    backend_server,
    agent_worker,
    openai_mocker,
    google_ads_mocker,
):
    """Test description."""
    # Create instance
    instance = authenticated_sdk_client.instances.create(
        name="Test Agent",
        tools=["run_gaql_query"],
        instructions="Test instructions",
    )

    # Execute task
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
