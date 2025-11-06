"""
Integration tests for streaming with mocked HTTP responses.

These tests verify the full pipeline: SDK → HTTP Stream → Parser → Events
using mocked HTTP SSE streams to avoid needing a live worker.
"""

from unittest.mock import Mock, patch

from m8tes.streaming import (
    DoneEvent,
    StreamAccumulator,
    TextDeltaEvent,
    ToolCallStartEvent,
    ToolResultEndEvent,
)


class MockSSEResponse:
    """Mock HTTP response that simulates Server-Sent Events stream."""

    def __init__(self, sse_lines):
        """
        Initialize mock SSE response.

        Args:
            sse_lines: List of SSE event lines to stream
        """
        self.sse_lines = sse_lines
        self.status_code = 200
        self.headers = {"content-type": "text/event-stream; charset=utf-8"}

    def raise_for_status(self):
        """Mock raise_for_status - does nothing if status is 200."""
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    def iter_lines(self, decode_unicode=True):
        """Simulate iter_lines() from requests Response."""
        yield from self.sse_lines


class TestInstanceTaskStreamingMocked:
    """Test Instance.execute_task() with mocked HTTP streams."""

    @patch("m8tes.instance.requests.post")
    def test_execute_task_basic_streaming(self, mock_post):
        """Test basic task execution with mocked SSE stream."""
        # Mock SSE stream data
        sse_lines = [
            'data: {"type":"text-start","id":"text_1"}',
            'data: {"type":"text-delta","id":"text_1","delta":"Hello "}',
            'data: {"type":"text-delta","id":"text_1","delta":"from "}',
            'data: {"type":"text-delta","id":"text_1","delta":"streaming!"}',
            'data: {"type":"text-end","id":"text_1"}',
            "data: [DONE]",
        ]

        # Setup mock - single call to SDK execute endpoint
        mock_response = MockSSEResponse(sse_lines)

        # Configure mock to return SSE response
        mock_post.return_value = mock_response

        # Mock the InstanceService and Run creation
        from m8tes.instance import AgentInstance

        mock_service = Mock()
        mock_run = Mock()
        mock_run.id = 123
        mock_service.http.client.runs.create.return_value = mock_run

        # Create instance
        instance = AgentInstance(
            instance_service=mock_service,
            data={
                "id": 1,
                "cloudflare_instance_id": "test-instance",
                "name": "Test",
                "tools": [],
            },
        )

        # Execute task and collect events
        events = []
        text_deltas = []

        for event in instance.execute_task("Test message", stream=True, format="events"):
            events.append(event)
            if isinstance(event, TextDeltaEvent):
                text_deltas.append(event.delta)

        # Verify we got all expected events
        assert len(events) > 0
        assert any(isinstance(e, TextDeltaEvent) for e in events)
        assert any(isinstance(e, DoneEvent) for e in events)

        # Verify text was accumulated correctly
        full_text = "".join(text_deltas)
        assert full_text == "Hello from streaming!"

    @patch("m8tes.instance.requests.post")
    def test_execute_task_with_tool_calls(self, mock_post):
        """Test task execution with tool calls in stream."""
        # Mock SSE stream with tool call
        sse_lines = [
            'data: {"type":"text-start","id":"text_1"}',
            'data: {"type":"text-delta","id":"text_1","delta":"Let me check... "}',
            'data: {"type":"tool-call-start","toolCallId":"call_123","toolName":"run_gaql_query"}',
            'data: {"type":"tool-call-delta","toolCallId":"call_123","delta":"{\\"query\\":\\""}',
            'data: {"type":"tool-call-delta","toolCallId":"call_123","delta":"SELECT...\\"}"}',
            'data: {"type":"tool-result-end","toolCallId":"call_123","result":{"rows":[{"campaign":"Test"}],"count":1}}',  # noqa: E501
            'data: {"type":"text-delta","id":"text_1","delta":"Found 1 campaign!"}',
            'data: {"type":"text-end","id":"text_1"}',
            "data: [DONE]",
        ]

        # Setup mock - single call to SDK execute endpoint
        mock_response = MockSSEResponse(sse_lines)

        # Configure mock to return SSE response
        mock_post.return_value = mock_response

        from m8tes.instance import AgentInstance

        mock_service = Mock()
        mock_run = Mock()
        mock_run.id = 123
        mock_service.http.client.runs.create.return_value = mock_run

        instance = AgentInstance(
            instance_service=mock_service,
            data={
                "id": 1,
                "cloudflare_instance_id": "test-instance",
                "name": "Test",
                "tools": ["run_gaql_query"],
            },
        )

        # Execute and collect events
        accumulator = StreamAccumulator()
        has_tool_call = False
        has_tool_result = False

        for event in instance.execute_task("Show campaigns", stream=True):
            accumulator.process(event)

            if isinstance(event, ToolCallStartEvent):
                has_tool_call = True
                assert event.tool_name == "run_gaql_query"

            if isinstance(event, ToolResultEndEvent):
                has_tool_result = True
                assert event.result is not None
                assert event.result["count"] == 1

        # Verify tool calls were processed
        assert has_tool_call
        assert has_tool_result

        # Verify text was accumulated
        text = accumulator.get_text()
        assert "Let me check" in text
        assert "Found 1 campaign" in text

        # Verify tool call metadata
        tool_calls = accumulator.get_tool_calls()
        assert "call_123" in tool_calls
        assert tool_calls["call_123"]["name"] == "run_gaql_query"

    @patch("m8tes.instance.requests.post")
    def test_execute_task_text_format(self, mock_post):
        """Test text-only format yields strings."""
        sse_lines = [
            'data: {"type":"text-delta","id":"text_1","delta":"Part 1 "}',
            'data: {"type":"text-delta","id":"text_1","delta":"Part 2"}',
            "data: [DONE]",
        ]

        # Setup mock - single call to SDK execute endpoint
        mock_response = MockSSEResponse(sse_lines)

        # Configure mock to return SSE response
        mock_post.return_value = mock_response

        from m8tes.instance import AgentInstance

        mock_service = Mock()
        mock_run = Mock(id=123)
        mock_service.http.client.runs.create.return_value = mock_run

        instance = AgentInstance(
            instance_service=mock_service,
            data={"id": 1, "cloudflare_instance_id": "test", "name": "Test", "tools": []},
        )

        # Execute with text format
        text_parts = []
        for text in instance.execute_task("Test", stream=True, format="text"):
            assert isinstance(text, str)
            text_parts.append(text)

        # Verify we got text chunks
        assert len(text_parts) == 2
        assert "".join(text_parts) == "Part 1 Part 2"

    @patch("m8tes.instance.requests.post")
    def test_execute_task_json_format(self, mock_post):
        """Test JSON format yields raw dictionaries."""
        sse_lines = [
            'data: {"type":"text-delta","delta":"Hello"}',
            "data: [DONE]",
        ]

        # Setup mock - single call to SDK execute endpoint
        mock_response = MockSSEResponse(sse_lines)

        # Configure mock to return SSE response
        mock_post.return_value = mock_response

        from m8tes.instance import AgentInstance

        mock_service = Mock()
        mock_run = Mock(id=123)
        mock_service.http.client.runs.create.return_value = mock_run

        instance = AgentInstance(
            instance_service=mock_service,
            data={"id": 1, "cloudflare_instance_id": "test", "name": "Test", "tools": []},
        )

        # Execute with JSON format
        json_events = []
        for event in instance.execute_task("Test", stream=True, format="json"):
            assert isinstance(event, dict)
            json_events.append(event)

        # Verify we got JSON events
        assert len(json_events) > 0
        assert any(e.get("type") == "text-delta" for e in json_events)


