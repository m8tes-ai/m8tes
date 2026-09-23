"""Wire contracts for per-repo coding secrets: what goes on the wire, and what never comes back."""

import json

import pytest
import responses

from m8tes import AgentRepoEnv, M8tes
from m8tes._exceptions import NotFoundError

BASE = "https://api.test/api/v2"
KEYS = {
    "repo_id": 9,
    "keys": [
        {"key": "DATABASE_URL", "updated_at": "2026-09-22T10:00:00"},
        {"key": "STRIPE_KEY", "updated_at": "2026-09-22T10:00:00"},
    ],
}


@responses.activate
def test_set_repo_env_puts_the_whole_map_and_returns_names_only():
    responses.put(f"{BASE}/agents/1/repos/9/env", json=KEYS)
    with M8tes(api_key="m8_test", base_url=BASE) as client:
        result = client.agents.set_repo_env(
            1, 9, env={"DATABASE_URL": "postgres://x", "STRIPE_KEY": "sk_test"}
        )
    assert json.loads(responses.calls[0].request.body) == {
        "env": {"DATABASE_URL": "postgres://x", "STRIPE_KEY": "sk_test"}
    }
    assert isinstance(result, AgentRepoEnv)
    assert result.repo_id == 9
    assert [k.key for k in result.keys] == ["DATABASE_URL", "STRIPE_KEY"]
    assert result.keys[0].updated_at == "2026-09-22T10:00:00"
    # Write-only: the dataclass has no field a value could land in.
    assert not hasattr(result.keys[0], "value")


@responses.activate
def test_get_repo_env_hits_the_env_route_with_user_scope():
    responses.get(f"{BASE}/agents/1/repos/9/env", json=KEYS)
    with M8tes(api_key="m8_test", base_url=BASE) as client:
        result = client.agents.get_repo_env(1, 9, user_id="tenant-1")
    assert responses.calls[0].request.url.endswith("/agents/1/repos/9/env?user_id=tenant-1")
    assert [k.key for k in result.keys] == ["DATABASE_URL", "STRIPE_KEY"]


@responses.activate
def test_delete_repo_env_key_escapes_the_key_segment():
    responses.delete(f"{BASE}/agents/1/repos/9/env/DATABASE_URL", status=204)
    with M8tes(api_key="m8_test", base_url=BASE) as client:
        assert client.agents.delete_repo_env_key(1, 9, "DATABASE_URL") is None
    assert responses.calls[0].request.method == "DELETE"


@responses.activate
def test_missing_key_raises_not_found():
    responses.delete(
        f"{BASE}/agents/1/repos/9/env/NOPE",
        status=404,
        json={"error": {"message": "NOPE is not set", "type": "not_found", "code": "nf"}},
    )
    with M8tes(api_key="m8_test", base_url=BASE) as client, pytest.raises(NotFoundError):
        client.agents.delete_repo_env_key(1, 9, "NOPE")


def test_from_dict_tolerates_an_empty_set():
    env = AgentRepoEnv.from_dict({"repo_id": 3, "keys": []})
    assert env.repo_id == 3
    assert env.keys == []
