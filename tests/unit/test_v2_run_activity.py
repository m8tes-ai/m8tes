"""Typed activity snapshots preserve recovery and scope without paginating history."""

import pytest
import responses

from m8tes import M8tes
from m8tes._exceptions import AuthenticationError

BASE = "https://api.test/v2"


@responses.activate
def test_activity_returns_typed_groups_and_recovery_metadata():
    responses.get(
        f"{BASE}/runs/activity",
        json={
            "data": [
                {
                    "agent_id": 42,
                    "runs": [
                        {
                            "id": 7,
                            "task_id": 9,
                            "status": "failed",
                            "created_at": "2026-09-07T10:00:00Z",
                            "last_activity_at": "2026-09-07T10:01:00Z",
                            "error_code": "deploy_interrupted",
                            "next_retry_at": "2026-09-07T10:02:00Z",
                            "auto_retry_count": 1,
                            "cancelled_at": None,
                            "needs_reply": True,
                        }
                    ],
                }
            ]
        },
    )
    with M8tes(api_key="m8_test", base_url=BASE) as client:
        result = client.runs.activity(user_id="alice")
    from m8tes import AgentRunActivity, RunActivity, RunActivitySnapshot

    assert isinstance(result, RunActivitySnapshot)
    assert isinstance(result.data[0], AgentRunActivity)
    assert isinstance(result.data[0].runs[0], RunActivity)
    assert result.data[0].agent_id == 42
    run = result.data[0].runs[0]
    assert (run.id, run.task_id, run.status, run.auto_retry_count) == (7, 9, "failed", 1)
    assert run.error_code == "deploy_interrupted"
    assert run.next_retry_at == "2026-09-07T10:02:00Z"
    assert run.cancelled_at is None
    assert run.needs_reply is True
    assert responses.calls[0].request.params == {"user_id": "alice"}
    assert len(responses.calls) == 1


@responses.activate
def test_activity_account_scope_is_unpaginated_and_empty_is_valid():
    responses.get(f"{BASE}/runs/activity", json={"data": []})
    with M8tes(api_key="m8_test", base_url=BASE) as client:
        assert client.runs.activity().data == []
    assert responses.calls[0].request.params == {}


@responses.activate
def test_activity_propagates_authentication_errors():
    responses.get(f"{BASE}/runs/activity", status=401, json={"error": {"message": "Invalid key"}})
    with M8tes(api_key="m8_test", base_url=BASE) as client, pytest.raises(AuthenticationError):
        client.runs.activity()
