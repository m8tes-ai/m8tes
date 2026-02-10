"""
Unit tests for AI SDK streaming protocol parser.
"""

import json

from m8tes.streaming import (
    AISDKStreamParser,
    DoneEvent,
    ErrorEvent,
    MessageEndEvent,
    MessageStartEvent,
    MetadataEvent,
    MetricsEvent,
    PlanDeltaEvent,
    PlanEndEvent,
    PlanStartEvent,
    ReasoningDeltaEvent,
    ReasoningEndEvent,
    ReasoningStartEvent,
    SandboxMetricsEvent,
    StreamAccumulator,
    StreamEvent,
    StreamEventType,
    TextDeltaEvent,
    TextEndEvent,
    TextStartEvent,
    ThinkingDeltaEvent,
    ThinkingEndEvent,
    ThinkingStartEvent,
    TodoUpdateEvent,
    ToolCallDeltaEvent,
    ToolCallEndEvent,
    ToolCallStartEvent,
    ToolResultDeltaEvent,
    ToolResultEndEvent,
    ToolResultStartEvent,
)


class TestStreamEventParsing:
    """Test parsing of individual stream events."""

    def test_parse_text_delta(self):
        """Test parsing text-delta event."""
        line = 'data: {"type":"text-delta","id":"text_123","delta":"Hello "}'
        events = AISDKStreamParser.parse_sse_line(line)
        assert len(events) == 1
        event = events[0]

        assert isinstance(event, TextDeltaEvent)
        assert event.type == StreamEventType.TEXT_DELTA
        assert event.delta == "Hello "
        assert event.id == "text_123"

    def test_parse_text_start(self):
        """Test parsing text-start event."""
        line = 'data: {"type":"text-start","id":"text_456"}'
        events = AISDKStreamParser.parse_sse_line(line)
        assert len(events) == 1
        event = events[0]

        assert isinstance(event, TextStartEvent)
        assert event.type == StreamEventType.TEXT_START
        assert event.id == "text_456"

    def test_parse_text_end(self):
        """Test parsing text-end event."""
        line = 'data: {"type":"text-end","id":"text_789"}'
        events = AISDKStreamParser.parse_sse_line(line)
        assert len(events) == 1
        event = events[0]

        assert isinstance(event, TextEndEvent)
        assert event.type == StreamEventType.TEXT_END
        assert event.id == "text_789"

    def test_parse_reasoning_delta(self):
        """Test parsing reasoning-delta event."""
        line = 'data: {"type":"reasoning-delta","id":"reasoning_1","delta":"Let me think..."}'
        events = AISDKStreamParser.parse_sse_line(line)
        assert len(events) == 1
        event = events[0]

        assert isinstance(event, ReasoningDeltaEvent)
        assert event.type == StreamEventType.REASONING_DELTA
        assert event.delta == "Let me think..."

    def test_parse_reasoning_start_end(self):
        """Reasoning start/end markers should map to dedicated events."""
        start_events = AISDKStreamParser.parse_sse_line(
            'data: {"type":"reasoning-start","id":"reasoning_99"}'
        )
        end_events = AISDKStreamParser.parse_sse_line(
            'data: {"type":"reasoning-end","id":"reasoning_99"}'
        )

        assert len(start_events) == 1
        assert isinstance(start_events[0], ReasoningStartEvent)
        assert start_events[0].id == "reasoning_99"

        assert len(end_events) == 1
        assert isinstance(end_events[0], ReasoningEndEvent)
        assert end_events[0].id == "reasoning_99"

    def test_parse_thinking_delta(self):
        """Thinking-delta events should emit ThinkingDeltaEvent."""
        line = 'data: {"type":"thinking-delta","id":"thinking_1","delta":"Analyzing..."}'
        events = AISDKStreamParser.parse_sse_line(line)

        assert len(events) == 1
        event = events[0]
        assert isinstance(event, ThinkingDeltaEvent)
        assert event.delta == "Analyzing..."

    def test_parse_thinking_start_end(self):
        """Thinking start/end events should be surfaced."""
        start_events = AISDKStreamParser.parse_sse_line(
            'data: {"type":"thinking-start","id":"thinking_1"}'
        )
        end_events = AISDKStreamParser.parse_sse_line(
            'data: {"type":"thinking-end","id":"thinking_1"}'
        )

        assert len(start_events) == 1
        assert isinstance(start_events[0], ThinkingStartEvent)
        assert start_events[0].id == "thinking_1"

        assert len(end_events) == 1
        assert isinstance(end_events[0], ThinkingEndEvent)
        assert end_events[0].id == "thinking_1"

    def test_parse_tool_call_start(self):
        """Test parsing tool-call-start event."""
        line = (
            'data: {"type":"tool-call-start","toolCallId":"call_123","toolName":"run_gaql_query"}'
        )
        events = AISDKStreamParser.parse_sse_line(line)
        assert len(events) == 1
        event = events[0]

        assert isinstance(event, ToolCallStartEvent)
        assert event.type == StreamEventType.TOOL_CALL_START
        assert event.tool_call_id == "call_123"
        assert event.tool_name == "run_gaql_query"

    def test_parse_tool_call_delta(self):
        """Test parsing tool-call-delta event."""
        line = 'data: {"type":"tool-call-delta","toolCallId":"call_123","delta":"{\\"query\\":"}'
        events = AISDKStreamParser.parse_sse_line(line)
        assert len(events) == 1
        event = events[0]

        assert isinstance(event, ToolCallDeltaEvent)
        assert event.type == StreamEventType.TOOL_CALL_DELTA
        assert event.tool_call_id == "call_123"
        assert event.delta == '{"query":'

    def test_parse_tool_result_start(self):
        """Test parsing tool-result-start event."""
        line = 'data: {"type":"tool-result-start","toolCallId":"call_123"}'
        events = AISDKStreamParser.parse_sse_line(line)
        assert len(events) == 1
        event = events[0]

        assert isinstance(event, ToolResultStartEvent)
        assert event.type == StreamEventType.TOOL_RESULT_START
        assert event.tool_call_id == "call_123"

    def test_parse_tool_result_end(self):
        """Test parsing tool-result-end event with result."""
        result_data = {"rows": [{"campaign": "Summer Sale"}], "count": 1}
        line = f'data: {{"type":"tool-result-end","toolCallId":"call_123","result":{json.dumps(result_data)}}}'  # noqa: E501
        events = AISDKStreamParser.parse_sse_line(line)
        assert len(events) == 1
        event = events[0]

        assert isinstance(event, ToolResultEndEvent)
        assert event.type == StreamEventType.TOOL_RESULT_END
        assert event.tool_call_id == "call_123"
        assert event.result == result_data

    def test_parse_message_start(self):
        """Test parsing message-start event."""
        line = 'data: {"type":"message-start","messageId":"msg_abc123"}'
        events = AISDKStreamParser.parse_sse_line(line)
        assert len(events) == 1
        event = events[0]

        assert isinstance(event, MessageStartEvent)
        assert event.type == StreamEventType.MESSAGE_START
        assert event.message_id == "msg_abc123"

    def test_parse_run_metrics_event(self):
        """Run metrics events should parse into MetricsEvent."""
        line = (
            'data: {"type":"run_metrics","execution_time_ms":1000,'
            '"input_tokens_used":111,"output_tokens_used":222,'
            '"claude_token_cost_usd":0.456}'
        )

        events = AISDKStreamParser.parse_sse_line(line)
        assert len(events) == 1
        event = events[0]

        assert isinstance(event, MetricsEvent)
        assert event.execution_time_ms == 1000
        assert event.input_tokens_used == 111
        assert event.output_tokens_used == 222
        assert event.claude_token_cost_usd == 0.456
        assert event.stop_reason is None

    def test_parse_run_metrics_event_with_stop_reason(self):
        """run_metrics stop_reason should be parsed."""
        line = (
            'data: {"type":"run_metrics","execution_time_ms":1000,'
            '"input_tokens_used":111,"output_tokens_used":222,'
            '"claude_token_cost_usd":0.456,"stop_reason":"refusal"}'
        )

        events = AISDKStreamParser.parse_sse_line(line)
        assert len(events) == 1
        event = events[0]

        assert isinstance(event, MetricsEvent)
        assert event.stop_reason == "refusal"

    def test_parse_sandbox_metrics_event(self):
        """Sandbox metrics events should parse into SandboxMetricsEvent."""
        line = 'data: {"type":"sandbox_metrics","sandbox_execution_time_ms":4321}'
        events = AISDKStreamParser.parse_sse_line(line)
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, SandboxMetricsEvent)
        assert event.sandbox_execution_time_ms == 4321

    def test_parse_error(self):
        """Test parsing error event."""
        line = 'data: {"type":"error","error":"API rate limit exceeded"}'
        events = AISDKStreamParser.parse_sse_line(line)
        assert len(events) == 1
        event = events[0]

        assert isinstance(event, ErrorEvent)
        assert event.type == StreamEventType.ERROR
        assert event.error == "API rate limit exceeded"

    def test_parse_done_json(self):
        """Test parsing done event as JSON."""
        line = 'data: {"type":"done"}'
        events = AISDKStreamParser.parse_sse_line(line)
        assert len(events) == 1
        event = events[0]

        assert isinstance(event, DoneEvent)
        assert event.type == StreamEventType.DONE

    def test_parse_done_marker(self):
        """Test parsing [DONE] marker."""
        line = "data: [DONE]"
        events = AISDKStreamParser.parse_sse_line(line)
        assert len(events) == 1
        event = events[0]

        assert isinstance(event, DoneEvent)
        assert event.type == StreamEventType.DONE

    def test_parse_unknown_type(self):
        """Test parsing unknown event type."""
        line = 'data: {"type":"custom-event","foo":"bar"}'
        events = AISDKStreamParser.parse_sse_line(line)
        assert len(events) == 1
        event = events[0]

        assert isinstance(event, StreamEvent)
        assert event.type == StreamEventType.UNKNOWN
        assert event.raw["foo"] == "bar"

    def test_parse_empty_line(self):
        """Test parsing empty line returns empty list."""
        assert AISDKStreamParser.parse_sse_line("") == []
        assert AISDKStreamParser.parse_sse_line("   ") == []

    def test_parse_malformed_json(self):
        """Test parsing malformed JSON returns empty list."""
        line = "data: {not valid json}"
        events = AISDKStreamParser.parse_sse_line(line)
        assert events == []

    def test_parse_non_data_line(self):
        """Test parsing non-data SSE lines returns empty list."""
        assert AISDKStreamParser.parse_sse_line("event: message") == []
        assert AISDKStreamParser.parse_sse_line("id: 123") == []
        assert AISDKStreamParser.parse_sse_line("retry: 1000") == []

    def test_parse_claude_plan_delta(self):
        """Plan delta event (flat format) should map to PlanDeltaEvent."""
        # Flat format (normalized by agent-runtime)
        line = 'data: {"type":"plan-delta","delta":"Step 1: Gather data"}'
        events = AISDKStreamParser.parse_sse_line(line)

        assert len(events) == 1
        event = events[0]
        assert isinstance(event, PlanDeltaEvent)
        assert event.delta == "Step 1: Gather data"

    def test_parse_plan_start_end(self):
        """Plan start/end events should emit typed events."""
        start_events = AISDKStreamParser.parse_sse_line('data: {"type":"plan-start","id":"plan_1"}')
        end_events = AISDKStreamParser.parse_sse_line('data: {"type":"plan-end","id":"plan_1"}')

        assert len(start_events) == 1
        assert isinstance(start_events[0], PlanStartEvent)
        assert start_events[0].id == "plan_1"

        assert len(end_events) == 1
        assert isinstance(end_events[0], PlanEndEvent)
        assert end_events[0].id == "plan_1"

    def test_parse_claude_native_content_block_delta(self):
        """Claude SDK native content_block_delta should map to TextDeltaEvent."""
        # Flat format from agent-runtime (normalized from Claude SDK)
        line = json.dumps(
            {
                "type": "content_block_delta",
                "id": "block_123",
                "delta": {"type": "text_delta", "text": "Hello world"},
            }
        )
        events = AISDKStreamParser.parse_sse_line(f"data: {line}")

        assert len(events) == 1
        event = events[0]
        assert isinstance(event, TextDeltaEvent)
        assert event.delta == "Hello world"
        assert event.id == "block_123"

    def test_parse_claude_native_content_block_start(self):
        """Claude SDK native content_block_start should map to TextStartEvent."""
        line = json.dumps(
            {
                "type": "content_block_start",
                "id": "block_456",
                "content_block": {"type": "text", "text": ""},
            }
        )
        events = AISDKStreamParser.parse_sse_line(f"data: {line}")

        assert len(events) == 1
        event = events[0]
        assert isinstance(event, TextStartEvent)
        assert event.id == "block_456"

    def test_parse_claude_tool_use_event(self):
        """Canonical tool_use events should map to ToolCallStartEvent."""
        line = 'data: {"type":"tool_use","id":"tool_1","name":"run_gaql_query"}'
        events = AISDKStreamParser.parse_sse_line(line)
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, ToolCallStartEvent)
        assert event.tool_call_id == "tool_1"
        assert event.tool_name == "run_gaql_query"

    def test_parse_claude_tool_result_event(self):
        """Canonical tool_result events should map to ToolResultEndEvent."""
        line = 'data: {"type":"tool_result","tool_use_id":"tool_1","content":{"count":3}}'
        events = AISDKStreamParser.parse_sse_line(line)
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, ToolResultEndEvent)
        assert event.tool_call_id == "tool_1"
        assert event.result == {"count": 3}

    def test_parse_multiline_sse_frame(self):
        """Multi-line data frames should be joined and parsed as one payload."""
        frame = 'data: {"type":"message-start",\ndata: "messageId":"msg_1"}'
        events = AISDKStreamParser.parse_sse_line(frame)
        assert len(events) == 1
        assert isinstance(events[0], MessageStartEvent)
        assert events[0].message_id == "msg_1"

    def test_parse_standard_todo_update_event(self):
        """Direct todo-update events should parse correctly."""
        line = json.dumps(
            {
                "type": "todo-update",
                "toolCallId": "call_99",
                "todos": [
                    {"id": "1", "content": "Example", "status": "completed"},
                ],
            }
        )
        events = AISDKStreamParser.parse_sse_line(f"data: {line}")
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, TodoUpdateEvent)
        assert event.tool_call_id == "call_99"
        assert event.todos[0]["status"] == "completed"


