"""RunStream — wraps AISDKStreamParser for developer-friendly streaming.

A stream that stops is not a run that stopped. The API detaches a run from the HTTP
response that started it, so iteration ends quietly only when the run said it was
over (a terminal event) or is parked on a human gate, where the server closes the
stream on purpose. Anything else raises ``StreamInterruptedError``, which names the
run so the caller can wait for it or rejoin it.

The SDK does not rejoin by itself. ``runs.stream(run_id)`` replays the run from its
start, and text a caller has already written out cannot be taken back.
"""

from __future__ import annotations

from collections.abc import Generator, Iterator
from typing import TYPE_CHECKING

from ._exceptions import RunFailedError, StreamInterruptedError
from .streaming import (
    TERMINAL_FAILURE_TYPES,
    AISDKStreamParser,
    StreamAccumulator,
    StreamEvent,
    StreamEventType,
    TextDeltaEvent,
    TextStartEvent,
    ToolCallStartEvent,
    ToolResultEndEvent,
)

if TYPE_CHECKING:
    import requests

#: Names the run on every streaming POST, from the moment the run row exists. The
#: ``metadata`` frame carries the same id, but only once the sandbox has booted.
RUN_ID_HEADER = "X-Run-Id"

#: After one of these the run is over, so the stream is allowed to end.
_TERMINAL_TYPES = TERMINAL_FAILURE_TYPES | {
    StreamEventType.DONE,
    StreamEventType.CANCELLED,
    StreamEventType.ERROR,
}

#: A human gate. While a run is parked on one the server closes the stream.
_GATE_TYPES = frozenset({StreamEventType.AWAITING_APPROVAL, StreamEventType.PERMISSION_REQUEST})

#: Frames only an attempt that is working sends. After a terminal frame they mean the
#: run was started again on this same response: a run that fails on one model provider
#: is re-driven on the next (``provider_fallback.maybe_redrive_failed_run`` runs before
#: the server ends the response), and no frame announces it. The failed attempt has
#: usually sent its own ``done`` by then, so no terminal frame is safe to latch on.
_WORK_FRAMES = frozenset(
    {"sandbox-connecting", "message_start", "content_block_start", "content_block_delta"}
)


def _run_id_from(response: requests.Response) -> int | None:
    """The run id the response header names, or None when absent or not an id.

    Tolerates a stand-in with no headers at all: callers hand RunStream their own
    fakes in tests, and those have never needed any.
    """
    raw = getattr(response, "headers", {}).get(RUN_ID_HEADER)
    if not isinstance(raw, str) or not raw.isdigit():
        return None
    return int(raw) or None


def _is_model_output(event: StreamEvent) -> bool:
    """Is the model producing again? It only does once every tool call is settled."""
    if isinstance(event, TextStartEvent | TextDeltaEvent):
        return True
    # Only a block the model is opening now. A standalone `tool_use` frame carries the
    # resolved input of a call that was already made, possibly the gated one.
    return isinstance(event, ToolCallStartEvent) and event.raw.get("type") == "content_block_start"


