"""
AI SDK streaming protocol parser.

Implements the Vercel AI SDK UI message stream protocol for consuming
streaming responses from the agent worker.

Protocol: https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol
"""

from collections.abc import Generator
from dataclasses import dataclass
from enum import Enum
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class StreamEventType(str, Enum):
    """AI SDK stream event types."""

    # Text events
    TEXT_START = "text-start"
    TEXT_DELTA = "text-delta"
    TEXT_END = "text-end"

    # Reasoning/thinking events (Claude, o3-mini, etc)
    REASONING_START = "reasoning-start"
    REASONING_DELTA = "reasoning-delta"
    REASONING_END = "reasoning-end"
    THINKING_START = "thinking-start"
    THINKING_DELTA = "thinking-delta"
    THINKING_END = "thinking-end"

    # Planning events
    PLAN_START = "plan-start"
    PLAN_DELTA = "plan-delta"
    PLAN_END = "plan-end"

    # Tool events
    TOOL_CALL_START = "tool-call-start"
    TOOL_CALL_DELTA = "tool-call-delta"
    TOOL_CALL_END = "tool-call-end"
    TOOL_RESULT_START = "tool-result-start"
    TOOL_RESULT_DELTA = "tool-result-delta"
    TOOL_RESULT_END = "tool-result-end"
    TODO_UPDATE = "todo-update"

    # Message events
    MESSAGE_START = "message-start"
    MESSAGE_DELTA = "message-delta"
    MESSAGE_END = "message-end"

    # Source/reference events
    SOURCE_URL = "source-url"
    SOURCE_DOCUMENT = "source-document"

    # Metadata / usage events
    METADATA = "metadata"
    RUN_METRICS = "run_metrics"

    # Error events
    ERROR = "error"

    # Stream completion
    DONE = "done"

    # Sandbox connection events
    SANDBOX_CONNECTING = "sandbox-connecting"
    SANDBOX_CONNECTED = "sandbox-connected"
    SANDBOX_METRICS = "sandbox_metrics"

    # Unknown/custom events
    UNKNOWN = "unknown"

    # Claude SDK native event types (from agent-runtime normalization)
    # These are the actual event types emitted by Claude Agent SDK
    CLAUDE_MESSAGE_START = "message_start"
    CLAUDE_MESSAGE_DELTA = "message_delta"
    CLAUDE_MESSAGE_STOP = "message_stop"
    CLAUDE_MESSAGE_COMPLETE = "message_complete"
    CLAUDE_CONTENT_BLOCK_START = "content_block_start"
    CLAUDE_CONTENT_BLOCK_DELTA = "content_block_delta"
    CLAUDE_CONTENT_BLOCK_STOP = "content_block_stop"
    CLAUDE_TOOL_USE = "tool_use"
    CLAUDE_TOOL_RESULT = "tool_result"