class TestStreamAccumulator:
    """Test stream event accumulation."""

    def test_accumulate_text_deltas(self):
        """Test accumulating text delta events."""
        accumulator = StreamAccumulator()

        events = [
            TextDeltaEvent(type=StreamEventType.TEXT_DELTA, raw={}, delta="Hello ", id="1"),
            TextDeltaEvent(type=StreamEventType.TEXT_DELTA, raw={}, delta="world", id="2"),
            TextDeltaEvent(type=StreamEventType.TEXT_DELTA, raw={}, delta="!", id="3"),
        ]

        for event in events:
            accumulator.process(event)

        assert accumulator.get_text() == "Hello world!"

    def test_accumulate_reasoning_deltas(self):
        """Test accumulating reasoning delta events."""
        accumulator = StreamAccumulator()

        events = [
            ReasoningDeltaEvent(
                type=StreamEventType.REASONING_DELTA,
                raw={},
                delta="First, I'll ",
                id="1",
            ),
            ReasoningDeltaEvent(
                type=StreamEventType.REASONING_DELTA,
                raw={},
                delta="check the data...",
                id="2",
            ),
        ]

        for event in events:
            accumulator.process(event)

        assert accumulator.get_reasoning() == "First, I'll check the data..."

    def test_accumulate_tool_calls(self):
        """Test accumulating tool call events."""
        accumulator = StreamAccumulator()

        events = [
            ToolCallStartEvent(
                type=StreamEventType.TOOL_CALL_START,
                raw={},
                tool_call_id="call_123",
                tool_name="run_gaql_query",
            ),
            ToolCallDeltaEvent(
                type=StreamEventType.TOOL_CALL_DELTA,
                raw={},
                tool_call_id="call_123",
                delta='{"query":',
            ),
            ToolCallDeltaEvent(
                type=StreamEventType.TOOL_CALL_DELTA,
                raw={},
                tool_call_id="call_123",
                delta='"SELECT..."',
            ),
            ToolCallDeltaEvent(
                type=StreamEventType.TOOL_CALL_DELTA,
                raw={},
                tool_call_id="call_123",
                delta="}",
            ),
            ToolResultEndEvent(
                type=StreamEventType.TOOL_RESULT_END,
                raw={},
                tool_call_id="call_123",
                result={"rows": [{"campaign": "Test"}], "count": 1},
            ),
        ]

        for event in events:
            accumulator.process(event)

        tool_calls = accumulator.get_tool_calls()
        assert "call_123" in tool_calls
        assert tool_calls["call_123"]["name"] == "run_gaql_query"
        assert tool_calls["call_123"]["arguments"] == '{"query":"SELECT..."}'
        assert tool_calls["call_123"]["result"]["count"] == 1
        assert tool_calls["call_123"]["completed"] is True

    def test_accumulate_tool_result_deltas(self):
        """Tool result deltas should be stitched into final result when end event has no payload."""
        accumulator = StreamAccumulator()

        events = [
            ToolCallStartEvent(
                type=StreamEventType.TOOL_CALL_START,
                raw={},
                tool_call_id="call_456",
                tool_name="lookup",
            ),
            ToolResultStartEvent(
                type=StreamEventType.TOOL_RESULT_START,
                raw={},
                tool_call_id="call_456",
            ),
            ToolResultDeltaEvent(
                type=StreamEventType.TOOL_RESULT_DELTA,
                raw={},
                tool_call_id="call_456",
                delta='{"rows":1',
            ),
            ToolResultDeltaEvent(
                type=StreamEventType.TOOL_RESULT_DELTA,
                raw={},
                tool_call_id="call_456",
                delta=',"status":"ok"}',
            ),
            ToolResultEndEvent(
                type=StreamEventType.TOOL_RESULT_END,
                raw={},
                tool_call_id="call_456",
                result=None,
            ),
        ]

        for event in events:
            accumulator.process(event)

        tool_calls = accumulator.get_tool_calls()
        assert tool_calls["call_456"]["result"] == '{"rows":1,"status":"ok"}'
        assert tool_calls["call_456"]["completed"] is True

    def test_tool_call_end_without_result_marks_completion(self):
        """Tool calls ending without explicit result should still mark completed."""
        accumulator = StreamAccumulator()

        events = [
            ToolCallStartEvent(
                type=StreamEventType.TOOL_CALL_START,
                raw={},
                tool_call_id="call_789",
                tool_name="TodoWrite",
            ),
            ToolCallEndEvent(
                type=StreamEventType.TOOL_CALL_END,
                raw={},
                tool_call_id="call_789",
            ),
        ]

        for event in events:
            accumulator.process(event)

        tool_calls = accumulator.get_tool_calls()
        assert tool_calls["call_789"]["completed"] is True
        assert tool_calls["call_789"]["result"] is None

    def test_accumulate_plan_and_metadata(self):
        """Plan and metadata events should be tracked."""
        accumulator = StreamAccumulator()

        events = [
            PlanDeltaEvent(type=StreamEventType.PLAN_DELTA, raw={}, delta="Step 1\n"),
            PlanDeltaEvent(type=StreamEventType.PLAN_DELTA, raw={}, delta="Step 2"),
            MetadataEvent(
                type=StreamEventType.METADATA,
                raw={},
                payload={"usage": {"input_tokens": 12, "output_tokens": 34}},
            ),
        ]

        for event in events:
            accumulator.process(event)

        assert accumulator.get_plan() == "Step 1\nStep 2"
        assert accumulator.get_metadata()[0]["usage"]["input_tokens"] == 12
        assert accumulator.get_usage() == {"input_tokens": 12, "output_tokens": 34}

    def test_accumulate_errors(self):
        """Test accumulating error events."""
        accumulator = StreamAccumulator()

        events = [
            ErrorEvent(type=StreamEventType.ERROR, raw={}, error="Error 1: Connection failed"),
            ErrorEvent(type=StreamEventType.ERROR, raw={}, error="Error 2: Timeout"),
        ]

        for event in events:
            accumulator.process(event)

        assert accumulator.has_errors()
        errors = accumulator.get_errors()
        assert len(errors) == 2
        assert "Connection failed" in errors[0]
        assert "Timeout" in errors[1]

    def test_message_start(self):
        """Test message start event."""
        accumulator = StreamAccumulator()

        event = MessageStartEvent(type=StreamEventType.MESSAGE_START, raw={}, message_id="msg_123")
        accumulator.process(event)

        assert accumulator.current_message_id == "msg_123"

    def test_message_end_resets_id(self):
        """Message end should clear current message tracking."""
        accumulator = StreamAccumulator()
        accumulator.process(
            MessageStartEvent(type=StreamEventType.MESSAGE_START, raw={}, message_id="msg_123")
        )
        accumulator.process(
            MessageEndEvent(type=StreamEventType.MESSAGE_END, raw={}, message_id="msg_123")
        )

        assert accumulator.current_message_id is None

    def test_empty_accumulator(self):
        """Test empty accumulator returns empty values."""
        accumulator = StreamAccumulator()

        assert accumulator.get_text() == ""
        assert accumulator.get_reasoning() == ""
        assert accumulator.get_plan() == ""
        assert accumulator.get_tool_calls() == {}
        assert not accumulator.has_errors()
        assert accumulator.get_errors() == []
        assert accumulator.get_metadata() == []
        assert accumulator.get_usage() is None

    def test_accumulate_todo_updates(self):
        """Todo update events should be tracked and exposed."""
        accumulator = StreamAccumulator()

        initial_todos = [
            {"id": "todo-1", "content": "Draft outline", "status": "pending"},
            {"id": "todo-2", "content": "Collect data", "status": "in_progress"},
        ]
        completed_todos = [
            {"id": "todo-1", "content": "Draft outline", "status": "completed"},
            {"id": "todo-2", "content": "Collect data", "status": "completed"},
        ]

        events = [
            ToolCallStartEvent(
                type=StreamEventType.TOOL_CALL_START,
                raw={},
                tool_call_id="todo-call-1",
                tool_name="TodoWrite",
            ),
            TodoUpdateEvent(
                type=StreamEventType.TODO_UPDATE,
                raw={},
                tool_call_id="todo-call-1",
                todos=initial_todos,
            ),
            ToolResultEndEvent(
                type=StreamEventType.TOOL_RESULT_END,
                raw={},
                tool_call_id="todo-call-1",
                result={"todos": completed_todos},
            ),
            TodoUpdateEvent(
                type=StreamEventType.TODO_UPDATE,
                raw={},
                tool_call_id="todo-call-1",
                todos=completed_todos,
            ),
        ]

        for event in events:
            accumulator.process(event)

        updates = accumulator.get_todo_updates()
        assert len(updates) == 2
        assert updates[-1]["todos"][0]["status"] == "completed"

        tool_calls = accumulator.get_tool_calls()
        assert "todo-call-1" in tool_calls
        assert tool_calls["todo-call-1"]["todos"][1]["status"] == "completed"


