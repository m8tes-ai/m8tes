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

        # Verify session ID was NOT captured (session.created is Claude's event, not metadata)
        assert instance._session_id is None

        # Verify session.created event was not yielded (filtered out)
        event_types = [e.type for e in events if hasattr(e, "type")]
        assert "session.created" not in event_types

        # Verify other events were still processed
        text_deltas = [e for e in events if isinstance(e, TextDeltaEvent)]
        assert len(text_deltas) == 1
        assert text_deltas[0].delta == "Hello"

    @patch("m8tes.instance.requests.post")
    def test_session_id_captured_only_from_metadata(self, mock_post, client, mock_instance_data):
        """Session ID should ONLY be captured from metadata events, not Claude events."""
        instance = AgentInstance(client.instances, mock_instance_data)

        backend_session_id = "backend-public-uuid-123"
        claude_session_id = "claude-internal-id-456"

        # Mock SSE response with BOTH metadata event (backend) and Claude events
        sse_events = [
            # Backend metadata event with our claude_session_id
            {
                "type": "metadata",
                "session_id": backend_session_id,
                "run_id": 1,
            },
            # Flat format events (normalized by agent-runtime)
            # Note: agent-runtime normalizes to flat format, no nested "event" key
            {
                "type": "message-start",
                "message_id": "msg-1",
                "session_id": claude_session_id,  # Claude's ID - should NOT overwrite
            },
            {
                "type": "text-delta",
                "delta": "Hi there",
                "id": "msg-1",
                "session_id": claude_session_id,  # Claude's ID - should NOT overwrite
            },
            {
                "type": "message-end",
                "message_id": "msg-1",
                "session_id": claude_session_id,  # Claude's ID - should NOT overwrite
            },
        ]

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/event-stream"}
        mock_response.raise_for_status = Mock()
        mock_response.iter_lines = Mock(return_value=[f"data: {json.dumps(e)}" for e in sse_events])
        mock_post.return_value = mock_response

        # Execute and consume stream
        events = list(instance._execute_via_sdk("Hello", mode="chat"))

        # CRITICAL: Should have backend's session_id, NOT Claude's
        assert instance._session_id == backend_session_id
        assert instance._session_id != claude_session_id

        # Ensure normal events still yielded
        assert any(isinstance(e, TextDeltaEvent) for e in events)

    @patch("m8tes.instance.requests.post")
    def test_session_id_sent_on_subsequent_requests(self, mock_post, client, mock_instance_data):
        """Test that session_id is sent in subsequent chat mode requests."""
        instance = AgentInstance(client.instances, mock_instance_data)

        backend_session_id = "backend-uuid-456"

        # First request - capture session ID from metadata event
        sse_events_first = [
            {"type": "metadata", "session_id": backend_session_id, "run_id": 1},
            {"type": "text-delta", "delta": "First response", "id": "0"},
            {"type": "done"},
        ]

        mock_response_first = Mock()
        mock_response_first.status_code = 200
        mock_response_first.headers = {"content-type": "text/event-stream"}
        mock_response_first.raise_for_status = Mock()
        mock_response_first.iter_lines = Mock(
            return_value=[f"data: {json.dumps(e)}" for e in sse_events_first]
        )

        # Second request - should use captured session ID
        sse_events_second = [
            {"type": "metadata", "session_id": backend_session_id, "run_id": 1},
            {"type": "text-delta", "delta": "Second response", "id": "0"},
            {"type": "done"},
        ]

        mock_response_second = Mock()
        mock_response_second.status_code = 200
        mock_response_second.headers = {"content-type": "text/event-stream"}
        mock_response_second.raise_for_status = Mock()
        mock_response_second.iter_lines = Mock(
            return_value=[f"data: {json.dumps(e)}" for e in sse_events_second]
        )

        mock_post.side_effect = [mock_response_first, mock_response_second]

        # First request (chat mode)
        list(instance._execute_via_sdk("First message", mode="chat"))

        # Verify session ID was captured
        assert instance._session_id == backend_session_id

        # Second request (chat mode)
        list(instance._execute_via_sdk("Second message", mode="chat"))

        # Verify second request included session_id
        second_call_kwargs = mock_post.call_args_list[1][1]
        assert second_call_kwargs["json"]["session_id"] == backend_session_id

    @patch("m8tes.instance.requests.post")
    def test_two_message_chat_maintains_session(self, mock_post, client, mock_instance_data):
        """Test two-message chat flow maintains the same session (regression test for bug)."""
        instance = AgentInstance(client.instances, mock_instance_data)

        backend_claude_session_id = "ac0eb732-40ab-4374-abe9-0b6f55cde713"
        claude_internal_id = "5b61b019-0c00-4ed6-9272-a1b0f4afcd7c"

        # First message - backend creates session, Claude returns its ID
        sse_events_first = [
            # Backend sends metadata with our claude_session_id
            {
                "type": "metadata",
                "session_id": backend_claude_session_id,
                "run_id": 145,
                "mode": "chat",
            },
            # Claude sends events with its session_id (should NOT overwrite)
            {
                "event": {"type": "message_start"},
                "session_id": claude_internal_id,
            },
            {
                "event": {
                    "type": "content_block_delta",
                    "delta": {"type": "text_delta", "text": "Hello! I'm m8tes"},
                },
                "session_id": claude_internal_id,
            },
            {
                "event": {"type": "message_stop"},
                "session_id": claude_internal_id,
            },
        ]

        # Second message - should use backend's claude_session_id
        sse_events_second = [
            {
                "type": "metadata",
                "session_id": backend_claude_session_id,
                "run_id": 145,
                "mode": "chat",
            },
            {
                "event": {
                    "type": "content_block_delta",
                    "delta": {"type": "text_delta", "text": "Say hello"},
                },
                "session_id": claude_internal_id,
            },
            {
                "event": {"type": "message_stop"},
                "session_id": claude_internal_id,
            },
        ]

        mock_response_first = Mock()
        mock_response_first.status_code = 200
        mock_response_first.headers = {"content-type": "text/event-stream"}
        mock_response_first.raise_for_status = Mock()
        mock_response_first.iter_lines = Mock(
            return_value=[f"data: {json.dumps(e)}" for e in sse_events_first]
        )

        mock_response_second = Mock()
        mock_response_second.status_code = 200
        mock_response_second.headers = {"content-type": "text/event-stream"}
        mock_response_second.raise_for_status = Mock()
        mock_response_second.iter_lines = Mock(
            return_value=[f"data: {json.dumps(e)}" for e in sse_events_second]
        )

        mock_post.side_effect = [mock_response_first, mock_response_second]

        # First message
        list(instance._execute_via_sdk("Say hello", mode="chat"))

        # CRITICAL: Should have backend's UUID, NOT Claude's
        assert instance._session_id == backend_claude_session_id
        assert instance._session_id != claude_internal_id

        # Second message
        list(instance._execute_via_sdk("What was my last message?", mode="chat"))

        # CRITICAL: Second request should send backend's UUID
        second_call_kwargs = mock_post.call_args_list[1][1]
        assert second_call_kwargs["json"]["session_id"] == backend_claude_session_id
        assert second_call_kwargs["json"]["session_id"] != claude_internal_id

        # Session ID should still be backend's UUID
        assert instance._session_id == backend_claude_session_id

    @patch("m8tes.instance.requests.post")
    def test_task_mode_never_sends_session_id(self, mock_post, client, mock_instance_data):
        """Test that task mode NEVER sends session_id, even if one is captured."""
        instance = AgentInstance(client.instances, mock_instance_data)

        # Manually set session_id (as if it was captured from a chat)
        instance._session_id = "captured_session_123"

        # Mock response for task execution
        sse_events = [
            {"type": "text-delta", "delta": "Task response", "id": "0"},
            {"type": "done"},
        ]

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/event-stream"}
        mock_response.raise_for_status = Mock()
        mock_response.iter_lines = Mock(return_value=[f"data: {json.dumps(e)}" for e in sse_events])
        mock_post.return_value = mock_response

        # Execute task (mode="task" by default)
        list(instance.execute_task("Do something", stream=True))

        # Verify request was made
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]

        # CRITICAL: Verify session_id is NOT in the request body
        assert "session_id" not in call_kwargs["json"]
        assert call_kwargs["json"]["mode"] == "task"

        # Verify the session_id is still stored (not cleared)
        assert instance._session_id == "captured_session_123"
