"""Execute the documented provider handoff through the real SDK transport."""

from pathlib import Path
import re

import pytest

from m8tes.testing import MockM8tes

SNIPPETS = (
    Path(__file__).resolve().parents[4]
    / "vite-frontend/src/constants/docs/shared-quickstart-snippets.ts"
)
pytestmark = pytest.mark.skipif(not SNIPPETS.exists(), reason="standalone SDK checkout")


def connect_snippet():
    match = re.search(
        r"export const PYTHON_XAI_CONNECT_SNIPPET = `(.*?)`;", SNIPPETS.read_text(), re.S
    )
    assert match, "The quickstart must include a complete provider handoff"
    return match.group(1)


@pytest.mark.parametrize("outcome", ["connected", "expired", "timeout"])
def test_documented_handoff_waits_for_connection(monkeypatch, capsys, outcome):
    client = MockM8tes()
    monkeypatch.setattr("m8tes.M8tes", lambda: client)
    clock = [0.0]
    monkeypatch.setattr("time.monotonic", lambda: clock[0])

    def advance_clock(seconds):
        clock[0] += seconds
        assert clock[0] <= 600, "Polling continued beyond the documented deadline"

    monkeypatch.setattr("time.sleep", advance_clock)
    authorization = {
        "provider": "xai",
        "state": "test-state",
        "status": "pending",
        "authorization_url": "https://example.com/authorize",
        "user_code": "TEST-CODE",
        "interval_seconds": 600 if outcome == "timeout" else 0,
    }
    client.mock.add("POST", "/model-connections/xai/authorizations", json=authorization)
    for status in ["pending"] if outcome == "timeout" else ["pending", outcome]:
        client.mock.add(
            "GET",
            "/model-connections/xai/authorizations/test-state",
            json={**authorization, "status": status},
        )

    if outcome == "connected":
        exec(connect_snippet(), {})
        assert len(client.mock.calls) == 3
        assert clock[0] == 2  # Zero intervals still wait one second per poll.
        assert "Connected" in capsys.readouterr().out
    else:
        expected_error = TimeoutError if outcome == "timeout" else RuntimeError
        with pytest.raises(expected_error):
            exec(connect_snippet(), {})
        assert "Connected" not in capsys.readouterr().out
        if outcome == "timeout":
            assert clock[0] == 600
            assert len(client.mock.calls) == 2

    assert all("/runs" not in call.path for call in client.mock.calls)


def test_handoff_shows_the_provider_url_and_code(monkeypatch, capsys):
    client = MockM8tes()
    monkeypatch.setattr("m8tes.M8tes", lambda: client)
    client.mock.add(
        "POST",
        "/model-connections/xai/authorizations",
        json={
            "provider": "xai",
            "state": "test-state",
            "status": "connected",
            "authorization_url": "https://example.com/authorize",
            "user_code": "TEST-CODE",
        },
    )
    exec(connect_snippet(), {})
    output = capsys.readouterr().out
    assert "https://example.com/authorize" in output
    assert "TEST-CODE" in output