class TestChatSessionStreamingMocked:
    """Test ChatSession.send() with mocked HTTP streams."""

    @patch("m8tes.instance.requests.post")
    def test_chat_session_send_streaming(self, mock_post):
        """Test chat session message with streaming."""
        sse_lines = [
            'data: {"event":{"type":"session.created"},"session":{"id":"sess-123"}}',
            'data: {"type":"text-delta","delta":"Hello! "}',
            'data: {"type":"text-delta","delta":"How can I help?"}',
            "data: [DONE]",
        ]

        # Single mock for /execute endpoint (no init/clear)
        mock_response = MockSSEResponse(sse_lines)
        mock_post.return_value = mock_response

        from m8tes.chat import ChatSession
        from m8tes.instance import AgentInstance

        mock_service = Mock()
        mock_run = Mock()
        mock_run.id = 456

        instance = AgentInstance(
            instance_service=mock_service,
            data={
                "id": 1,
                "cloudflare_instance_id": "test",
                "name": "Test",
                "tools": [],
            },
        )

        chat = ChatSession(instance, mock_run)

        # Send message and collect text
        text_parts = []
        for event in chat.send("Hello", stream=True):
            if isinstance(event, TextDeltaEvent):
                text_parts.append(event.delta)

        # Verify response
        assert "".join(text_parts) == "Hello! How can I help?"


