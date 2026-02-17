"""Fixtures for V2 SDK integration tests against a real FastAPI backend."""

import os
import time
import uuid

import pytest
import requests

from m8tes import M8tes


def get_backend_url() -> str:
    return os.getenv("E2E_BACKEND_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def backend_url():
    """Verify backend is running and return its URL."""
    url = get_backend_url()
    for attempt in range(30):
        try:
            if requests.get(f"{url}/health", timeout=2).status_code == 200:
                return url
        except requests.exceptions.RequestException:
            if attempt < 29:
                time.sleep(1)
    pytest.skip(
        f"Backend not available at {url}. "
        "Start with: cd fastapi && uv run uvicorn main:app --reload --port 8000"
    )


@pytest.fixture(scope="session")
def v2_client(backend_url):
    """Create V2 SDK client authenticated against real backend.

    Registers a test user, logs in, and returns a configured M8tes client.
    """
    email = f"sdk-integ-{uuid.uuid4().hex[:8]}@test.m8tes.ai"
    password = "TestPassword123!"

    # Register
    resp = requests.post(
        f"{backend_url}/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "SDK Integration Test"},
    )
    assert resp.status_code == 201, f"Registration failed: {resp.text}"
    token = resp.json()["api_key"]

    client = M8tes(api_key=token, base_url=f"{backend_url}/api/v2")
    yield client
    client.close()
