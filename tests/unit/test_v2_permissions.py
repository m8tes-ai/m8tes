"""Tests for v2 SDK Permissions resource."""

import json

import responses

from m8tes._http import HTTPClient
from m8tes._resources.permissions import Permissions
from m8tes._types import PermissionPolicy, SyncPage

BASE = "https://api.test/v2"


@responses.activate
def test_create_permission():
    responses.add(
        responses.POST,
        f"{BASE}/permissions/",
        json={"id": 1, "user_id": "u_1", "tool_name": "gmail", "created_at": ""},
        status=201,
    )
    http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
    p = Permissions(http).create(user_id="u_1", tool="gmail")
    assert isinstance(p, PermissionPolicy)
    assert p.id == 1
    assert p.tool_name == "gmail"
    body = json.loads(responses.calls[0].request.body)
    assert body == {"user_id": "u_1", "tool": "gmail"}


@responses.activate
def test_list_permissions():
    responses.add(
        responses.GET,
        f"{BASE}/permissions/",
        json={
            "data": [
                {"id": 1, "user_id": "u_1", "tool_name": "gmail", "created_at": ""},
                {"id": 2, "user_id": "u_1", "tool_name": "slack", "created_at": ""},
            ],
            "has_more": False,
        },
    )
    http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
    result = Permissions(http).list(user_id="u_1")
    assert isinstance(result, SyncPage)
    assert len(result.data) == 2
    assert all(isinstance(p, PermissionPolicy) for p in result.data)
    assert result.has_more is False
    assert "user_id=u_1" in responses.calls[0].request.url


@responses.activate
def test_delete_permission():
    responses.add(responses.DELETE, f"{BASE}/permissions/1", status=204)
    http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
    Permissions(http).delete(1, user_id="u_1")
    assert responses.calls[0].request.method == "DELETE"
    assert "user_id=u_1" in responses.calls[0].request.url


@responses.activate
def test_create_account_level_permission_omits_no_field():
    """Omitting user_id targets the account-level scope.

    The wire body still carries `user_id: null` — the backend treats absent and null the
    same, and being explicit keeps the SDK's payload shape stable.
    """
    responses.add(
        responses.POST,
        f"{BASE}/permissions/",
        json={"id": 3, "user_id": None, "tool_name": "gmail", "created_at": ""},
        status=201,
    )
    http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
    p = Permissions(http).create(tool="gmail")
    assert p.user_id is None
    assert json.loads(responses.calls[0].request.body) == {"user_id": None, "tool": "gmail"}


@responses.activate
def test_list_account_level_permissions_sends_no_user_id():
    """No user_id param at all — sending `user_id=` would mean the empty-string scope."""
    responses.add(
        responses.GET,
        f"{BASE}/permissions/",
        json={
            "data": [{"id": 3, "user_id": None, "tool_name": "gmail", "created_at": ""}],
            "has_more": False,
        },
    )
    http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
    result = Permissions(http).list()
    assert [p.user_id for p in result.data] == [None]
    assert "user_id" not in responses.calls[0].request.url


@responses.activate
def test_delete_account_level_permission_sends_no_user_id():
    responses.add(responses.DELETE, f"{BASE}/permissions/3", status=204)
    http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
    Permissions(http).delete(3)
    assert "user_id" not in responses.calls[0].request.url
