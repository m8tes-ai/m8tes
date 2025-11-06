"""Test data factories for m8tes SDK."""

from datetime import datetime
from typing import Any
from unittest.mock import Mock


class SDKDataFactory:
    """Factory for creating SDK test data."""

    @staticmethod
    def create_agent_data(
        agent_id: str = "agent_123",
        name: str = "Test Agent",
        tools: list[str] | None = None,
        instructions: str = "Test instructions",
    ) -> dict[str, Any]:
        """Create mock agent data."""
        if tools is None:
            tools = ["google_ads_search", "google_ads_negatives"]

        return {
            "id": agent_id,
            "name": name,
            "tools": tools,
            "instructions": instructions,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

    @staticmethod
    def create_deployment_data(
        deployment_id: str = "deploy_123",
        agent_id: str = "agent_123",
        name: str = "Test Deployment",
        schedule: str | None = "daily",
        webhook_url: str | None = None,
        status: str = "active",
    ) -> dict[str, Any]:
        """Create mock deployment data."""
        return {
            "id": deployment_id,
            "agent_id": agent_id,
            "name": name,
            "schedule": schedule,
            "webhook_url": webhook_url,
            "status": status,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

    @staticmethod
    def create_run_event(
        event_type: str = "start",
        content: str | None = None,
        tool: str | None = None,
        action: str | None = None,
        agent_id: str = "agent_123",
    ) -> dict[str, Any]:
        """Create mock run event."""
        event = {
            "type": event_type,
            "agent_id": agent_id,
            "timestamp": datetime.now().isoformat(),
        }

        if content is not None:
            event["content"] = content
        if tool is not None:
            event["tool"] = tool
        if action is not None:
            event["action"] = action

        return event

    @staticmethod
    def create_api_response(
        data: Any = None,
        status: str = "success",
        message: str | None = None,
    ) -> dict[str, Any]:
        """Create mock API response."""
        response = {
            "status": status,
            "timestamp": datetime.now().isoformat(),
        }

        if data is not None:
            response["data"] = data
        if message is not None:
            response["message"] = message

        return response

    @staticmethod
    def create_error_response(
        error_code: str = "INVALID_REQUEST",
        message: str = "Invalid request",
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create mock error response."""
        response = {
            "status": "error",
            "error": {
                "code": error_code,
                "message": message,
            },
            "timestamp": datetime.now().isoformat(),
        }

        if details:
            response["error"]["details"] = details

        return response

    @staticmethod
    def create_google_auth_response(
        account_email: str = "test@example.com",
        status: str = "connected",
    ) -> dict[str, Any]:
        """Create mock Google authentication response."""
        return {
            "status": status,
            "account": account_email,
            "provider": "google",
            "connected_at": datetime.now().isoformat(),
        }

    @staticmethod
    def create_streaming_events(count: int = 5) -> list[dict[str, Any]]:
        """Create a sequence of mock streaming events."""
        events = [
            SDKDataFactory.create_run_event("start"),
            SDKDataFactory.create_run_event("thought", content="Analyzing account..."),
            SDKDataFactory.create_run_event(
                "action", tool="google_ads_search", action="get_campaigns"
            ),
            SDKDataFactory.create_run_event("result", content="Found 3 campaigns to optimize"),
            SDKDataFactory.create_run_event("complete", content="Optimization complete"),
        ]

        return events[:count]


class HTTPResponseFactory:
    """Factory for creating HTTP responses for testing."""

    @staticmethod
    def success_response(data: Any = None, status_code: int = 200):
        """Create a successful HTTP response mock."""
        response = Mock()
        response.status_code = status_code
        response.ok = True
        response.json.return_value = SDKDataFactory.create_api_response(data=data)
        response.text = str(response.json())
        return response

    @staticmethod
    def error_response(
        status_code: int = 400,
        error_code: str = "BAD_REQUEST",
        message: str = "Bad request",
    ):
        """Create an error HTTP response mock."""
        response = Mock()
        response.status_code = status_code
        response.ok = False
        response.json.return_value = SDKDataFactory.create_error_response(
            error_code=error_code, message=message
        )
        response.text = str(response.json())
        return response

    @staticmethod
    def streaming_response(events: list[dict[str, Any]]):
        """Create a streaming HTTP response mock."""
        response = Mock()
        response.status_code = 200
        response.ok = True

        # Mock the iter_lines method to return events as SSE format
        def iter_lines():
            for event in events:
                yield f"data: {event}".encode()

        response.iter_lines = iter_lines
        return response
