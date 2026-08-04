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


@responses.activate
def test_create_sends_the_audience_and_reads_it_back():
    """A classification you can set but not read back is one you cannot trust."""
    responses.add(
        responses.POST,
        f"{BASE}/memories/",
        json={
            "id": 9,
            "user_id": None,
            "content": "We target DACH mid-market SaaS",
            "source": "api",
            "audience": "company",
            "created_at": "",
        },
        status=201,
    )
    http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
    m = Memories(http).create(content="We target DACH mid-market SaaS", audience="company")
    assert m.audience == "company"
    assert json.loads(responses.calls[0].request.body)["audience"] == "company"


@responses.activate
def test_omitting_the_audience_sends_no_key_at_all():
    """Sending an explicit null would ask an older server to reject a valid create."""
    responses.add(
        responses.POST,
        f"{BASE}/memories/",
        json={"id": 9, "user_id": None, "content": "A fact", "source": "api", "created_at": ""},
        status=201,
    )
    http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
    m = Memories(http).create(content="A fact")
    assert "audience" not in json.loads(responses.calls[0].request.body)
    assert m.audience is None, "a server that does not send it means unclassified, not an error"


@responses.activate
def test_update_can_correct_a_classification():
    responses.add(
        responses.PATCH,
        f"{BASE}/memories/9",
        json={
            "id": 9,
            "user_id": None,
            "content": "We target DACH mid-market SaaS",
            "source": "api",
            "audience": "company",
            "created_at": "",
        },
        status=200,
    )
    http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
    m = Memories(http).update(9, content="We target DACH mid-market SaaS", audience="company")
    assert m.audience == "company"
    assert json.loads(responses.calls[0].request.body) == {
        "content": "We target DACH mid-market SaaS",
        "audience": "company",
    }


@responses.activate
def test_a_content_only_update_does_not_send_an_audience():
    """Otherwise every content edit would erase the classification server-side."""
    responses.add(
        responses.PATCH,
        f"{BASE}/memories/9",
        json={
            "id": 9,
            "user_id": None,
            "content": "Edited",
            "source": "api",
            "audience": "personal",
            "created_at": "",
        },
        status=200,
    )
    http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
    m = Memories(http).update(9, content="Edited")
    assert json.loads(responses.calls[0].request.body) == {"content": "Edited"}
    assert m.audience == "personal", "the server kept it; the SDK must surface that"


@responses.activate
def test_update_can_send_an_audience_alone():
    """Round-tripping content just to fix a label is how a stale copy clobbers an edit."""
    responses.add(
        responses.PATCH,
        f"{BASE}/memories/9",
        json={
            "id": 9,
            "user_id": None,
            "content": "Untouched",
            "source": "api",
            "audience": "company",
            "created_at": "",
        },
        status=200,
    )
    http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
    m = Memories(http).update(9, audience="company")
    assert json.loads(responses.calls[0].request.body) == {"audience": "company"}
    assert m.audience == "company"


def test_update_with_neither_field_never_reaches_the_wire():
    """A no-op PATCH that reports success is worse than a refusal."""
    import pytest

    http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
    with pytest.raises(ValueError, match="content, audience, or both"):
        Memories(http).update(9)


@responses.activate
def test_scope_tells_a_mate_memory_from_an_unclassified_one():
    """Both report audience=None; only `scope` says which is which."""
    responses.add(
        responses.GET,
        f"{BASE}/memories/",
        json={
            "data": [
                {"id": 1, "content": "A Mate fact", "source": "agent", "scope": "teammate"},
                {"id": 2, "content": "An account fact", "source": "api", "scope": "account"},
            ],
            "has_more": False,
        },
        status=200,
    )
    http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
    page = Memories(http).list()
    assert [m.audience for m in page.data] == [None, None], "audience alone cannot tell them apart"
    assert [m.scope for m in page.data] == ["teammate", "account"]


@responses.activate
def test_scope_defaults_to_account_against_an_older_server():
    """A server that predates the field must not crash the client."""
    responses.add(
        responses.POST,
        f"{BASE}/memories/",
        json={"id": 1, "user_id": None, "content": "A fact", "source": "api", "created_at": ""},
        status=201,
    )
    http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
    assert Memories(http).create(content="A fact").scope == "account"
