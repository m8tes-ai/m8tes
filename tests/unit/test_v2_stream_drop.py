"""A stream that stops is not a run that stopped.

The API detaches a run from the HTTP response that started it, so a dropped
connection ends the STREAM and nothing else: the run keeps working, and
``GET /runs/{id}/stream`` exists to rejoin it. Before these tests the SDK read a
dropped stream two wrong ways:

- a body that ended without a terminal event made iteration finish normally, so
  ``stream.text`` was half an answer that looked whole;
- a connection that broke mid-body escaped as a raw ``requests`` exception with
  no run id and no hint that the run carries on.

The transport tests use a real server on a real socket. A mocked response can
only raise what the test tells it to; these pin what ``requests`` really does.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import socket
import threading
from unittest.mock import MagicMock

import pytest
import requests
import responses

from m8tes import StreamInterruptedError
from m8tes._exceptions import M8tesError, RunFailedError
from m8tes._http import REPLAY_HEADER, HTTPClient
from m8tes._resources.runs import Runs
from m8tes._resources.tasks import Tasks
from m8tes._streaming import RunStream
from m8tes.streaming import TERMINAL_FAILURE_TYPES

BASE = "https://api.m8tes.ai/v2"


def frame(payload: dict) -> bytes:
    return f"data: {json.dumps(payload)}\n\n".encode()


def metadata(run_id: int = 7) -> bytes:
    return frame({"type": "metadata", "run_id": run_id, "mode": "task"})


def text(delta: str) -> bytes:
    return frame(
        {"type": "content_block_delta", "id": "b1", "delta": {"type": "text_delta", "text": delta}}
    )


DONE = frame({"type": "done", "completion_state": "complete"})
KEEPALIVE = b": keepalive\n\n"


# --------------------------------------------------------------- real server --

Script = Callable[[BaseHTTPRequestHandler], None]


@pytest.fixture
def serve() -> Iterator[Callable[[Script], str]]:
    """Start a real HTTP server; ``script`` writes each response and decides how it ends."""
    servers: list[ThreadingHTTPServer] = []

    def start(script: Script) -> str:
        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_args: object) -> None:
                pass

            def _serve(self) -> None:
                self.rfile.read(int(self.headers.get("content-length") or 0))
                script(self)

            do_GET = do_POST = _serve  # noqa: N815

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        servers.append(server)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{server.server_address[1]}/api/v2"

    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


def start_sse(handler: BaseHTTPRequestHandler, *, chunked: bool = False, **headers: str) -> None:
    handler.send_response(200)
    handler.send_header("Content-Type", "text/event-stream")
    for name, value in headers.items():
        handler.send_header(name.replace("_", "-"), value)
    # Without chunking the body simply runs until the server closes the connection.
    handler.send_header(
        "Transfer-Encoding" if chunked else "Connection", "chunked" if chunked else "close"
    )
    handler.end_headers()


def write_chunk(handler: BaseHTTPRequestHandler, body: bytes) -> None:
    handler.wfile.write(f"{len(body):x}\r\n".encode() + body + b"\r\n")
    handler.wfile.flush()


def runs_at(base_url: str, timeout: float = 5) -> Runs:
    return Runs(HTTPClient(api_key="m8_test123", base_url=base_url, timeout=timeout))


class TestTransport:
    def test_a_body_that_closes_without_a_terminal_event_raises(self, serve):
        def script(handler):
            start_sse(handler)
            handler.wfile.write(metadata(7) + text("half an ans"))

        stream = runs_at(serve(script)).create(message="Hi")

        with pytest.raises(StreamInterruptedError) as exc:
            list(stream)

        assert exc.value.run_id == 7
        assert "may still be working" in str(exc.value)
        assert "client.runs.stream(7)" in str(exc.value)
        assert "client.runs.wait(7)" in str(exc.value)
        # What did arrive stays readable; it is never handed back as the answer.
        assert stream.text == "half an ans"

    def test_a_connection_that_dies_mid_body_raises_with_its_cause(self, serve):
        def script(handler):
            start_sse(handler, chunked=True)
            write_chunk(handler, metadata(7) + text("par"))
            handler.connection.shutdown(socket.SHUT_RDWR)  # no terminating chunk
            handler.close_connection = True

        stream = runs_at(serve(script)).create(message="Hi")

        with pytest.raises(StreamInterruptedError) as exc:
            list(stream)

        assert exc.value.run_id == 7
        assert "the connection was lost" in exc.value.reason
        assert isinstance(exc.value.__cause__, requests.exceptions.ChunkedEncodingError)
        assert stream.text == "par"

    def test_a_stream_that_goes_silent_past_the_read_timeout_raises(self, serve):
        release = threading.Event()

        def script(handler):
            start_sse(handler, X_Run_Id="7")
            handler.wfile.write(KEEPALIVE)
            handler.wfile.flush()
            release.wait(5)  # hold the socket open and say nothing

        stream = runs_at(serve(script), timeout=0.3).create(message="Hi")
        try:
            with pytest.raises(StreamInterruptedError) as exc:
                list(stream)
        finally:
            release.set()

        assert exc.value.run_id == 7
        assert isinstance(exc.value.__cause__, requests.exceptions.ConnectionError)

    def test_the_run_is_named_from_the_header_before_any_frame(self, serve):
        # `metadata` waits for the sandbox to boot. X-Run-Id does not.
        def script(handler):
            start_sse(handler, X_Run_Id="55")
            handler.wfile.write(KEEPALIVE)

        stream = runs_at(serve(script)).create(message="Hi")

        assert stream.run_id == 55
        with pytest.raises(StreamInterruptedError) as exc:
            list(stream)
        assert exc.value.run_id == 55

    def test_a_connection_that_breaks_after_the_terminal_event_is_not_an_interruption(self, serve):
        def script(handler):
            start_sse(handler, chunked=True)
            write_chunk(handler, metadata(7) + text("all of it") + DONE)
            handler.connection.shutdown(socket.SHUT_RDWR)  # never sends the last chunk
            handler.close_connection = True

        stream = runs_at(serve(script)).create(message="Hi")

        list(stream)

        assert stream.text == "all of it"


# ------------------------------------------------------------------- mocked --


def stream_of(
    *frames: bytes,
    raise_on_error: bool = False,
    run_id: int | None = None,
    headers: dict[str, str] | None = None,
) -> RunStream:
    """A RunStream over a body that ends cleanly after ``frames``."""
    lines = b"".join(frames).decode().split("\n")
    response = MagicMock()
    response.iter_lines.return_value = iter(lines)
    response.headers = headers or {}
    return RunStream(response, raise_on_error=raise_on_error, run_id=run_id)


GATE = frame(
    {
        "type": "awaiting_approval",
        "request_id": "r1",
        "tool_use_id": "toolu_gated",
        "tool_name": "Bash",
    }
)
QUESTION = frame(
    {
        "type": "awaiting_approval",
        "request_id": "q1",
        "tool_use_id": "toolu_ask",
        "tool_name": "AskUserQuestion",
    }
)


class TestEndsQuietlyOnlyWhenTheRunSaidSo:
    @pytest.mark.parametrize(
        "ending",
        [
            DONE,
            b"data: [DONE]\n\n",
            frame({"type": "error", "error": "model call failed"}),
            frame({"type": "cancelled", "run_id": 7}),
            frame({"type": "sdk_success", "subtype": "success", "is_error": True}),
            *(frame({"type": failure.value}) for failure in sorted(TERMINAL_FAILURE_TYPES)),
        ],
    )
    def test_a_terminal_event_ends_the_stream(self, ending):
        stream = stream_of(metadata(7), text("x"), ending)

        list(stream)

        assert stream.text == "x"

    @pytest.mark.parametrize("gate", [GATE, QUESTION])
    def test_a_run_parked_on_a_human_gate_ends_the_stream(self, gate):
        # The server closes the stream here on purpose: the run is waiting on a person.
        list(stream_of(metadata(7), gate))

    def test_a_live_permission_request_left_open_is_a_pause_too(self):
        list(stream_of(metadata(7), frame({"type": "permission_request", "request_id": "r1"})))

    def test_another_tools_result_does_not_close_the_gate(self):
        # Parallel tool calls: one tool is gated, another one finishes meanwhile.
        other = frame({"type": "tool_result", "tool_use_id": "toolu_other", "content": "ok"})

        list(stream_of(metadata(7), GATE, other))

    @pytest.mark.parametrize(
        "after_gate",
        [
            frame(
                {"type": "permission_resolved", "request_id": "r1", "resolved_status": "allowed"}
            ),
            frame({"type": "tool_result", "tool_use_id": "toolu_gated", "content": "ok"}),
            text("back at work"),
            frame({"type": "content_block_start", "id": "b2", "block_type": "text"}),
            frame(
                {
                    "type": "content_block_start",
                    "id": "t2",
                    "block_type": "tool_use",
                    "name": "Read",
                }
            ),
        ],
    )
    def test_a_gate_the_run_moved_past_is_not_a_pause(self, after_gate):
        # The gate was answered, or the model is producing again: the run is working,
        # so a stream that ends here was cut.
        with pytest.raises(StreamInterruptedError):
            list(stream_of(metadata(7), GATE, after_gate))

    def test_the_gated_calls_own_resolved_input_does_not_close_the_gate(self):
        # A standalone `tool_use` frame carries the input of a call already made.
        # It is not the model producing again, so the run is still parked.
        resolved_input = frame(
            {"type": "tool_use", "id": "toolu_gated", "name": "Bash", "input": {"command": "ls"}}
        )

        list(stream_of(metadata(7), GATE, resolved_input))

    def test_a_late_copy_of_an_answered_gate_is_not_a_pause(self):
        # The server can deliver a gate frame twice (broadcast, then DB reconcile).
        answered = frame(
            {"type": "permission_resolved", "request_id": "r1", "resolved_status": "allowed"}
        )

        with pytest.raises(StreamInterruptedError):
            list(stream_of(metadata(7), GATE, answered, GATE))

    def test_a_resolution_for_a_different_gate_leaves_this_one_open(self):
        stale = frame(
            {"type": "permission_resolved", "request_id": "r0", "resolved_status": "allowed"}
        )

        list(stream_of(metadata(7), GATE, stale))

    def test_an_empty_body_is_an_interruption(self):
        with pytest.raises(StreamInterruptedError) as exc:
            list(stream_of())

        assert exc.value.run_id is None
        assert "client.runs.list()" in str(exc.value)

    def test_a_caller_that_stops_reading_early_gets_no_error(self):
        stream = stream_of(metadata(7), text("a"), text("b"))

        for event in stream:
            if event.type.value == "text-delta":
                break

        assert stream.text == "a"

    def test_iter_text_raises_after_yielding_what_arrived(self):
        stream = stream_of(metadata(7), text("a"), text("b"))
        seen: list[str] = []

        with pytest.raises(StreamInterruptedError):
            for chunk in stream.iter_text():
                seen.append(chunk)

        assert seen == ["a", "b"]

    def test_the_interruption_wins_over_raise_on_error(self):
        # No terminal frame: whether the run failed is not known yet.
        stream = stream_of(
            metadata(7), frame({"type": "mcp_error", "error": "tool offline"}), raise_on_error=True
        )

        with pytest.raises(StreamInterruptedError):
            list(stream)

    def test_raise_on_error_still_reports_a_run_that_failed(self):
        stream = stream_of(
            metadata(7), frame({"type": "error", "error": "model call failed"}), raise_on_error=True
        )

        with pytest.raises(RunFailedError):
            list(stream)

    def test_the_response_is_closed_when_the_stream_is_interrupted(self):
        stream = stream_of(metadata(7))

        with pytest.raises(StreamInterruptedError):
            list(stream)

        stream._response.close.assert_called_once()

    def test_a_provider_retry_after_an_error_still_reports_a_later_cut(self):
        # A provider attempt can emit an error and then retry on the same run.
        # The ERROR frame must not permanently mark the stream ended, or a cut
        # during the retry looks like a finished run with only partial output.
        with pytest.raises(StreamInterruptedError) as exc:
            list(
                stream_of(
                    metadata(7),
                    frame({"type": "error", "error": "provider attempt failed"}),
                    text("retrying now"),
                )
            )

        assert exc.value.run_id == 7


ERROR = frame({"type": "error", "error": "usage limit reached"})
FAILED_RESULT = frame({"type": "sdk_success", "subtype": "success", "is_error": True})
FAILED_DONE = frame({"type": "done", "completion_state": "error", "stop_reason": "error"})
RUN_METRICS = frame({"type": "run_metrics", "total_tokens": 10})


class TestATerminalFrameIsNotAlwaysTheLastWord:
    """A run that fails on one model provider is started again on the next, on the same
    response, and no frame announces it (``maybe_redrive_failed_run`` runs before the
    server ends the response). The failed attempt has usually sent its own ``done`` by
    then: a provider limit arrives as an is_error result followed by ``done``. So no
    terminal frame can be latched on. A second attempt that was cut read as a run that
    had finished."""

    @pytest.mark.parametrize(
        "work",
        [
            frame({"type": "sandbox-connecting"}),
            frame({"type": "message_start", "message": {"id": "msg_2", "role": "assistant"}}),
            frame({"type": "content_block_start", "id": "b2", "block_type": "text"}),
            frame({"type": "content_block_start", "id": "k2", "block_type": "thinking"}),
            frame(
                {
                    "type": "content_block_start",
                    "id": "t2",
                    "block_type": "tool_use",
                    "name": "Read",
                }
            ),
            text("second attempt"),
        ],
    )
    @pytest.mark.parametrize(
        "ending",
        [
            (ERROR,),
            (ERROR, DONE),
            # What a provider limit really sends before the next provider takes over.
            (FAILED_RESULT, RUN_METRICS, FAILED_DONE),
        ],
    )
    def test_work_after_a_terminal_frame_means_the_run_is_going_again(self, ending, work):
        with pytest.raises(StreamInterruptedError) as exc:
            list(stream_of(metadata(7), *ending, work))

        assert exc.value.run_id == 7

    def test_a_second_attempt_that_finishes_ends_the_stream(self):
        cleared = frame({"type": "error_cleared", "reason": "provider_fallback"})
        stream = stream_of(
            metadata(7),
            FAILED_RESULT,
            FAILED_DONE,
            text("the answer"),
            DONE,
            cleared,
            raise_on_error=True,
        )

        list(stream)

        assert stream.text == "the answer"
        assert stream.errors == []

    def test_the_failed_attempts_own_done_does_not_retract_the_error(self):
        # A `done` follows a real failure too. Clearing on it would hide that failure.
        # The retraction is `error_cleared`, which this stream never sends.
        stream = stream_of(
            metadata(7),
            FAILED_RESULT,
            FAILED_DONE,
            text("the answer"),
            DONE,
            raise_on_error=True,
        )

        with pytest.raises(RunFailedError):
            list(stream)

    def test_a_trailing_snapshot_does_not_retract_the_error(self):
        stream = stream_of(
            metadata(7),
            ERROR,
            frame({"type": "message_snapshot", "message_id": None}),
            raise_on_error=True,
        )

        with pytest.raises(RunFailedError):
            list(stream)

    @pytest.mark.parametrize(
        "tail",
        [
            RUN_METRICS,
            frame({"type": "message_snapshot", "message_id": None}),
            frame({"type": "error_cleared", "reason": "provider_fallback"}),
            frame({"type": "replay_complete"}),
            KEEPALIVE,
        ],
    )
    def test_what_trails_a_failed_attempt_does_not_reopen_it(self, tail):
        # None of these is the run working again, so the run is still over.
        list(stream_of(metadata(7), ERROR, tail))

    def test_a_connection_lost_during_a_second_attempt_is_an_interruption(self, serve):
        def script(handler):
            start_sse(handler, chunked=True)
            write_chunk(handler, metadata(7) + FAILED_RESULT + FAILED_DONE + text("second att"))
            handler.connection.shutdown(socket.SHUT_RDWR)  # no terminating chunk
            handler.close_connection = True

        stream = runs_at(serve(script)).create(message="Hi")

        with pytest.raises(StreamInterruptedError) as exc:
            list(stream)

        assert exc.value.run_id == 7
        assert "the connection was lost" in exc.value.reason
        assert stream.text == "second att"


class TestTheErrorNamesTheRun:
    def test_it_is_an_m8tes_error_with_a_machine_code(self):
        with pytest.raises(M8tesError) as exc:
            list(stream_of(metadata(7)))

        assert isinstance(exc.value, StreamInterruptedError)
        assert exc.value.error_code == "stream_interrupted"
        assert exc.value.details == {
            "run_id": 7,
            "reason": "the connection closed before the run's final event",
        }

    def test_the_metadata_frame_wins_over_the_header(self):
        stream = stream_of(metadata(7), headers={"X-Run-Id": "999"})

        with pytest.raises(StreamInterruptedError) as exc:
            list(stream)

        assert exc.value.run_id == 7

    @pytest.mark.parametrize("value", ["not-a-number", "0", "-4", ""])
    def test_a_header_that_is_not_a_run_id_is_ignored(self, value):
        stream = stream_of(headers={"X-Run-Id": value})

        assert stream.run_id is None

    @responses.activate
    def test_a_join_knows_its_run_with_no_frame_at_all(self):
        responses.add(responses.GET, f"{BASE}/runs/42/stream", body=b"", status=200)
        stream = Runs(HTTPClient(api_key="m8_test123", base_url=BASE, timeout=5)).stream(42)

        assert stream.run_id == 42
        with pytest.raises(StreamInterruptedError) as exc:
            list(stream)
        assert exc.value.run_id == 42

    @responses.activate
    def test_a_reply_names_its_run_from_the_header(self):
        responses.add(
            responses.POST,
            f"{BASE}/runs/42/reply",
            body=KEEPALIVE,
            status=200,
            headers={"X-Run-Id": "42"},
        )
        stream = Runs(HTTPClient(api_key="m8_test123", base_url=BASE, timeout=5)).reply(
            42, message="More"
        )

        with pytest.raises(StreamInterruptedError) as exc:
            list(stream)
        assert exc.value.run_id == 42

    @responses.activate
    def test_a_reply_names_its_run_even_when_a_proxy_strips_the_header(self):
        responses.add(responses.POST, f"{BASE}/runs/42/reply", body=KEEPALIVE, status=200)
        stream = Runs(HTTPClient(api_key="m8_test123", base_url=BASE, timeout=5)).reply(
            42, message="More"
        )

        assert stream.run_id == 42

    @responses.activate
    def test_stream_text_raises_instead_of_ending_on_half_an_answer(self):
        responses.add(
            responses.POST,
            f"{BASE}/runs/",
            body=metadata(7) + text("half"),
            status=200,
            headers={"X-Run-Id": "7"},
        )
        chunks: list[str] = []

        with pytest.raises(StreamInterruptedError) as exc:
            for chunk in Runs(
                HTTPClient(api_key="m8_test123", base_url=BASE, timeout=5)
            ).stream_text(message="Hi"):
                chunks.append(chunk)

        assert chunks == ["half"]
        assert exc.value.run_id == 7

    @responses.activate
    def test_a_task_run_names_its_run_from_the_header(self):
        responses.add(
            responses.POST,
            f"{BASE}/tasks/3/runs",
            body=KEEPALIVE,
            status=200,
            headers={"X-Run-Id": "88"},
        )
        stream = Tasks(HTTPClient(api_key="m8_test123", base_url=BASE, timeout=5)).run(3)

        with pytest.raises(StreamInterruptedError) as exc:
            list(stream)
        assert exc.value.run_id == 88

    @responses.activate
    def test_the_join_an_idempotent_replay_makes_names_its_run(self):
        responses.add(
            responses.POST,
            f"{BASE}/runs/",
            json={"id": 77, "status": "running", "teammate_id": 1},
            status=200,
            headers={REPLAY_HEADER: "true"},
        )
        responses.add(responses.GET, f"{BASE}/runs/77/stream", body=b"", status=200)
        stream = Runs(HTTPClient(api_key="m8_test123", base_url=BASE, timeout=5)).create(
            message="Hi"
        )

        with pytest.raises(StreamInterruptedError) as exc:
            list(stream)
        assert exc.value.run_id == 77


def start_replay(handler: BaseHTTPRequestHandler, **headers: str) -> None:
    """Open an idempotent replay: JSON, not SSE, on a connection the server closes."""
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json")
    handler.send_header(REPLAY_HEADER, "true")
    for name, value in headers.items():
        handler.send_header(name.replace("_", "-"), value)
    handler.send_header("Connection", "close")
    handler.end_headers()


class TestAReplayThatIsCut:
    """An idempotent replay answers with the run as JSON. ``resp.json()`` threw that
    body away when it stalled or was cut, so the caller got a raw ``requests`` error
    that named no run, on a request that had already created one."""

    def test_a_replay_that_stalls_names_the_run_from_what_arrived(self, serve):
        release = threading.Event()

        def script(handler):
            start_replay(handler)
            handler.wfile.write(b'{"id": 42, "status": "runn')
            handler.wfile.flush()
            release.wait(5)  # and no more

        try:
            with pytest.raises(StreamInterruptedError) as exc:
                runs_at(serve(script), timeout=0.3).create(message="Hi")
        finally:
            release.set()

        assert exc.value.run_id == 42
        assert isinstance(exc.value.__cause__, requests.exceptions.ConnectionError)

    def test_a_replay_cut_off_mid_body_names_the_run(self, serve):
        def script(handler):
            start_replay(handler)
            handler.wfile.write(b'{"id": 42, "status": "runn')

        with pytest.raises(StreamInterruptedError) as exc:
            runs_at(serve(script)).create(message="Hi")

        assert exc.value.run_id == 42
        assert "client.runs.wait(42)" in str(exc.value)

    def test_a_replay_cut_short_of_its_declared_length_names_the_run(self, serve):
        # The API declares a length. A read sized past what arrived raises on the cut
        # and hands back nothing, which is why the head is read a byte at a time.
        def script(handler):
            handler.send_response(200)
            handler.send_header("Content-Type", "application/json")
            handler.send_header(REPLAY_HEADER, "true")
            handler.send_header("Content-Length", "500")
            handler.end_headers()
            handler.wfile.write(b'{"id": 42, "status": "runn')
            handler.close_connection = True

        with pytest.raises(StreamInterruptedError) as exc:
            runs_at(serve(script)).create(message="Hi")

        assert exc.value.run_id == 42

    @responses.activate
    def test_a_whole_replay_longer_than_its_head_is_read_to_the_end(self):
        # The join only happens if the whole body parsed, past the byte-wise head.
        responses.add(
            responses.POST,
            f"{BASE}/runs/",
            json={"id": 77, "status": "running", "teammate_id": 1, "output": "x" * 5000},
            status=200,
            headers={REPLAY_HEADER: "true"},
        )
        responses.add(responses.GET, f"{BASE}/runs/77/stream", body=DONE, status=200)
        stream = Runs(HTTPClient(api_key="m8_test123", base_url=BASE, timeout=5)).create(
            message="Hi"
        )

        list(stream)

        assert stream.run_id == 77

    def test_the_header_names_the_run_when_the_body_has_not(self, serve):
        def script(handler):
            start_replay(handler, X_Run_Id="42")
            handler.wfile.write(b"{")

        with pytest.raises(StreamInterruptedError) as exc:
            runs_at(serve(script)).create(message="Hi")

        assert exc.value.run_id == 42

    @pytest.mark.parametrize(
        "body",
        [
            b'{"id": 4',  # run 42, cut between the digits
            b'{"id": 42',  # the last digit may not have arrived
            b'{"task": {"id": 9}, "id": 42, "status": "runn',  # an id that is not the run's
        ],
    )
    def test_a_cut_that_cannot_name_the_run_names_none_rather_than_the_wrong_one(self, serve, body):
        def script(handler):
            start_replay(handler)
            handler.wfile.write(body)

        with pytest.raises(StreamInterruptedError) as exc:
            runs_at(serve(script)).create(message="Hi")

        assert exc.value.run_id is None
        assert "client.runs.list()" in str(exc.value)

    def test_a_reply_keeps_the_run_it_was_sent_to(self, serve):
        # The call already named run 42. A half-read `4` must not replace it.
        def script(handler):
            start_replay(handler)
            handler.wfile.write(b'{"id": 4')

        with pytest.raises(StreamInterruptedError) as exc:
            runs_at(serve(script)).reply(42, message="More")

        assert exc.value.run_id == 42

    def test_the_response_is_closed_when_a_replay_is_cut(self):
        resp = MagicMock()
        resp.headers = {REPLAY_HEADER: "true"}
        resp.iter_content.return_value = iter([b'{"id": 42, "sta'])

        with pytest.raises(StreamInterruptedError):
            Runs(MagicMock())._stream_or_replay(resp, raise_on_error=False)

        resp.close.assert_called_once()


class TestAQueuedReplyKeepsItsReceipt:
    """A reply to a run whose turn is still going is queued, and the stream handed back
    is that turn's. A wait after a drop then needs the queued message's id, or it
    returns the turn the reply is queued behind."""

    def _reply(self, **receipt) -> RunStream:
        responses.add(
            responses.POST,
            f"{BASE}/runs/42/reply",
            json={"id": 42, "status": "running", "teammate_id": 1, **receipt},
            status=200,
            headers={REPLAY_HEADER: "true"},
        )
        responses.add(responses.GET, f"{BASE}/runs/42/stream", body=DONE, status=200)
        return Runs(HTTPClient(api_key="m8_test123", base_url=BASE, timeout=5)).reply(
            42, message="More"
        )

    @responses.activate
    def test_the_stream_carries_the_queued_message_id(self):
        stream = self._reply(delivery="queued", queued_message_id=55)

        assert stream.await_queued_message_id == 55

    @responses.activate
    def test_a_replay_that_was_not_queued_carries_none(self):
        # A retried reply whose first attempt RESUMED the run: nothing is queued.
        stream = self._reply(delivery="resumed", queued_message_id=55)

        assert stream.await_queued_message_id is None

    def test_a_stream_that_was_never_queued_carries_none(self):
        assert stream_of(DONE).await_queued_message_id is None
