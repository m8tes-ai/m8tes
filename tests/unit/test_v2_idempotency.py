"""Idempotency-Key generation, POST retry, and replay handling.

The behaviour under test is why POST retry is safe at all. Before keys, `_http`
refused to retry POSTs: a create that timed out might already have started a
billable run, so re-sending risked charging twice. Sending a key on every
run-creating POST inverts that — the server replays the run it already made — so
these tests must pin BOTH halves: the key is always sent, AND a POST without one
is still never retried.
"""

import json
from unittest.mock import Mock

import pytest
import requests
import responses

from m8tes._exceptions import APIError, ConflictError
from m8tes._http import IDEMPOTENCY_HEADER, REPLAY_HEADER, HTTPClient
from m8tes._resources.runs import Runs, idempotency_headers
from m8tes._resources.tasks import Tasks

BASE = "https://api.m8tes.ai/v2"


@pytest.fixture
def http():
    return HTTPClient(api_key="m8_test123", base_url=BASE, timeout=10)


def _run_json(run_id=42, status="running"):
    return {"id": run_id, "status": status, "teammate_id": 1}


class TestKeyIsAlwaysSent:
    @responses.activate
    def test_runs_create_sends_a_key(self, http):
        responses.add(responses.POST, f"{BASE}/runs/", json=_run_json(), status=200)
        Runs(http).create(message="Hi", stream=False)
        assert responses.calls[0].request.headers[IDEMPOTENCY_HEADER]

    @responses.activate
    def test_runs_reply_sends_a_key(self, http):
        responses.add(responses.POST, f"{BASE}/runs/42/reply", json=_run_json(), status=200)
        Runs(http).reply(42, message="More", stream=False)
        assert responses.calls[0].request.headers[IDEMPOTENCY_HEADER]

    @responses.activate
    def test_tasks_run_sends_a_key(self, http):
        responses.add(responses.POST, f"{BASE}/tasks/7/runs", json=_run_json(), status=200)
        Tasks(http).run(7, stream=False)
        assert responses.calls[0].request.headers[IDEMPOTENCY_HEADER]

    @responses.activate
    def test_with_files_sends_a_key(self, http):
        responses.add(responses.POST, f"{BASE}/runs/with-files", json=_run_json(), status=200)
        Runs(http).create(message="Hi", stream=False, files=[("a.txt", b"data")])
        assert responses.calls[0].request.headers[IDEMPOTENCY_HEADER]

    @responses.activate
    def test_caller_key_is_used_verbatim(self, http):
        """A caller's own key is what survives a process restart — a job runner
        passing its job id must get THAT key on the wire, not a fresh uuid."""
        responses.add(responses.POST, f"{BASE}/runs/", json=_run_json(), status=200)
        Runs(http).create(message="Hi", stream=False, idempotency_key="job-1234")
        assert responses.calls[0].request.headers[IDEMPOTENCY_HEADER] == "job-1234"

    @responses.activate
    def test_two_calls_get_different_keys(self, http):
        """Auto-minting must never dedupe two DELIBERATE identical runs."""
        responses.add(responses.POST, f"{BASE}/runs/", json=_run_json(), status=200)
        responses.add(responses.POST, f"{BASE}/runs/", json=_run_json(43), status=200)
        Runs(http).create(message="Hi", stream=False)
        Runs(http).create(message="Hi", stream=False)
        assert (
            responses.calls[0].request.headers[IDEMPOTENCY_HEADER]
            != responses.calls[1].request.headers[IDEMPOTENCY_HEADER]
        )

    def test_generated_keys_are_unique(self):
        keys = {idempotency_headers(None)[IDEMPOTENCY_HEADER] for _ in range(200)}
        assert len(keys) == 200


