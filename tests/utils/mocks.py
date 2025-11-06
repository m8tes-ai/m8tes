"""Mock utilities for m8tes SDK tests."""

import json
from typing import Any
from unittest.mock import Mock, patch

import responses


class MockHTTPClient:
    """Mock HTTP client for testing SDK requests."""

    def __init__(self):
        self.requests = []
        self.responses = {}

    def add_response(
        self,
        method: str,
        url: str,
        response_data: Any = None,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ):
        """Add a mock response for a specific request."""
        key = f"{method.upper()} {url}"
        self.responses[key] = {
            "data": response_data,
            "status_code": status_code,
            "headers": headers or {},
        }

    def get_response(self, method: str, url: str):
        """Get the mock response for a request."""
        key = f"{method.upper()} {url}"
        return self.responses.get(key)

    def track_request(self, method: str, url: str, **kwargs):
        """Track a request for later verification."""
        self.requests.append(
            {
                "method": method.upper(),
                "url": url,
                "kwargs": kwargs,
            }
        )


def create_mock_response(
    status_code: int = 200,
    json_data: dict[str, Any] | None = None,
    text: str | None = None,
    headers: dict[str, str] | None = None,
):
    """Create a mock HTTP response."""
    response = Mock()
    response.status_code = status_code
    response.ok = status_code < 400

    if json_data is not None:
        response.json.return_value = json_data
        response.text = json.dumps(json_data)
    elif text is not None:
        response.text = text
        response.json.side_effect = ValueError("No JSON")
    else:
        response.text = ""
        response.json.side_effect = ValueError("No JSON")

    response.headers = headers or {}
    return response


def create_streaming_mock(events: list[dict[str, Any]]):
    """Create a mock for streaming responses."""

    def iter_lines():
        for event in events:
            yield f"data: {json.dumps(event)}".encode()

    response = Mock()
    response.status_code = 200
    response.ok = True
    response.iter_lines = iter_lines
    return response


class ResponsesMock:
    """Wrapper around responses library for easier testing."""

    def __init__(self):
        self.mock = responses.RequestsMock()

    def __enter__(self):
        self.mock.__enter__()
        return self

    def __exit__(self, *args):
        return self.mock.__exit__(*args)

    def add_agent_creation(
        self,
        base_url: str,
        agent_data: dict[str, Any],
        status_code: int = 201,
    ):
        """Add mock for agent creation endpoint."""
        self.mock.add(
            responses.POST,
            f"{base_url}/agents",
            json={"status": "success", "data": agent_data},
            status=status_code,
        )

    def add_agent_run(
        self,
        base_url: str,
        agent_id: str,
        events: list[dict[str, Any]],
        status_code: int = 200,
    ):
        """Add mock for agent run endpoint (streaming)."""
        # Mock streaming response
        body = "\n".join([f"data: {json.dumps(event)}" for event in events])
        self.mock.add(
            responses.POST,
            f"{base_url}/agents/{agent_id}/run",
            body=body,
            status=status_code,
            headers={"Content-Type": "text/event-stream"},
        )

    def add_deployment_creation(
        self,
        base_url: str,
        deployment_data: dict[str, Any],
        status_code: int = 201,
    ):
        """Add mock for deployment creation endpoint."""
        self.mock.add(
            responses.POST,
            f"{base_url}/deployments",
            json={"status": "success", "data": deployment_data},
            status=status_code,
        )

    def add_google_auth_start(
        self,
        base_url: str,
        auth_url: str = "https://accounts.google.com/oauth/authorize?...",
        status_code: int = 200,
    ):
        """Add mock for Google OAuth start endpoint."""
        self.mock.add(
            responses.POST,
            f"{base_url}/integrations/google/authorize",
            json={"status": "success", "data": {"auth_url": auth_url}},
            status=status_code,
        )

    def add_google_auth_complete(
        self,
        base_url: str,
        account_email: str = "test@example.com",
        status_code: int = 200,
    ):
        """Add mock for Google OAuth completion endpoint."""
        self.mock.add(
            responses.POST,
            f"{base_url}/integrations/google/exchange",
            json={
                "status": "success",
                "data": {
                    "status": "connected",
                    "account": account_email,
                },
            },
            status=status_code,
        )

    def add_error_response(
        self,
        method: str,
        url: str,
        error_code: str = "INTERNAL_ERROR",
        message: str = "Internal server error",
        status_code: int = 500,
    ):
        """Add mock error response."""
        method_func = getattr(self.mock, method.lower())
        method_func(
            url,
            json={
                "status": "error",
                "error": {
                    "code": error_code,
                    "message": message,
                },
            },
            status=status_code,
        )


def mock_environment_variables(**env_vars):
    """Context manager to mock environment variables."""
    return patch.dict("os.environ", env_vars)