@dataclass
class StreamEvent:
    """Base class for all stream events."""

    type: StreamEventType
    raw: dict[str, Any]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> list["StreamEvent"]:
        """Parse event from JSON dictionary.

        Expects flat event format (already normalized by agent-runtime).
        No longer handles nested Claude SDK format - agent-runtime normalizes all events.

        Returns:
            List of StreamEvent objects (usually just one event per payload).
        """
        # Check for Claude SDK system messages (init, success, etc)
        if data.get("subtype") in ("init", "success"):
            # Skip system messages entirely
            return []

        # Get event type from flat format
        event_type_str = data.get("type", "unknown")

        # Map string to enum
        try:
            event_type = StreamEventType(event_type_str)
        except ValueError:
            event_type = StreamEventType.UNKNOWN

        event: StreamEvent

        # Create specialized event based on type
        if event_type == StreamEventType.TEXT_DELTA:
            event = TextDeltaEvent(
                type=event_type,
                raw=data,
                delta=data.get("delta", ""),
                id=data.get("id"),
            )
        elif event_type == StreamEventType.TEXT_START:
            event = TextStartEvent(
                type=event_type,
                raw=data,
                id=data.get("id"),
            )
        elif event_type == StreamEventType.TEXT_END:
            event = TextEndEvent(
                type=event_type,
                raw=data,
                id=data.get("id"),
            )
        elif event_type == StreamEventType.REASONING_START:
            event = ReasoningStartEvent(
                type=event_type,
                raw=data,
                id=data.get("id"),
            )
        elif event_type == StreamEventType.REASONING_DELTA:
            event = ReasoningDeltaEvent(
                type=event_type,
                raw=data,
                delta=data.get("delta") or data.get("text") or "",
                id=data.get("id"),
            )
        elif event_type == StreamEventType.REASONING_END:
            event = ReasoningEndEvent(
                type=event_type,
                raw=data,
                id=data.get("id"),
            )
        elif event_type == StreamEventType.THINKING_START:
            event = ThinkingStartEvent(
                type=event_type,
                raw=data,
                id=data.get("id"),
            )
        elif event_type == StreamEventType.THINKING_DELTA:
            event = ThinkingDeltaEvent(
                type=event_type,
                raw=data,
                delta=data.get("delta") or data.get("text") or "",
                id=data.get("id"),
            )
        elif event_type == StreamEventType.THINKING_END:
            event = ThinkingEndEvent(
                type=event_type,
                raw=data,
                id=data.get("id"),
            )
        elif event_type == StreamEventType.PLAN_START:
            event = PlanStartEvent(
                type=event_type,
                raw=data,
                id=data.get("id"),
            )
        elif event_type == StreamEventType.PLAN_DELTA:
            event = PlanDeltaEvent(
                type=event_type,
                raw=data,
                delta=data.get("delta") or data.get("text") or data.get("plan") or "",
                id=data.get("id"),
            )
        elif event_type == StreamEventType.PLAN_END:
            event = PlanEndEvent(
                type=event_type,
                raw=data,
                id=data.get("id"),
            )
        elif event_type == StreamEventType.TOOL_CALL_START:
            event = ToolCallStartEvent(
                type=event_type,
                raw=data,
                tool_call_id=data.get("toolCallId"),
                tool_name=data.get("toolName"),
            )
        elif event_type == StreamEventType.TOOL_CALL_DELTA:
            event = ToolCallDeltaEvent(
                type=event_type,
                raw=data,
                tool_call_id=data.get("toolCallId"),
                delta=data.get("delta", ""),
            )
        elif event_type == StreamEventType.TOOL_CALL_END:
            event = ToolCallEndEvent(
                type=event_type,
                raw=data,
                tool_call_id=data.get("toolCallId"),
            )
        elif event_type == StreamEventType.TOOL_RESULT_START:
            event = ToolResultStartEvent(
                type=event_type,
                raw=data,
                tool_call_id=data.get("toolCallId"),
            )
        elif event_type == StreamEventType.TOOL_RESULT_DELTA:
            event = ToolResultDeltaEvent(
                type=event_type,
                raw=data,
                tool_call_id=data.get("toolCallId"),
                delta=data.get("delta", ""),
            )
        elif event_type == StreamEventType.TOOL_RESULT_END:
            event = ToolResultEndEvent(
                type=event_type,
                raw=data,
                tool_call_id=data.get("toolCallId"),
                result=data.get("result"),
            )
        elif event_type == StreamEventType.MESSAGE_START:
            event = MessageStartEvent(
                type=event_type,
                raw=data,
                message_id=data.get("messageId"),
            )
        elif event_type == StreamEventType.MESSAGE_END:
            event = MessageEndEvent(
                type=event_type,
                raw=data,
                message_id=data.get("messageId"),
            )
        elif event_type == StreamEventType.METADATA:
            payload = data.get("payload")
            if isinstance(payload, dict):
                metadata_payload = payload
            else:
                metadata_payload = {k: v for k, v in data.items() if k != "type"}
            event = MetadataEvent(type=event_type, raw=data, payload=metadata_payload)
        elif event_type == StreamEventType.RUN_METRICS:
            event = MetricsEvent(
                type=event_type,
                raw=data,
                execution_time_ms=data.get("execution_time_ms"),
                input_tokens_used=data.get("input_tokens_used"),
                output_tokens_used=data.get("output_tokens_used"),
                claude_token_cost_usd=data.get("claude_token_cost_usd"),
                stop_reason=data.get("stop_reason"),
                completion_state=data.get("completion_state"),
                unresolved_tool_use_ids=(
                    [
                        tool_id
                        for tool_id in data.get("unresolved_tool_use_ids", [])
                        if isinstance(tool_id, str)
                    ]
                    if isinstance(data.get("unresolved_tool_use_ids"), list)
                    else None
                ),
            )
        elif event_type == StreamEventType.SANDBOX_METRICS:
            event = SandboxMetricsEvent(
                type=event_type,
                raw=data,
                sandbox_execution_time_ms=data.get("sandbox_execution_time_ms"),
            )
        elif event_type == StreamEventType.ERROR:
            event = ErrorEvent(
                type=event_type,
                raw=data,
                error=data.get("error", "Unknown error"),
            )
        elif event_type == StreamEventType.DONE:
            event = DoneEvent(
                type=event_type,
                raw=data,
                completion_state=data.get("completion_state"),
                unresolved_tool_use_ids=(
                    [
                        tool_id
                        for tool_id in data.get("unresolved_tool_use_ids", [])
                        if isinstance(tool_id, str)
                    ]
                    if isinstance(data.get("unresolved_tool_use_ids"), list)
                    else None
                ),
                stop_reason=data.get("stop_reason"),
            )
        elif event_type == StreamEventType.SANDBOX_CONNECTING:
            event = SandboxConnectingEvent(
                type=event_type,
                raw=data,
                message=data.get("message"),
            )
        elif event_type == StreamEventType.SANDBOX_CONNECTED:
            event = SandboxConnectedEvent(
                type=event_type,
                raw=data,
                sandbox_id=data.get("sandbox_id"),
                duration_ms=data.get("duration_ms"),
                message=data.get("message"),
            )
        elif event_type == StreamEventType.TODO_UPDATE:
            todos_payload = data.get("todos")
            if isinstance(todos_payload, list):
                todos_list = [todo for todo in todos_payload if isinstance(todo, dict)]
            else:
                todos_list = []
            event = TodoUpdateEvent(
                type=event_type,
                raw=data,
                tool_call_id=data.get("toolCallId") or data.get("tool_call_id"),
                todos=todos_list,
            )

        # Handle Claude SDK native content_block_delta events
        elif event_type == StreamEventType.CLAUDE_CONTENT_BLOCK_DELTA:
            delta_data = data.get("delta", {})
            delta_type = delta_data.get("type", "")
            block_id = data.get("id")

            if delta_type == "text_delta":
                event = TextDeltaEvent(
                    type=StreamEventType.TEXT_DELTA,
                    raw=data,
                    delta=delta_data.get("text", ""),
                    id=block_id,
                )
            elif delta_type == "thinking_delta":
                event = ThinkingDeltaEvent(
                    type=StreamEventType.THINKING_DELTA,
                    raw=data,
                    delta=delta_data.get("text", ""),
                    id=block_id,
                )
            elif delta_type == "plan_delta":
                event = PlanDeltaEvent(
                    type=StreamEventType.PLAN_DELTA,
                    raw=data,
                    delta=delta_data.get("text", ""),
                    id=block_id,
                )
            elif delta_type == "input_json_delta":
                # Tool input streaming
                event = ToolCallDeltaEvent(
                    type=StreamEventType.TOOL_CALL_DELTA,
                    raw=data,
                    tool_call_id=block_id,
                    delta=delta_data.get("partial_json", ""),
                )
            else:
                # Unknown delta type - return base event
                event = StreamEvent(type=event_type, raw=data)

        # Handle Claude SDK native content_block_start events
        elif event_type == StreamEventType.CLAUDE_CONTENT_BLOCK_START:
            block_data = data.get("content_block", {})
            block_type = block_data.get("type") or data.get("block_type", "")
            block_id = data.get("id") or block_data.get("id")

            if block_type == "text":
                event = TextStartEvent(
                    type=StreamEventType.TEXT_START,
                    raw=data,
                    id=block_id,
                )
            elif block_type == "thinking":
                event = ThinkingStartEvent(
                    type=StreamEventType.THINKING_START,
                    raw=data,
                    id=block_id,
                )
            elif block_type == "plan":
                event = PlanStartEvent(
                    type=StreamEventType.PLAN_START,
                    raw=data,
                    id=block_id,
                )
            elif block_type == "tool_use":
                event = ToolCallStartEvent(
                    type=StreamEventType.TOOL_CALL_START,
                    raw=data,
                    tool_call_id=block_id,
                    tool_name=block_data.get("name") or data.get("name"),
                )
            else:
                # Unknown block type
                event = StreamEvent(type=event_type, raw=data)

        # Handle Claude SDK native content_block_stop events
        elif event_type == StreamEventType.CLAUDE_CONTENT_BLOCK_STOP:
            # Note: We don't know the block type from stop event alone
            # Just create a generic end event
            block_id = data.get("id")
            event = StreamEvent(type=event_type, raw=data)

        # Handle Claude SDK native message events
        elif event_type == StreamEventType.CLAUDE_MESSAGE_START:
            message_data = data.get("message", {})
            event = MessageStartEvent(
                type=StreamEventType.MESSAGE_START,
                raw=data,
                message_id=message_data.get("id"),
            )
        elif (
            event_type == StreamEventType.CLAUDE_MESSAGE_STOP
            or event_type == StreamEventType.CLAUDE_MESSAGE_COMPLETE
        ):
            event = MessageEndEvent(
                type=StreamEventType.MESSAGE_END,
                raw=data,
                message_id=data.get("message_id"),
            )
        elif event_type == StreamEventType.CLAUDE_MESSAGE_DELTA:
            delta_data = data.get("delta", {})
            if isinstance(delta_data, dict) and isinstance(delta_data.get("text"), str):
                event = TextDeltaEvent(
                    type=StreamEventType.TEXT_DELTA,
                    raw=data,
                    delta=delta_data.get("text", ""),
                    id=data.get("id"),
                )
            else:
                event = StreamEvent(type=event_type, raw=data)
        elif event_type == StreamEventType.CLAUDE_TOOL_USE:
            event = ToolCallStartEvent(
                type=StreamEventType.TOOL_CALL_START,
                raw=data,
                tool_call_id=data.get("id"),
                tool_name=data.get("name"),
            )
        elif event_type == StreamEventType.CLAUDE_TOOL_RESULT:
            event = ToolResultEndEvent(
                type=StreamEventType.TOOL_RESULT_END,
                raw=data,
                tool_call_id=data.get("tool_use_id") or data.get("id"),
                result=data.get("content") if "content" in data else data.get("result"),
            )

        else:
            # Return base event for unknown types
            event = StreamEvent(type=event_type, raw=data)

        return [event]


