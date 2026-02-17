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

    def test_stream_break_mid_iteration(self):
        """If iter_lines raises mid-stream, response is still closed."""
        resp = MagicMock()
        resp.iter_lines.return_value = iter(
            [*_sse_frame({"type": "text-delta", "delta": "Hi"}), Exception("connection reset")]
        )
        resp.close = MagicMock()

        # iter_lines won't actually raise from iter() — simulate via side_effect
        original_lines = [
            f"data: {json.dumps({'type': 'text-delta', 'delta': 'Hi'})}",
            "",
        ]

        def _iter_lines(**_kwargs):
            yield from original_lines
            raise ConnectionError("stream cut")

        resp.iter_lines = _iter_lines
        stream = RunStream(resp)
        with stream:
            events = []
            try:
                for event in stream:
                    events.append(event)
            except ConnectionError:
                pass
        assert len(events) == 1
        resp.close.assert_called_once()

    def test_error_event_accumulated(self):
        """Error events should be captured by accumulator."""
        lines = _sse_frame({"type": "error", "error": "Something went wrong"})
        resp = self._make_response(lines)
        stream = RunStream(resp)
        list(stream)
        # Access accumulator directly to check error was captured
        assert stream._accumulator.has_errors()
        assert "Something went wrong" in stream._accumulator.get_errors()

    def test_empty_stream_yields_nothing(self):
        """Empty response yields no events."""
        resp = self._make_response([])
        stream = RunStream(resp)
        events = list(stream)
        assert events == []
        assert stream.text == ""

    def test_malformed_json_skipped(self):
        """Invalid JSON in SSE frame should be skipped, not raise."""
        lines = ["data: {invalid json", "", *_sse_frame({"type": "text-delta", "delta": "ok"})]
        resp = self._make_response(lines)
        stream = RunStream(resp)
        events = list(stream)
        # Only the valid event should come through
        assert len(events) == 1
        assert stream.text == "ok"