class TestDisplayIntegration:
    """Test display components with real event sequences."""

    def test_verbose_display_with_event_sequence(self):
        """Test VerboseDisplay with realistic event sequence."""
        from m8tes.cli.display import VerboseDisplay

        events = [
            TextDeltaEvent(type="text-delta", raw={}, delta="Analyzing your request... "),
            ToolCallStartEvent(
                type="tool-call-start",
                raw={},
                tool_call_id="call_1",
                tool_name="run_gaql_query",
            ),
            ToolResultEndEvent(
                type="tool-result-end",
                raw={},
                tool_call_id="call_1",
                result={
                    "rows": [
                        {"campaign_name": "Summer Sale", "clicks": 1234},
                        {"campaign_name": "Fall Promo", "clicks": 890},
                    ],
                    "count": 2,
                },
            ),
            TextDeltaEvent(type="text-delta", raw={}, delta="I found 2 campaigns for you!"),
            DoneEvent(type="done", raw={}),
        ]

        display = VerboseDisplay()
        display.start()

        # Process all events (visual output goes to terminal)
        for event in events:
            display.on_event(event)

        display.finish()

        # Verify accumulator collected data correctly
        assert (
            display.accumulator.get_text()
            == "Analyzing your request... I found 2 campaigns for you!"
        )
        tool_calls = display.accumulator.get_tool_calls()
        assert "call_1" in tool_calls
        assert tool_calls["call_1"]["name"] == "run_gaql_query"
        assert tool_calls["call_1"]["result"]["count"] == 2

    def test_compact_display_filters_correctly(self):
        """Test CompactDisplay only shows text."""
        from m8tes.cli.display import CompactDisplay

        events = [
            TextDeltaEvent(type="text-delta", raw={}, delta="Text only "),
            ToolCallStartEvent(
                type="tool-call-start",
                raw={},
                tool_call_id="call_1",
                tool_name="run_gaql_query",
            ),
            ToolResultEndEvent(type="tool-result-end", raw={}, tool_call_id="call_1", result={}),
            TextDeltaEvent(type="text-delta", raw={}, delta="output"),
            DoneEvent(type="done", raw={}),
        ]

        display = CompactDisplay()
        display.start()

        for event in events:
            display.on_event(event)

        display.finish()

        # Should only accumulate text
        assert display.accumulator.get_text() == "Text only output"

    def test_json_display_outputs_all_events(self):
        """Test JsonDisplay outputs all event types."""
        from m8tes.cli.display import JsonDisplay

        events = [
            TextDeltaEvent(type="text-delta", raw={"type": "text-delta"}, delta="Hi"),
            ToolCallStartEvent(
                type="tool-call-start",
                raw={"type": "tool-call-start"},
                tool_call_id="call_1",
                tool_name="test_tool",
            ),
            DoneEvent(type="done", raw={"type": "done"}),
        ]

        display = JsonDisplay()
        display.start()

        for event in events:
            display.on_event(event)

        display.finish()

        # JSON display doesn't accumulate, just outputs
        # Verify it doesn't error at least
        assert True

    def test_verbose_display_prints_markdown_summary(self):
        """Verbose display streams text and ends with markdown-normalized summary."""
        from rich.console import Console

        from m8tes.cli.display import VerboseDisplay

        console = Console(record=True, force_terminal=True, width=80)
        display = VerboseDisplay(console=console)
        display.start()

        events = [
            TextDeltaEvent(
                type="text-delta",
                raw={},
                delta=(
                    "Here is the plan:\n"
                    "- [x] Completed item\n"
                    "- [ ] Pending item\n\n"
                    "| Col A | Col B |\n"
                    "| --- | --- |\n"
                    "| 1 | 2 |\n\n"
                    "```\nprint('hi')\n```"
                ),
            ),
            DoneEvent(type="done", raw={}),
        ]

        for event in events:
            display.on_event(event)

        display.finish()

        output = console.export_text()
        # Streamed text should appear in console
        assert "Here is the plan" in output
        # Final markdown panel title should be present
        assert "Response" in output
        # Task list markers should be converted to unicode checkboxes
        assert "☑ Completed item" in output
        assert "☐ Pending item" in output
        # Table and code block content should be present
        assert "Col A" in output and "Col B" in output
        assert "print('hi')" in output
