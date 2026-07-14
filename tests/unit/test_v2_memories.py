"""Tests for v2 SDK Memories resource."""

import json

import responses

from m8tes._http import HTTPClient
from m8tes._resources.memories import Memories
from m8tes._types import Memory, SyncPage

BASE = "https://api.test/v2"


@responses.activate
def test_create_memory():
    responses.add(
        responses.POST,
        f"{BASE}/memories/",
        json={
            "id": 1,
            "user_id": "u_1",
            "content": "Likes email",
            "source": "api",
            "created_at": "",
        },
        status=201,
    )
    http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
    m = Memories(http).create(user_id="u_1", content="Likes email")
    assert isinstance(m, Memory)
    assert m.id == 1
    assert m.content == "Likes email"
    body = json.loads(responses.calls[0].request.body)
    assert body == {"user_id": "u_1", "content": "Likes email"}


@responses.activate
def test_list_memories():
    responses.add(
        responses.GET,
        f"{BASE}/memories/",
        json={
            "data": [
                {"id": 1, "user_id": "u_1", "content": "Likes email"},
                {"id": 2, "user_id": "u_1", "content": "Timezone: PST"},
            ],
            "has_more": False,
        },
    )
    http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
    result = Memories(http).list(user_id="u_1")
    assert isinstance(result, SyncPage)
    assert len(result.data) == 2
    assert all(isinstance(m, Memory) for m in result.data)
    assert result.has_more is False
    assert "user_id=u_1" in responses.calls[0].request.url


@responses.activate
def test_delete_memory():
    responses.add(responses.DELETE, f"{BASE}/memories/1", status=204)
    http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
    Memories(http).delete(1, user_id="u_1")
    assert responses.calls[0].request.method == "DELETE"
    assert "user_id=u_1" in responses.calls[0].request.url


@responses.activate
def test_create_account_memory_omits_user_id():
    responses.add(
        responses.POST,
        f"{BASE}/memories/",
        json={"id": 3, "user_id": None, "content": "Brand voice: direct"},
        status=201,
    )
    http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
    m = Memories(http).create(content="Brand voice: direct")
    assert m.user_id is None
    body = json.loads(responses.calls[0].request.body)
    assert body == {"content": "Brand voice: direct"}


@responses.activate
def test_list_account_scope_omits_user_id():
    responses.add(responses.GET, f"{BASE}/memories/", json={"data": [], "has_more": False})
    http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
    Memories(http).list()
    assert "user_id" not in responses.calls[0].request.url


@responses.activate
def test_update_memory():
    responses.add(
        responses.PATCH,
        f"{BASE}/memories/7",
        json={"id": 7, "user_id": "u_1", "content": "Prefers Slack now"},
    )
    http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
    m = Memories(http).update(7, content="Prefers Slack now", user_id="u_1")
    assert m.content == "Prefers Slack now"
    assert "user_id=u_1" in responses.calls[0].request.url
    assert json.loads(responses.calls[0].request.body) == {"content": "Prefers Slack now"}
