"""Tests for Runs.poll() — polling helper for non-streaming runs."""

import pytest
import responses

from m8tes._http import HTTPClient
from m8tes._resources.runs import Runs
from m8tes._types import Run

BASE = "https://api.test/v2"


@pytest.fixture
def http():
    return HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)


class TestPoll:
    @responses.activate
    def test_already_completed(self, http):
        """Poll returns immediately if run is already in terminal state."""
        responses.add(
            responses.GET,
            f"{BASE}/runs/1",
            json={"id": 1, "status": "completed", "output": "Done"},
        )
        run = Runs(http).poll(1)
        assert isinstance(run, Run)
        assert run.status == "completed"
        assert run.output == "Done"
        assert len(responses.calls) == 1

    @responses.activate
    def test_already_failed(self, http):
        """Poll returns immediately if run has failed."""
        responses.add(
            responses.GET,
            f"{BASE}/runs/1",
            json={"id": 1, "status": "failed", "error": "Crash"},
        )
        run = Runs(http).poll(1)
        assert run.status == "failed"
        assert run.error == "Crash"

    @responses.activate
    def test_already_cancelled(self, http):
        """Poll returns immediately if run was cancelled."""
        responses.add(
            responses.GET,
            f"{BASE}/runs/1",
            json={"id": 1, "status": "cancelled"},
        )
        run = Runs(http).poll(1)
        assert run.status == "cancelled"

    @responses.activate
    def test_polls_until_complete(self, http):
        """Poll retries until terminal status."""
        # First two calls: still running
        responses.add(responses.GET, f"{BASE}/runs/1", json={"id": 1, "status": "running"})
        responses.add(responses.GET, f"{BASE}/runs/1", json={"id": 1, "status": "running"})
        # Third call: completed
        responses.add(
            responses.GET,
            f"{BASE}/runs/1",
            json={"id": 1, "status": "completed", "output": "Final"},
        )

        run = Runs(http).poll(1, interval=0.01, timeout=5.0)
        assert run.status == "completed"
        assert len(responses.calls) == 3

    @responses.activate
    def test_timeout_does_not_cancel_by_default(self, http):
        """Observing a run via poll must not cancel it when the local deadline fires."""
        responses.add(responses.GET, f"{BASE}/runs/1", json={"id": 1, "status": "running"})
        with pytest.raises(TimeoutError, match="did not complete"):
            Runs(http).poll(1, interval=0.01, timeout=0.05)
        assert not any(c.request.method == "POST" for c in responses.calls)

    @responses.activate
    def test_timeout(self, http):
        """Poll raises TimeoutError when deadline exceeded, and cancels when asked."""
        responses.add(responses.GET, f"{BASE}/runs/1", json={"id": 1, "status": "running"})
        responses.add(
            responses.POST,
            f"{BASE}/runs/1/cancel",
            json={"id": 1, "status": "cancelled"},
        )

        with pytest.raises(TimeoutError, match="did not complete"):
            Runs(http).poll(1, interval=0.01, timeout=0.05, cancel_on_timeout=True)
        cancel_calls = [
            c
            for c in responses.calls
            if c.request.method == "POST" and c.request.url.endswith("/cancel")
        ]
        assert cancel_calls

    @responses.activate
    def test_transient_error_retried(self, http):
        """Poll retries on transient 500 errors."""
        # First call: server error
        err = {"error": {"message": "oops"}}
        responses.add(responses.GET, f"{BASE}/runs/1", json=err, status=500)
        # Second call: completed
        responses.add(
            responses.GET,
            f"{BASE}/runs/1",
            json={"id": 1, "status": "completed", "output": "OK"},
        )
        run = Runs(http).poll(1, interval=0.01, timeout=5.0)
        assert run.status == "completed"
        assert len(responses.calls) == 2

    @responses.activate
    def test_transient_error_timeout(self, http):
        """Poll raises TimeoutError if server errors persist past deadline."""
        err = {"error": {"message": "oops"}}
        responses.add(responses.GET, f"{BASE}/runs/1", json=err, status=500)
        # Cancel may 404 if GET never returned a run — still best-effort.
        responses.add(
            responses.POST,
            f"{BASE}/runs/1/cancel",
            json={"error": {"message": "not found"}},
            status=404,
        )
        with pytest.raises(TimeoutError, match="did not complete"):
            Runs(http).poll(1, interval=0.01, timeout=0.05)