@dataclass
class TextDeltaEvent(StreamEvent):
    """Incremental text chunk."""

    delta: str
    id: str | None = None


@dataclass
class TextStartEvent(StreamEvent):
    """Start of text generation."""

    id: str | None = None


@dataclass
class TextEndEvent(StreamEvent):
    """End of text generation."""

    id: str | None = None


@dataclass
class ReasoningDeltaEvent(StreamEvent):
    """Incremental reasoning text (for o3-mini, etc)."""

    delta: str
    id: str | None = None


@dataclass
class ReasoningStartEvent(StreamEvent):
    """Reasoning section started."""

    id: str | None = None


@dataclass
class ReasoningEndEvent(StreamEvent):
    """Reasoning section ended."""

    id: str | None = None


@dataclass
class ThinkingDeltaEvent(StreamEvent):
    """Incremental Claude thinking output."""

    delta: str
    id: str | None = None


@dataclass
class ThinkingStartEvent(StreamEvent):
    """Claude thinking block started."""

    id: str | None = None


@dataclass
class ThinkingEndEvent(StreamEvent):
    """Claude thinking block ended."""

    id: str | None = None


@dataclass
class PlanDeltaEvent(StreamEvent):
    """Incremental Claude plan output."""

    delta: str
    id: str | None = None


