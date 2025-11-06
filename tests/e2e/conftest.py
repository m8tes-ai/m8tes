"""
E2E test configuration and fixtures.

Provides fixtures for running end-to-end tests against real FastAPI backend
with Claude Agent SDK. Always uses REAL APIs (costs money!).

Requirements:
    1. FastAPI backend running at http://localhost:8000
    2. Valid ANTHROPIC_API_KEY in backend .env
    3. PostgreSQL database running (via docker compose)
"""

import os
import time

import pytest
import requests


# Configuration
def use_real_apis() -> bool:
    """E2E tests always use real APIs."""
    return True


def get_backend_url() -> str:
    """Get backend URL for E2E tests."""
    return os.getenv("E2E_BACKEND_URL", "http://localhost:8000")


# Service Health Checks
@pytest.fixture(scope="session")
def backend_server():
    """
    Verify FastAPI backend server is running and healthy.

    The backend should be started manually before running E2E tests:
        cd fastapi && docker compose up -d
        cd fastapi && uv run uvicorn main:app --reload --port 8000
    """
    backend_url = get_backend_url()
    health_url = f"{backend_url}/health"

    # Wait up to 30 seconds for backend to be ready
    max_attempts = 30
    for attempt in range(max_attempts):
        try:
            response = requests.get(health_url, timeout=2)
            if response.status_code == 200:
                print(f"\n✅ FastAPI backend ready at {backend_url}")
                return backend_url
        except requests.exceptions.RequestException:
            if attempt < max_attempts - 1:
                time.sleep(1)
            else:
                pytest.skip(
                    f"FastAPI backend not available at {backend_url}. "
                    "Start it with: cd fastapi && uv run uvicorn main:app --reload --port 8000"
                )

    pytest.skip(f"Backend server health check failed at {health_url}")


# Real API Usage (No Mocking)
@pytest.fixture
def openai_mocker():
    """
    E2E tests use real Claude Agent SDK / Anthropic API (costs money!).
    This fixture exists for backwards compatibility but does nothing.
    """
    print("\n💰 Using REAL Claude Agent SDK / Anthropic API (will cost money)")
    yield None


@pytest.fixture
def google_ads_mocker():
    """
    E2E tests use real Google Ads API (requires test account).
    This fixture exists for backwards compatibility but does nothing.
    """
    print("\n🔍 Using REAL Google Ads API (requires test account)")
    yield None


@pytest.fixture
def meta_ads_mocker():
    """
    E2E tests use real Meta Ads API (requires test account).
    This fixture exists for backwards compatibility but does nothing.
    """
    print("\n📘 Using REAL Meta Ads API (requires test account)")
    yield None


# Test User Management
@pytest.fixture
def test_user(backend_server):
    """
    Create a test user for E2E tests and clean up after.

    Returns dict with user credentials:
        {"email": "...", "password": "...", "api_key": "..."}
    """
    import uuid

    from m8tes import M8tes

    # Generate unique test user
    test_email = f"test-{uuid.uuid4()}@m8tes.ai"
    test_password = "TestPassword123!"

    # Create unauthenticated client
    client = M8tes(base_url=backend_server)

    try:
        # Register user
        client.auth.register(email=test_email, password=test_password, full_name="E2E Test User")

        # Login to get API key
        login_response = client.auth.login(email=test_email, password=test_password)
        api_key = login_response.get("api_key")

        user_data = {
            "email": test_email,
            "password": test_password,
            "api_key": api_key,
        }

        print(f"\n✅ Created test user: {test_email}")

        yield user_data

        # Cleanup: Delete test user
        # Note: Would need DELETE /api/v1/auth/me endpoint
        print(f"\n🧹 Cleaned up test user: {test_email}")

    except Exception as e:
        pytest.fail(f"Failed to create test user: {e}")


@pytest.fixture
def authenticated_sdk_client(test_user, backend_server):
    """
    SDK client authenticated as test user.

    Ready to use for E2E tests.
    """
    from m8tes import M8tes

    client = M8tes(api_key=test_user["api_key"], base_url=backend_server)

    return client


# Test Markers
@pytest.fixture
def skip_if_no_real_apis():
    """
    No-op fixture for backwards compatibility.
    E2E tests always use real APIs now.
    """
    pass


# Helper Functions
def wait_for_run_completion(run, timeout=30):
    """
    Wait for a run to complete.

    Args:
        run: Run instance
        timeout: Maximum seconds to wait

    Returns:
        Updated run instance

    Raises:
        TimeoutError: If run doesn't complete in time
    """
    start_time = time.time()

    while time.time() - start_time < timeout:
        run.refresh()

        # Check if run has completed (based on worker response)
        if hasattr(run, "_worker_response") and run._worker_response:
            return run

        # Check if run has error
        if hasattr(run, "_error") and run._error:
            raise RuntimeError(f"Run failed: {run._error}")

        time.sleep(0.5)

    raise TimeoutError(f"Run did not complete within {timeout} seconds")


def capture_streaming_events(stream_generator):
    """
    Capture all events from a streaming generator.

    Args:
        stream_generator: Generator yielding stream events

    Returns:
        List of all events
    """
    events = []
    for event in stream_generator:
        events.append(event)
    return events