class TestPostRetry:
    """A POST is retryable exactly when it carries a key — not before, not otherwise."""

    @responses.activate
    def test_post_with_a_key_is_retried_on_500(self, http):
        responses.add(responses.POST, f"{BASE}/runs/", json={}, status=500)
        responses.add(responses.POST, f"{BASE}/runs/", json=_run_json(), status=200)

        resp = http.request("POST", "/runs/", json={}, headers={IDEMPOTENCY_HEADER: "k"})

        assert resp.status_code == 200
        assert len(responses.calls) == 2

    @responses.activate
    def test_post_without_a_key_is_never_retried(self, http):
        """The pre-idempotency guarantee, still load-bearing: an unkeyed POST that
        may have started a billable run must fail rather than double-charge."""
        for _ in range(3):
            responses.add(responses.POST, f"{BASE}/runs/", json={"detail": "down"}, status=500)

        with pytest.raises(APIError):
            http.request("POST", "/runs/", json={})

        assert len(responses.calls) == 1

    @responses.activate
    def test_a_key_on_an_unsupported_route_does_not_enable_retry(self, http):
        """The header is not evidence the SERVER honours it.

        A caller who sets `Idempotency-Key` on an unrelated POST — or at client
        level, which the TS SDK explicitly supports — would otherwise make every
        POST retryable, including `tasks.create`, which has no server-side
        idempotency. A timed-out create would then be re-sent and duplicate the
        task. Found in review.
        """
        for _ in range(3):
            responses.add(responses.POST, f"{BASE}/tasks/", json={"detail": "down"}, status=500)

        with pytest.raises(APIError):
            http.request("POST", "/tasks/", json={}, headers={IDEMPOTENCY_HEADER: "k"})

        assert len(responses.calls) == 1

    @responses.activate
    def test_the_supported_routes_are_all_recognised(self, http):
        """Every route the server DOES make idempotent must still retry, or the
        gate above silently disables the whole feature."""
        from m8tes._http import _is_idempotent_route

        for path in (
            "/runs/",
            "/runs",
            "/runs/with-files",
            "/runs/42/reply",
            "/runs/42/reply/with-files",
            "/tasks/7/runs",
        ):
            assert _is_idempotent_route(path), path
        # False INCLUSION is the defect review found: suffix matching also accepted
        # `/foo/reply` and `/foo/runs`, and the low-level transport is public, so an
        # unsupported route could be retried on a server that ignores the key.
        for path in (
            "/tasks/",
            "/teammates/",
            "/runs/42/retry",
            "/runs/42/cancel",
            "/foo/reply",
            "/foo/runs",
            "/foo/reply/with-files",
            "/reruns",
            "/runs/abc/reply",
        ):
            assert not _is_idempotent_route(path), path

    @responses.activate
    def test_header_match_is_case_insensitive(self, http):
        """HTTP header names are case-insensitive, so a caller passing
        'idempotency-key' must get retries too — matching on the exact string
        would silently drop them back to no-retry."""
        responses.add(responses.POST, f"{BASE}/runs/", json={}, status=503)
        responses.add(responses.POST, f"{BASE}/runs/", json=_run_json(), status=200)

        resp = http.request("POST", "/runs/", json={}, headers={"idempotency-key": "k"})

        assert len(responses.calls) == 2
        assert resp.status_code == 200

    def test_keyed_post_is_retried_after_a_network_timeout(self, monkeypatch, http):
        """The case the feature exists for: no response at all. Without a key this
        raises immediately; with one, re-sending is safe because the server replays."""
        calls = []

        def _send(method, url, **kwargs):
            calls.append(kwargs.get("headers"))
            if len(calls) == 1:
                raise requests.Timeout("read timed out")
            resp = Mock(spec=requests.Response)
            resp.ok, resp.status_code = True, 200
            return resp

        monkeypatch.setattr(http._session, "request", _send)
        monkeypatch.setattr("m8tes._http.time.sleep", lambda _s: None)

        http.request("POST", "/runs/", json={}, headers={IDEMPOTENCY_HEADER: "k"})

        assert len(calls) == 2
        # Same key on the retry, or the server would create a second run.
        assert calls[0][IDEMPOTENCY_HEADER] == calls[1][IDEMPOTENCY_HEADER] == "k"

    def test_unkeyed_post_still_raises_on_a_network_timeout(self, monkeypatch, http):
        calls = []

        def _send(method, url, **kwargs):
            calls.append(1)
            raise requests.Timeout("read timed out")

        monkeypatch.setattr(http._session, "request", _send)
        monkeypatch.setattr("m8tes._http.time.sleep", lambda _s: None)

        with pytest.raises(APIError):
            http.request("POST", "/runs/", json={})

        assert len(calls) == 1