class TestTerminalStatuses:
    """`closed` is a terminal run status the SDK used to spin on.

    The server's TERMINAL_RUN_STATUSES (fastapi/app/models/run.py) has four
    members; both poll() and wait() hardcoded three, each with its own copy of
    the set. A closed run therefore never satisfied the exit condition and the
    caller waited out the full timeout on a run that had already finished.

    SDK-to-SDK comparison could never catch this — the TypeScript SDK shipped
    the identical three-element set. Only comparing against the server finds it,
    so that comparison is now a test rather than a habit.
    """

    def test_closed_is_terminal(self):
        from m8tes._resources.runs import TERMINAL_STATUSES

        assert "closed" in TERMINAL_STATUSES

    @responses.activate
    def test_poll_returns_a_closed_run_instead_of_timing_out(self, http):
        responses.add(responses.GET, f"{BASE}/runs/1", json={"id": 1, "status": "closed"})
        run = Runs(http).poll(1, interval=0.01, timeout=0.5)
        assert run.status == "closed"

    @responses.activate
    def test_wait_returns_a_closed_run_instead_of_timing_out(self, http):
        responses.add(responses.GET, f"{BASE}/runs/1", json={"id": 1, "status": "closed"})
        run = Runs(http).wait(1, interval=0.01, timeout=0.5)
        assert run.status == "closed"

    def test_matches_the_server_exactly(self):
        """Drift guard against fastapi/app/models/run.py, the source of truth.

        Mirrors packages/sdk/test/server-drift.test.ts so neither SDK can drift
        alone. Skips when the backend isn't in the tree (published-package CI).
        """
        from pathlib import Path
        import re

        from m8tes._resources.runs import TERMINAL_STATUSES

        here = Path(__file__).resolve()
        repo = next((p for p in here.parents if (p / "fastapi").is_dir()), None)
        if repo is None:
            pytest.skip("backend not present in this checkout")
        src = (repo / "fastapi" / "app" / "models" / "run.py").read_text()

        block = src.split("TERMINAL_RUN_STATUSES", 1)[1]
        block = block[: block.index(")")]
        members = re.findall(r"RunStatus\.(\w+)\.value", block)
        assert len(members) >= 3, "failed to parse TERMINAL_RUN_STATUSES from the backend"

        enum_src = src.split("class RunStatus", 1)[1]
        values = dict(re.findall(r"^\s{4}(\w+)\s*=\s*[\"'](\w+)[\"']", enum_src, re.M))
        expected = {values[m] for m in members}
        assert expected == TERMINAL_STATUSES, (
            f"SDK terminal statuses {sorted(TERMINAL_STATUSES)} != server {sorted(expected)}"
        )


# The run as the server reports it while a follow-up sits queued behind the turn that
# is still finishing: terminal, carrying the queued message's id, holding the PREVIOUS
# turn's output.
PRIOR_TURN = {
    "id": 1,
    "status": "completed",
    "output": "answer to the PREVIOUS message",
    "delivery": "queued",
    "queued_message_id": 77,
    "pending_queued_message_ids": [77],
}


