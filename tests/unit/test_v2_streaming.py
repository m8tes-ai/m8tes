"""Tests for v2 RunStream context manager."""

import json
from unittest.mock import MagicMock

from m8tes._streaming import RunStream
from m8tes.streaming import StreamEvent


def _sse_frame(data: dict | str) -> list[str]:
    """Build SSE frame lines (data line + empty separator)."""
    payload = data if isinstance(data, str) else json.dumps(data)
    return [f"data: {payload}", ""]


class TestRunStream:
    def _make_response(self, lines: list[str]):
        """Create a mock response that yields SSE lines (decoded strings)."""
        resp = MagicMock()
        resp.iter_lines.return_value = iter(lines)
        resp.close = MagicMock()
        return resp

    def test_iteration_yields_events(self):
        lines = _sse_frame({"type": "text-delta", "delta": "Hello"})
        resp = self._make_response(lines)
        stream = RunStream(resp)
        events = list(stream)
        assert len(events) == 1
        assert isinstance(events[0], StreamEvent)

    def test_context_manager_closes_response(self):
        resp = self._make_response([])
        with RunStream(resp) as stream:
            list(stream)
        resp.close.assert_called_once()

    def test_text_accumulation(self):
        lines = _sse_frame({"type": "text-delta", "delta": "Hello"}) + _sse_frame(
            {"type": "text-delta", "delta": " world"}
        )
        resp = self._make_response(lines)
        stream = RunStream(resp)
        list(stream)
        assert stream.text == "Hello world"

    def test_output_is_alias_for_text(self):
        lines = _sse_frame({"type": "text-delta", "delta": "Test"})
        resp = self._make_response(lines)
        stream = RunStream(resp)
        list(stream)
        assert stream.output == stream.text == "Test"

    def test_done_event(self):
        lines = _sse_frame("[DONE]")
        resp = self._make_response(lines)
        stream = RunStream(resp)
        events = list(stream)
        assert len(events) == 1
        assert events[0].type.value == "done"