@dataclass
class PlanStartEvent(StreamEvent):
    """Plan section started."""

    id: str | None = None


@dataclass
class PlanEndEvent(StreamEvent):
    """Plan section ended."""

    id: str | None = None


@dataclass
class ToolCallStartEvent(StreamEvent):
    """Tool call begins."""

    tool_call_id: str | None
    tool_name: str | None


@dataclass
class ToolCallEndEvent(StreamEvent):
    """Tool call finished."""

    tool_call_id: str | None


@dataclass
class ToolCallDeltaEvent(StreamEvent):
    """Incremental tool call arguments."""

    tool_call_id: str | None
    delta: str


@dataclass
class ToolResultStartEvent(StreamEvent):
    """Tool result starts streaming."""

    tool_call_id: str | None


@dataclass
class ToolResultDeltaEvent(StreamEvent):
    """Incremental tool result."""

    tool_call_id: str | None
    delta: str


@dataclass
class ToolResultEndEvent(StreamEvent):
    """Tool result complete."""

    tool_call_id: str | None
    result: Any | None


@dataclass
class TodoUpdateEvent(StreamEvent):
    """Structured todo update emitted from the TodoWrite tool."""

    tool_call_id: str | None
    todos: list[dict[str, Any]]


@dataclass
class MessageStartEvent(StreamEvent):
    """New message begins."""

    message_id: str | None


