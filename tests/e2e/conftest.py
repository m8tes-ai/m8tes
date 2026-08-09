"""
E2E test configuration for the CLI subprocess tests.

Provides the backend health-check fixture for tests that drive the real
`m8tes` CLI against a live FastAPI backend. The legacy SDK-object e2e suite
(instances/chat sessions) was deleted with the legacy v1 SDK — live SDK
coverage lives in tests/integration/test_v2_integration.py (runtime marks).

Requirements:
    1. FastAPI backend running at http://localhost:8000 (or E2E_BACKEND_URL)
"""

import os
import time

import pytest
import requests


def get_backend_url() -> str:
    """Get backend URL for E2E tests."""
    return os.getenv("E2E_BACKEND_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def backend_server():
    """
    Verify FastAPI backend server is running and healthy.

    The backend should be started manually before running E2E tests:
        cd fastapi && uv run uvicorn main:app --reload --port 8000
    """
    backend_url = get_backend_url()
    health_url = f"{backend_url}/health"

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
