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
        f"{BASE}/permissions",
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
        f"{BASE}/permissions",
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