@dataclass
class MessageEndEvent(StreamEvent):
    """Message is complete."""

    message_id: str | None


@dataclass
class MetadataEvent(StreamEvent):
    """Structured metadata emitted alongside stream (usage, session info, etc)."""

    payload: dict[str, Any]


@dataclass
class MetricsEvent(StreamEvent):
    """Claude execution metrics."""

    execution_time_ms: int | None
    input_tokens_used: int | None
    output_tokens_used: int | None
    claude_token_cost_usd: float | None
    stop_reason: str | None = None
    completion_state: str | None = None
    unresolved_tool_use_ids: list[str] | None = None


@dataclass
class SandboxMetricsEvent(StreamEvent):
    """Sandbox execution metrics."""

    sandbox_execution_time_ms: int | None


@dataclass
class ErrorEvent(StreamEvent):
    """Error occurred during streaming."""

    error: str


@dataclass
class DoneEvent(StreamEvent):
    """Stream complete marker."""

    completion_state: str | None = None
    unresolved_tool_use_ids: list[str] | None = None
    stop_reason: str | None = None


@dataclass
class SandboxConnectingEvent(StreamEvent):
    """Sandbox connection is starting."""

    message: str | None = None


@dataclass
class SandboxConnectedEvent(StreamEvent):
    """Sandbox connection completed."""

    sandbox_id: str | None = None
    duration_ms: int | None = None
    message: str | None = None