class TestStreamingReplay:
    """A replayed streaming create answers with JSON, not SSE."""

    @responses.activate
    def test_replay_joins_the_existing_runs_stream(self, http):
        """The caller asked for a stream and must still get one — transparently,
        without learning a retry happened."""
        responses.add(
            responses.POST,
            f"{BASE}/runs/",
            json=_run_json(42, "running"),
            status=200,
            headers={REPLAY_HEADER: "true"},
        )
        responses.add(
            responses.GET,
            f"{BASE}/runs/42/stream",
            body="data: {}\n\n",
            status=200,
            content_type="text/event-stream",
        )

        stream = Runs(http).create(message="Hi", stream=True)

        assert responses.calls[-1].request.url == f"{BASE}/runs/42/stream"
        stream._close()

    @responses.activate
    def test_a_non_replay_response_is_streamed_directly(self, http):
        """The normal path must not be routed through the rejoin — that would turn
        every first request into two."""
        responses.add(
            responses.POST,
            f"{BASE}/runs/",
            body="data: {}\n\n",
            status=200,
            content_type="text/event-stream",
        )

        stream = Runs(http).create(message="Hi", stream=True)

        assert len(responses.calls) == 1
        stream._close()

    @responses.activate
    def test_replay_of_a_finished_run_raises_instead_of_yielding_nothing(self, http):
        """An empty stream would read as 'the agent said nothing'. The error names
        the run and confirms a single charge, so the caller can recover."""
        responses.add(
            responses.POST,
            f"{BASE}/runs/",
            json=_run_json(42, "completed"),
            status=200,
            headers={REPLAY_HEADER: "true"},
        )

        with pytest.raises(ConflictError) as exc:
            Runs(http).create(message="Hi", stream=True)

        assert exc.value.code == "idempotent_replay_terminal"
        assert exc.value.details["run_id"] == 42
        assert "runs.get(42)" in exc.value.message

    @responses.activate
    def test_task_run_replay_joins_the_stream_too(self, http):
        """The twin path — tasks.run shares the create path's replay handling, so a
        fix on one side can never silently miss the other."""
        responses.add(
            responses.POST,
            f"{BASE}/tasks/7/runs",
            json=_run_json(99, "running"),
            status=200,
            headers={REPLAY_HEADER: "true"},
        )
        responses.add(
            responses.GET,
            f"{BASE}/runs/99/stream",
            body="data: {}\n\n",
            status=200,
            content_type="text/event-stream",
        )

        stream = Tasks(http).run(7, stream=True)

        assert responses.calls[-1].request.url == f"{BASE}/runs/99/stream"
        stream._close()


class TestNonStreamingReplay:
    @responses.activate
    def test_replay_returns_the_run(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/runs/",
            json=_run_json(42, "running"),
            status=200,
            headers={REPLAY_HEADER: "true"},
        )

        run = Runs(http).create(message="Hi", stream=False)

        assert run.id == 42

    @responses.activate
    def test_payload_is_unchanged_by_the_key(self, http):
        """The key rides in a header, never the body — a server that ignores the
        header must see byte-identical JSON to before."""
        responses.add(responses.POST, f"{BASE}/runs/", json=_run_json(), status=200)

        Runs(http).create(message="Hi", stream=False, idempotency_key="k")

        assert json.loads(responses.calls[0].request.body) == {"message": "Hi", "stream": False}