class TestQueuedReplyDeadline:
    """A queued follow-up must never resolve to the previous turn's output.

    A reply sent to a run that is still working goes in as ``delivery="queued"``, and
    the server reports it against the run the caller is already watching. That run
    therefore reaches a terminal status carrying the queued message's id BEFORE the new
    turn starts. ``wait``'s polling loop knew to keep going; both of its deadline
    branches did not, and returned that stale run as the reply's result (Greptile P1,
    PR #1562).
    """

    @responses.activate
    def test_deadline_refuses_the_prior_turn(self, http):
        """No cancel: the first terminal-return site inside _resolve_deadline."""
        responses.add(responses.GET, f"{BASE}/runs/1", json=PRIOR_TURN)

        with pytest.raises(TimeoutError, match="did not complete"):
            Runs(http).wait(1, interval=0.01, timeout=0.05, await_queued_message_id=77)

    @responses.activate
    def test_deadline_refuses_the_prior_turn_after_cancelling(self, http):
        """cancel_on_timeout: the second terminal-return site, reachable from wait().

        wait() is public and takes both arguments, so the post-cancel re-read needs the
        same guard as the first read. Without it the stale run comes back here instead.
        """
        responses.add(responses.GET, f"{BASE}/runs/1", json=PRIOR_TURN)
        responses.add(responses.POST, f"{BASE}/runs/1/cancel", json={"id": 1, "status": "running"})
        responses.add(responses.GET, f"{BASE}/runs/1", json=PRIOR_TURN)

        with pytest.raises(TimeoutError, match="did not complete"):
            Runs(http).wait(
                1,
                interval=0.01,
                timeout=0.05,
                cancel_on_timeout=True,
                await_queued_message_id=77,
            )

    @responses.activate
    def test_deadline_still_returns_the_awaited_turn(self, http):
        """The guard is identity-scoped, not a blanket refusal of queued runs.

        Once the queued message is the one that ran, the server stops reporting it as
        queued. That run is the caller's result and must come back, or this fix would
        turn every queued reply into a timeout.
        """
        responses.add(
            responses.GET,
            f"{BASE}/runs/1",
            json={"id": 1, "status": "completed", "output": "answer to MY message"},
        )

        run = Runs(http).wait(1, interval=0.01, timeout=0.05, await_queued_message_id=77)
        assert run.output == "answer to MY message"

    @responses.activate
    def test_deadline_ignores_an_unrelated_queued_message(self, http):
        """A different queued id is somebody else's follow-up, not ours to wait on."""
        responses.add(
            responses.GET,
            f"{BASE}/runs/1",
            json={
                **PRIOR_TURN,
                "queued_message_id": 99,
                "pending_queued_message_ids": [99],
                "output": "not mine",
            },
        )

        run = Runs(http).wait(1, interval=0.01, timeout=0.05, await_queued_message_id=77)
        assert run.output == "not mine"

    @responses.activate
    def test_pending_list_refuses_when_not_fifo_head(self, http):
        """Our id may sit behind another pending message — still refuse the prior turn."""
        responses.add(
            responses.GET,
            f"{BASE}/runs/1",
            json={
                "id": 1,
                "status": "completed",
                "output": "PREVIOUS TERMINAL TURN",
                "delivery": "queued",
                "queued_message_id": 76,
                "pending_queued_message_ids": [76, 77],
            },
        )

        with pytest.raises(TimeoutError, match="did not complete"):
            Runs(http).wait(1, interval=0.01, timeout=0.05, await_queued_message_id=77)

    @responses.activate
    def test_get_shape_without_delivery_fields_still_refuses(self, http):
        """Greptile: GET used to omit delivery/queued_message_id entirely.

        The pending list alone must be enough — otherwise the guard is inert against
        the real server serializer.
        """
        responses.add(
            responses.GET,
            f"{BASE}/runs/1",
            json={
                "id": 1,
                "status": "completed",
                "output": "PREVIOUS TERMINAL TURN",
                "pending_queued_message_ids": [77],
            },
        )

        with pytest.raises(TimeoutError, match="did not complete"):
            Runs(http).wait(1, interval=0.01, timeout=0.05, await_queued_message_id=77)

    @responses.activate
    def test_poll_is_unaffected(self, http):
        """poll() has no queued concept and must keep returning any terminal run."""
        responses.add(responses.GET, f"{BASE}/runs/1", json=PRIOR_TURN)

        run = Runs(http).poll(1, interval=0.01, timeout=0.05)
        assert run.status == "completed"

    @responses.activate
    def test_reply_and_wait_times_out_instead_of_echoing(self, http):
        """End to end: the bug as a caller meets it."""
        responses.add(
            responses.POST,
            f"{BASE}/runs/1/reply",
            json={
                "id": 1,
                "status": "running",
                "delivery": "queued",
                "queued_message_id": 77,
                "pending_queued_message_ids": [77],
            },
        )
        responses.add(responses.GET, f"{BASE}/runs/1", json=PRIOR_TURN)

        with pytest.raises(TimeoutError, match="did not complete"):
            Runs(http).reply_and_wait(
                1, message="second question", poll_interval=0.01, poll_timeout=0.05
            )