class AISDKStreamParser:
    """
    Parser for AI SDK UI message stream protocol.

    Handles Server-Sent Events (SSE) format with JSON payloads.
    """

    @staticmethod
    def parse_sse_line(line: str) -> list[StreamEvent]:
        """
        Parse a single SSE frame into StreamEvent objects.

        Args:
            line: SSE frame content (one or more lines, without trailing blank line)

        Returns:
            List of StreamEvents (possibly empty if the frame carries metadata only)
        """
        if not line or not line.strip():
            return []

        data_lines: list[str] = []
        for raw_line in line.splitlines():
            stripped = raw_line.strip()
            if not stripped or stripped.startswith(":"):
                continue
            if raw_line.startswith("data:"):
                data_lines.append(raw_line[5:].lstrip(" "))

        if not data_lines:
            return []

        payload = "\n".join(data_lines).strip()
        if not payload:
            return []

        if payload == "[DONE]":
            return [DoneEvent(type=StreamEventType.DONE, raw={})]

        try:
            data = json.loads(payload)
            return StreamEvent.from_dict(data)
        except json.JSONDecodeError:
            logger.warning("Failed to parse SSE JSON: %s", payload[:200])
            return []

    @staticmethod
    def parse_stream(
        response: object, decode_unicode: bool = True
    ) -> Generator[StreamEvent, None, None]:
        """
        Parse SSE stream from HTTP response.

        Args:
            response: requests.Response object with streaming enabled
            decode_unicode: Decode lines as unicode

        Yields:
            StreamEvent objects
        """
        frame_lines: list[str] = []
        for line in response.iter_lines(decode_unicode=decode_unicode):  # type: ignore[attr-defined]
            if isinstance(line, bytes):
                line = line.decode("utf-8", errors="replace")

            # Empty line terminates an SSE frame.
            if line == "":
                if frame_lines:
                    frame = "\n".join(frame_lines)
                    frame_lines = []
                    events = AISDKStreamParser.parse_sse_line(frame)
                    yield from events
                continue

            frame_lines.append(line)

        # Flush trailing frame if stream ended without a final blank line.
        if frame_lines:
            frame = "\n".join(frame_lines)
            events = AISDKStreamParser.parse_sse_line(frame)
            yield from events


