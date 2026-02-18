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
    def test_timeout(self, http):
        """Poll raises TimeoutError when deadline exceeded."""
        # Always return running
        responses.add(responses.GET, f"{BASE}/runs/1", json={"id": 1, "status": "running"})

        with pytest.raises(TimeoutError, match="did not complete"):
            Runs(http).poll(1, interval=0.01, timeout=0.05)

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
        with pytest.raises(TimeoutError, match="did not complete"):
            Runs(http).poll(1, interval=0.01, timeout=0.05)
