"""Integration tests for SDK instance streaming."""

import json
from unittest.mock import Mock, patch

import pytest

from m8tes import M8tes
from m8tes.instance import AgentInstance
from m8tes.streaming import DoneEvent, TextDeltaEvent, ToolCallStartEvent


class TestInstanceStreaming:
    """Test SDK instance streaming functionality."""

    @pytest.fixture
    def client(self):
        """Create M8tes client."""
        return M8tes(api_key="test-key", base_url="http://test.local")

    @pytest.fixture
    def mock_instance_data(self):
        """Mock instance data."""
        return {
            "id": 1,
            "name": "Test Instance",
            "cloudflare_instance_id": "test-123",
            "execution_mode": "claude_sdk",
            "user_id": 1,
            "agent_type": "marketing",
            "instructions": "Test instructions",
            "tools": ["run_gaql_query"],
            "tool_configs": {},
            "status": "active",
            "is_active": True,
            "run_count": 0,
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-01T00:00:00",
        }

    def create_sse_response(self, events):
        """Create a mock SSE response."""
        lines = []
        for event in events:
            lines.append(f"data: {json.dumps(event)}\n")
        return "\n".join(lines).encode()

    @patch("m8tes.instance.requests.post")
    def test_execute_task_with_streaming(self, mock_post, client, mock_instance_data):
        """Test execute_task with streaming enabled."""
        # Create instance
        instance = AgentInstance(client.instances, mock_instance_data)

        # Mock SSE response
        sse_events = [
            {"type": "text-start", "id": "0"},
            {"type": "text-delta", "delta": "Hello", "id": "0"},
            {"type": "text-delta", "delta": " world", "id": "0"},
            {"type": "text-end", "id": "0"},
            {"type": "done"},
        ]

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/event-stream"}
        mock_response.raise_for_status = Mock()
        mock_response.iter_lines = Mock(return_value=[f"data: {json.dumps(e)}" for e in sse_events])
        mock_post.return_value = mock_response

        # Execute task with streaming
        events = list(instance.execute_task("Say hello", stream=True, format="events"))

        # Verify streaming was requested
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["task"] == "Say hello"
        assert call_kwargs["json"]["stream"] is True
        assert call_kwargs["stream"] is True

        # Verify events
        assert len(events) >= 3
        text_deltas = [e for e in events if isinstance(e, TextDeltaEvent)]
        assert len(text_deltas) == 2
        assert text_deltas[0].delta == "Hello"
        assert text_deltas[1].delta == " world"

        # Verify done event
        done_events = [e for e in events if isinstance(e, DoneEvent)]
        assert len(done_events) == 1

    @patch("m8tes.instance.requests.post")
    def test_execute_task_text_format(self, mock_post, client, mock_instance_data):
        """Test execute_task with text format."""
        instance = AgentInstance(client.instances, mock_instance_data)

        sse_events = [
            {"type": "text-delta", "delta": "Hello", "id": "0"},
            {"type": "text-delta", "delta": " world", "id": "0"},
            {"type": "done"},
        ]

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/event-stream"}
        mock_response.raise_for_status = Mock()
        mock_response.iter_lines = Mock(return_value=[f"data: {json.dumps(e)}" for e in sse_events])
        mock_post.return_value = mock_response

        # Execute with text format
        text_chunks = list(instance.execute_task("Say hello", stream=True, format="text"))

        # Should only yield text strings
        assert all(isinstance(chunk, str) for chunk in text_chunks)
        assert "".join(text_chunks) == "Hello world"

    @patch("m8tes.instance.requests.post")
    def test_execute_task_with_tool_calls(self, mock_post, client, mock_instance_data):
        """Test execute_task with tool call events."""
        instance = AgentInstance(client.instances, mock_instance_data)

        sse_events = [
            {"type": "text-delta", "delta": "Let me check", "id": "0"},
            {"type": "tool-call-start", "toolName": "run_gaql_query", "toolCallId": "tool-123"},
            {"type": "tool-call-delta", "delta": '{"query":', "toolCallId": "tool-123"},
            {"type": "tool-call-delta", "delta": '"SELECT ..."}', "toolCallId": "tool-123"},
            {"type": "text-delta", "delta": "Here are the results", "id": "1"},
            {"type": "done"},
        ]

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/event-stream"}
        mock_response.raise_for_status = Mock()
        mock_response.iter_lines = Mock(return_value=[f"data: {json.dumps(e)}" for e in sse_events])
        mock_post.return_value = mock_response

        events = list(instance.execute_task("Run query", stream=True, format="events"))

        # Verify tool call events
        tool_starts = [e for e in events if isinstance(e, ToolCallStartEvent)]
        assert len(tool_starts) == 1
        assert tool_starts[0].tool_name == "run_gaql_query"
        assert tool_starts[0].tool_call_id == "tool-123"

    @patch("m8tes.instance.requests.post")
    def test_execute_task_without_streaming(self, mock_post, client, mock_instance_data):
        """Test execute_task with streaming disabled."""
        instance = AgentInstance(client.instances, mock_instance_data)

        # Mock non-streaming JSON response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.raise_for_status = Mock()
        mock_response.json = Mock(
            return_value={
                "execution_id": 1,
                "response": "Hello world",
                "success": True,
                "duration_ms": 100,
                "created_at": "2025-01-01T00:00:00",
            }
        )
        mock_post.return_value = mock_response

        # Execute without streaming
        events = list(instance.execute_task("Say hello", stream=False, format="events"))

        # Verify non-streaming was requested
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["stream"] is False
        assert call_kwargs["stream"] is False

        # Should get TextDelta + Done events
        assert len(events) == 2
        assert isinstance(events[0], TextDeltaEvent)
        assert events[0].delta == "Hello world"
        assert isinstance(events[1], DoneEvent)

    @patch("m8tes.instance.requests.post")
    def test_execute_task_handles_errors(self, mock_post, client, mock_instance_data):
        """Test execute_task handles streaming errors correctly."""
        instance = AgentInstance(client.instances, mock_instance_data)

        # Mock 401 error
        import requests

        mock_response = Mock()
        mock_response.status_code = 401

        # Create proper HTTPError
        http_error = requests.HTTPError("401 Unauthorized")
        http_error.response = mock_response

        mock_response.raise_for_status = Mock(side_effect=http_error)
        mock_post.return_value = mock_response

        # Should raise AuthenticationError
        from m8tes.exceptions import AuthenticationError

        with pytest.raises(AuthenticationError):
            list(instance.execute_task("Say hello"))

    @patch("m8tes.instance.requests.post")
    def test_execute_task_json_format(self, mock_post, client, mock_instance_data):
        """Test execute_task with JSON format."""
        instance = AgentInstance(client.instances, mock_instance_data)

        sse_events = [
            {"type": "text-delta", "delta": "Hello", "id": "0"},
            {"type": "done"},
        ]

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/event-stream"}
        mock_response.raise_for_status = Mock()
        mock_response.iter_lines = Mock(return_value=[f"data: {json.dumps(e)}" for e in sse_events])
        mock_post.return_value = mock_response

        # Execute with JSON format
        json_events = list(instance.execute_task("Say hello", stream=True, format="json"))

        # Should yield raw dictionaries
        assert all(isinstance(event, dict) for event in json_events)
        assert json_events[0]["type"] == "text-delta"
        assert json_events[0]["delta"] == "Hello"

    @patch("m8tes.instance.requests.post")
    def test_session_created_event_filtered(self, mock_post, client, mock_instance_data):
        """Test that session.created events are filtered out (not yielded to consumers)."""
        instance = AgentInstance(client.instances, mock_instance_data)

        # Mock SSE response with session.created event (nested structure)
        # Note: session_id from session.created should NOT be captured (Claude's internal ID)
        sse_events = [
            {"event": {"type": "session.created"}, "session": {"id": "claude-internal-id"}},
            {"type": "text-delta", "delta": "Hello", "id": "0"},
            {"type": "done"},
        ]

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/event-stream"}
        mock_response.raise_for_status = Mock()
        mock_response.iter_lines = Mock(return_value=[f"data: {json.dumps(e)}" for e in sse_events])
        mock_post.return_value = mock_response

        # Execute task - session.created should NOT be yielded
        events = list(instance.execute_task("Say hello", stream=True, format="events"))

        # Verify session.created event was not yielded (filtered out)
        event_types = [e.type for e in events if hasattr(e, "type")]
        assert "session.created" not in event_types

        # Verify other events were still processed
        text_deltas = [e for e in events if isinstance(e, TextDeltaEvent)]
        assert len(text_deltas) == 1
        assert text_deltas[0].delta == "Hello"