class StreamAccumulator:
    """
    Accumulates streaming events into complete messages.

    Useful for collecting all text deltas into a single string.
    """

    def __init__(self) -> None:
        self.text_parts: list[str] = []
        self.reasoning_parts: list[str] = []
        self.plan_parts: list[str] = []
        self.tool_calls: dict[str, dict[str, Any]] = {}
        self.current_message_id: str | None = None
        self.errors: list[str] = []
        self.metadata_events: list[dict[str, Any]] = []
        self.latest_usage: dict[str, Any] | None = None
        self.todo_updates: list[dict[str, Any]] = []

    def process(self, event: StreamEvent) -> None:
        """Process a stream event and accumulate data."""
        if isinstance(event, TextDeltaEvent):
            self.text_parts.append(event.delta)

        elif isinstance(event, ReasoningDeltaEvent | ThinkingDeltaEvent):
            self.reasoning_parts.append(event.delta)

        elif isinstance(
            event,
            ReasoningStartEvent | ThinkingStartEvent | ReasoningEndEvent | ThinkingEndEvent,
        ):
            if self.reasoning_parts and not self.reasoning_parts[-1].endswith("\n"):
                self.reasoning_parts.append("\n")

        elif isinstance(event, PlanDeltaEvent):
            self.plan_parts.append(event.delta)

        elif isinstance(event, PlanStartEvent | PlanEndEvent):
            if self.plan_parts and not self.plan_parts[-1].endswith("\n"):
                self.plan_parts.append("\n")

        elif isinstance(event, ToolCallStartEvent):
            if event.tool_call_id:
                self.tool_calls[event.tool_call_id] = {
                    "name": event.tool_name,
                    "arguments": "",
                    "result": None,
                    "result_chunks": "",
                    "todos": None,
                    "completed": False,
                }

        elif isinstance(event, ToolCallDeltaEvent):
            if event.tool_call_id and event.tool_call_id in self.tool_calls:
                self.tool_calls[event.tool_call_id]["arguments"] += event.delta

        elif isinstance(event, ToolResultStartEvent):
            if event.tool_call_id and event.tool_call_id not in self.tool_calls:
                self.tool_calls[event.tool_call_id] = {
                    "name": None,
                    "arguments": "",
                    "result": None,
                    "result_chunks": "",
                    "todos": None,
                    "completed": False,
                }
            elif event.tool_call_id and event.tool_call_id in self.tool_calls:
                self.tool_calls[event.tool_call_id].setdefault("completed", False)

        elif isinstance(event, ToolResultDeltaEvent):
            if event.tool_call_id and event.tool_call_id in self.tool_calls:
                self.tool_calls[event.tool_call_id]["result_chunks"] += event.delta

        elif isinstance(event, ToolResultEndEvent):
            if event.tool_call_id and event.tool_call_id in self.tool_calls:
                self.tool_calls[event.tool_call_id]["result"] = (
                    event.result
                    if event.result is not None
                    else self.tool_calls[event.tool_call_id].get("result_chunks") or None
                )
                self.tool_calls[event.tool_call_id]["completed"] = True

        elif isinstance(event, ToolCallEndEvent):
            if event.tool_call_id:
                tool_state = self.tool_calls.setdefault(
                    event.tool_call_id,
                    {
                        "name": None,
                        "arguments": "",
                        "result": None,
                        "result_chunks": "",
                        "todos": None,
                        "completed": False,
                    },
                )
                tool_state["completed"] = True
        elif isinstance(event, TodoUpdateEvent):
            update_payload = {
                "tool_call_id": event.tool_call_id,
                "todos": event.todos,
            }
            self.todo_updates.append(update_payload)
            if event.tool_call_id:
                tool_state = self.tool_calls.setdefault(
                    event.tool_call_id,
                    {
                        "name": None,
                        "arguments": "",
                        "result": None,
                        "result_chunks": "",
                        "todos": None,
                        "completed": False,
                    },
                )
                tool_state["todos"] = event.todos

        elif isinstance(event, MessageStartEvent):
            self.current_message_id = event.message_id

        elif isinstance(event, MessageEndEvent):
            self.current_message_id = None

        elif isinstance(event, ErrorEvent):
            self.errors.append(event.error)

        elif isinstance(event, MetadataEvent):
            self.metadata_events.append(event.payload)
            usage = event.payload.get("usage") if isinstance(event.payload, dict) else None
            if isinstance(usage, dict):
                self.latest_usage = usage

    def get_text(self) -> str:
        """Get accumulated text."""
        return "".join(self.text_parts)

    def get_reasoning(self) -> str:
        """Get accumulated reasoning."""
        return "".join(self.reasoning_parts)

    def get_plan(self) -> str:
        """Get accumulated plan text."""
        return "".join(self.plan_parts)

    def get_tool_calls(self) -> dict[str, dict[str, Any]]:
        """Get all tool calls with results."""
        normalized: dict[str, dict[str, Any]] = {}
        for tool_id, data in self.tool_calls.items():
            normalized[tool_id] = {
                "name": data.get("name"),
                "arguments": data.get("arguments"),
                "result": data.get("result") or data.get("result_chunks") or None,
                "todos": data.get("todos"),
                "completed": bool(data.get("completed")),
            }
        return normalized

    def has_errors(self) -> bool:
        """Check if any errors occurred."""
        return len(self.errors) > 0

    def get_errors(self) -> list[str]:
        """Get all error messages."""
        return self.errors

    def get_metadata(self) -> list[dict[str, Any]]:
        """Return raw metadata events."""
        return self.metadata_events

    def get_usage(self) -> dict[str, Any] | None:
        """Return the most recent usage payload, if available."""
        return self.latest_usage

    def get_todo_updates(self) -> list[dict[str, Any]]:
        """Return structured todo snapshots as they were streamed."""
        return self.todo_updates