class TestFullStreamParsing:
    """Test parsing complete SSE streams."""

    def test_parse_complete_stream(self):
        """Test parsing a complete message stream."""
        # Mock SSE stream lines
        sse_lines = [
            'data: {"type":"message-start","messageId":"msg_1"}',
            'data: {"type":"text-start","id":"text_1"}',
            'data: {"type":"text-delta","id":"text_1","delta":"I found "}',
            'data: {"type":"text-delta","id":"text_1","delta":"3 campaigns"}',
            'data: {"type":"tool-call-start","toolCallId":"call_1","toolName":"run_gaql_query"}',
            'data: {"type":"tool-result-end","toolCallId":"call_1","result":{"count":3}}',
            'data: {"type":"text-delta","id":"text_1","delta":" for you."}',
            'data: {"type":"text-end","id":"text_1"}',
            "data: [DONE]",
        ]

        # Parse all events
        events = []
        for line in sse_lines:
            events.extend(AISDKStreamParser.parse_sse_line(line))

        # Verify event sequence
        assert len(events) == 9
        assert isinstance(events[0], MessageStartEvent)
        assert isinstance(events[1], TextStartEvent)
        assert isinstance(events[2], TextDeltaEvent)
        assert isinstance(events[4], ToolCallStartEvent)
        assert isinstance(events[5], ToolResultEndEvent)
        assert isinstance(events[-1], DoneEvent)

        # Accumulate and verify
        accumulator = StreamAccumulator()
        for event in events:
            accumulator.process(event)

        assert accumulator.get_text() == "I found 3 campaigns for you."
        assert "call_1" in accumulator.get_tool_calls()
        assert accumulator.get_tool_calls()["call_1"]["result"]["count"] == 3

    def test_parse_stream_handles_multiline_frames(self):
        """parse_stream should group lines by blank separators into SSE frames."""

        class MockResponse:
            def iter_lines(self, decode_unicode=True):
                _ = decode_unicode
                lines = [
                    'data: {"type":"message-start",',
                    'data: "messageId":"msg_1"}',
                    "",
                    'data: {"type":"done"}',
                    "",
                ]
                for item in lines:
                    yield item

        events = list(AISDKStreamParser.parse_stream(MockResponse()))
        assert len(events) == 2
        assert isinstance(events[0], MessageStartEvent)
        assert isinstance(events[1], DoneEvent)
