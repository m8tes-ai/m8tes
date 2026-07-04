"""Tests for v2 end-user resource helpers."""

import json

import responses

from m8tes._http import HTTPClient
from m8tes._resources.users import Users
from m8tes._types import EndUser, SyncPage

BASE = "https://api.test/v2"


def _http() -> HTTPClient:
    return HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)


@responses.activate
def test_create_user_minimal():
    responses.add(
        responses.POST,
        f"{BASE}/users/",
        json={"id": 1, "user_id": "cust_123", "created_at": "2026-02-28T00:00:00Z"},
        status=201,
    )

    user = Users(_http()).create(user_id="cust_123")

    assert isinstance(user, EndUser)
    assert user.user_id == "cust_123"
    assert json.loads(responses.calls[0].request.body) == {"user_id": "cust_123"}


@responses.activate
def test_create_user_all_fields():
    responses.add(
        responses.POST,
        f"{BASE}/users/",
        json={"id": 1, "user_id": "cust_123", "name": "Alice"},
        status=201,
    )

    Users(_http()).create(
        user_id="cust_123",
        name="Alice",
        email="alice@example.com",
        company="Acme",
        metadata={"tier": "pro"},
    )

    assert json.loads(responses.calls[0].request.body) == {
        "user_id": "cust_123",
        "name": "Alice",
        "email": "alice@example.com",
        "company": "Acme",
        "metadata": {"tier": "pro"},
    }


@responses.activate
def test_list_users():
    responses.add(
        responses.GET,
        f"{BASE}/users/",
        json={
            "data": [
                {"id": 1, "user_id": "cust_123"},
                {"id": 2, "user_id": "cust_456"},
            ],
            "has_more": False,
        },
        status=200,
    )

    page = Users(_http()).list(limit=2)

    assert isinstance(page, SyncPage)
    assert [user.user_id for user in page.data] == ["cust_123", "cust_456"]
    assert "limit=2" in responses.calls[0].request.url


@responses.activate
def test_list_users_auto_paging():
    responses.add(
        responses.GET,
        f"{BASE}/users/",
        json={"data": [{"id": 1, "user_id": "cust_123"}], "has_more": True},
        status=200,
    )
    responses.add(
        responses.GET,
        f"{BASE}/users/",
        json={"data": [{"id": 2, "user_id": "cust_456"}], "has_more": False},
        status=200,
    )

    page = Users(_http()).list(limit=1)
    users = list(page.auto_paging_iter())

    assert [user.user_id for user in users] == ["cust_123", "cust_456"]
    assert "starting_after=1" in responses.calls[1].request.url


@responses.activate
def test_get_user():
    responses.add(
        responses.GET,
        f"{BASE}/users/cust_123",
        json={"id": 1, "user_id": "cust_123", "name": "Alice"},
        status=200,
    )

    user = Users(_http()).get("cust_123")

    assert user.name == "Alice"


@responses.activate
def test_update_user_partial():
    responses.add(
        responses.PATCH,
        f"{BASE}/users/cust_123",
        json={"id": 1, "user_id": "cust_123", "company": "NewCo"},
        status=200,
    )

    user = Users(_http()).update("cust_123", company="NewCo")

    assert user.company == "NewCo"
    assert json.loads(responses.calls[0].request.body) == {"company": "NewCo"}


@responses.activate
def test_delete_user():
    responses.add(
        responses.DELETE,
        f"{BASE}/users/cust_123",
        status=204,
    )

    Users(_http()).delete("cust_123")

    assert responses.calls[0].request.method == "DELETE"


@responses.activate
def test_usage_rollup():
    from m8tes._types import EndUserUsage

    responses.add(
        responses.GET,
        f"{BASE}/usage/end-users",
        json={
            "data": [
                {
                    "id": 7,
                    "user_id": "cust_123",
                    "runs_used": 12,
                    "cost_used": "3.41",
                    "input_tokens": 182000,
                    "output_tokens": 24500,
                    "total_tokens": 206500,
                    "last_active_at": "2026-07-02T18:04:00Z",
                    "runs_limit": 50,
                    "cost_limit_cents": 2000,
                    "period_end": "2026-07-27T10:00:00Z",
                }
            ],
            "has_more": False,
        },
        status=200,
    )

    page = Users(_http()).usage()

    assert isinstance(page, SyncPage)
    row = page.data[0]
    assert isinstance(row, EndUserUsage)
    assert row.user_id == "cust_123"
    assert row.runs_used == 12
    assert row.total_tokens == 206500
    assert row.runs_limit == 50
    assert "user_id" not in (responses.calls[0].request.params or {})


@responses.activate
def test_usage_single_user_filter():
    responses.add(
        responses.GET,
        f"{BASE}/usage/end-users",
        json={"data": [], "has_more": False},
        status=200,
    )

    Users(_http()).usage("cust_123")

    assert responses.calls[0].request.params["user_id"] == "cust_123"
