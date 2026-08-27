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
            c for c in responses.calls
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