class RunStream:
    """Iterable stream of run events. Use as context manager or iterate directly.

    Usage:
        with client.runs.create(message="Do X") as stream:
            for event in stream:
                print(event.type, event.raw)
        print(stream.text)  # full accumulated text

    Raises StreamInterruptedError if the stream stops before the run does. The run
    keeps working on the server: wait for it with ``client.runs.wait(exc.run_id)``.
    """

    def __init__(
        self,
        response: requests.Response,
        *,
        raise_on_error: bool = False,
        run_id: int | None = None,
    ):
        self._response = response
        self._accumulator = StreamAccumulator()
        self._closed = False
        # When True, a run that emits error events raises RunFailedError once you finish
        # iterating the stream — so a mid-run failure is never silently seen as empty
        # output. No effect until/unless you iterate (the accumulator only fills then).
        self._raise_on_error = raise_on_error
        # The run this stream belongs to, known before any frame: the run the caller
        # joined, or the one the response header names.
        self._known_run_id = run_id if run_id is not None else _run_id_from(response)
        self._ended = False
        # Set when this stream was opened by joining a queued reply's live turn:
        # wait helpers must await THIS inbound message, not the prior turn's end.
        self.await_queued_message_id: int | None = None
        # (request_id, tool_use_id) of a gate the run has not moved past, else None.
        self._open_gate: tuple[object, object] | None = None
        # Gates already answered. The server can deliver a gate frame twice, and a
        # late copy of an answered one must not read as a pause.
        self._answered_gates: set[object] = set()

    def _close(self) -> None:
        """Close the underlying response (idempotent)."""
        if not self._closed:
            self._closed = True
            self._response.close()

    def _track(self, event: StreamEvent) -> None:
        """Note whether the stream would be allowed to end here."""
        if event.type in _TERMINAL_TYPES:
            self._ended = True
        elif event.raw.get("type") in _WORK_FRAMES:
            # A terminal frame is the last word only until work follows it.
            self._ended = False
        if event.type in _GATE_TYPES:
            if event.raw.get("request_id") not in self._answered_gates:
                self._open_gate = (event.raw.get("request_id"), event.raw.get("tool_use_id"))
        elif event.type == StreamEventType.PERMISSION_RESOLVED:
            self._answered_gates.add(event.raw.get("request_id"))
            if self._open_gate is not None and event.raw.get("request_id") == self._open_gate[0]:
                self._open_gate = None
        elif self._open_gate is not None:
            _, tool_use_id = self._open_gate
            # Another tool finishing beside a gated one settles nothing, so only the
            # gated tool's own result counts.
            ran = (
                isinstance(event, ToolResultEndEvent)
                and tool_use_id is not None
                and event.tool_call_id == tool_use_id
            )
            if ran or _is_model_output(event):
                self._open_gate = None

    def __iter__(self) -> Iterator[StreamEvent]:
        try:
            try:
                for event in AISDKStreamParser.parse_stream(self._response):
                    self._accumulator.process(event)
                    self._track(event)
                    yield event
            except OSError as exc:
                # Every transport failure `requests` raises while reading a body is an
                # OSError: a reset, a premature end, a read timeout. Raw, it carried no
                # run id and no hint that the run carries on. Once a terminal event is
                # in, the run is over whatever the socket does next.
                if not self._ended:
                    raise StreamInterruptedError(
                        self.run_id, f"the connection was lost ({exc})"
                    ) from exc
            # The body ended cleanly. That is the end of the RUN only if the run said so.
            if not self._ended and self._open_gate is None:
                raise StreamInterruptedError(
                    self.run_id, "the connection closed before the run's final event"
                )
            if self._raise_on_error and self._accumulator.has_errors():
                errors = self._accumulator.get_errors()
                raise RunFailedError(f"Run failed: {'; '.join(errors)}", details={"errors": errors})
        finally:
            self._close()

    def __enter__(self) -> RunStream:
        return self

    def __exit__(self, *_: object) -> None:
        self._close()

    @property
    def text(self) -> str:
        """Full accumulated assistant text after iteration."""
        return self._accumulator.get_text()

    @property
    def output(self) -> str:
        """Alias for text."""
        return self.text

    @property
    def run_id(self) -> int | None:
        """Run ID.

        Known from the start for ``runs.stream()``, and as soon as the response opens
        for ``runs.create()``, ``runs.reply()`` and ``tasks.run()`` — before the
        metadata event, which waits for the sandbox to boot.
        """
        return self._accumulator.run_id or self._known_run_id

    @property
    def errors(self) -> list[str]:
        """Error messages emitted by the run during streaming.

        Check this after iterating (or pass raise_on_error=True) so a run that failed
        mid-stream isn't mistaken for a successful empty response.
        """
        return self._accumulator.get_errors()

    @property
    def has_errors(self) -> bool:
        """True if the run emitted any error event during streaming."""
        return self._accumulator.has_errors()

    def iter_text(self) -> Generator[str, None, None]:
        """Yield only text chunks — no event filtering needed.

        Usage:
            with client.runs.create(message="...") as stream:
                for chunk in stream.iter_text():
                    print(chunk, end="", flush=True)
            print(stream.run_id, stream.text)
        """
        for event in self:
            if isinstance(event, TextDeltaEvent):
                yield event.delta
