"""Tests for the v2 keys resource (rotate / revoke / info + named keys)."""

import responses

from m8tes._http import HTTPClient
from m8tes._resources.keys import Keys
from m8tes._types import ApiKeyCreated, ApiKeyInfo, ApiKeyRotated, NamedApiKey

BASE = "https://api.test/v2"


def _http() -> HTTPClient:
    return HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)


@responses.activate
def test_info():
    responses.add(
        responses.GET,
        f"{BASE}/keys/",
        json={"has_key": True, "prefix": "m8_abcd1234"},
        status=200,
    )
    info = Keys(_http()).info()
    assert isinstance(info, ApiKeyInfo)
    assert info.has_key is True
    assert info.prefix == "m8_abcd1234"


@responses.activate
def test_rotate():
    responses.add(
        responses.POST,
        f"{BASE}/keys/rotate",
        json={"api_key": "m8_newsecretkey", "prefix": "m8_newsecret"},
        status=200,
    )
    rotated = Keys(_http()).rotate()
    assert isinstance(rotated, ApiKeyRotated)
    assert rotated.api_key == "m8_newsecretkey"
    assert rotated.prefix == "m8_newsecret"


@responses.activate
def test_revoke():
    responses.add(
        responses.DELETE,
        f"{BASE}/keys/",
        json={"has_key": False, "prefix": None},
        status=200,
    )
    info = Keys(_http()).revoke()
    assert info.has_key is False
    assert info.prefix is None


# ── Named / multiple keys ────────────────────────────────────────────────


@responses.activate
def test_create_named():
    responses.add(
        responses.POST,
        f"{BASE}/keys/",
        json={
            "id": 7,
            "name": "production",
            "api_key": "m8_prodsecret",
            "prefix": "m8_prodsecr",
            "expires_at": "2027-01-01T00:00:00+00:00",
        },
        status=200,
    )
    key = Keys(_http()).create(name="production", expires_in_days=365)
    assert isinstance(key, ApiKeyCreated)
    assert key.id == 7
    assert key.name == "production"
    assert key.api_key == "m8_prodsecret"
    assert key.expires_at == "2027-01-01T00:00:00+00:00"
    body = responses.calls[0].request.body
    assert b'"expires_in_days": 365' in body
    assert b'"name": "production"' in body


@responses.activate
def test_create_named_no_expiry_omits_field():
    responses.add(
        responses.POST,
        f"{BASE}/keys/",
        json={"id": 1, "name": "ci", "api_key": "m8_x", "prefix": "m8_x", "expires_at": None},
        status=200,
    )
    key = Keys(_http()).create(name="ci")
    assert key.expires_at is None
    assert b"expires_in_days" not in responses.calls[0].request.body


@responses.activate
def test_list_named():
    responses.add(
        responses.GET,
        f"{BASE}/keys/all",
        json=[
            {
                "id": 2,
                "name": "staging",
                "prefix": "m8_stag1234",
                "created_at": "2026-01-01T00:00:00+00:00",
                "last_used_at": None,
                "expires_at": None,
                "active": True,
            }
        ],
        status=200,
    )
    keys = Keys(_http()).list()
    assert len(keys) == 1
    assert isinstance(keys[0], NamedApiKey)
    assert keys[0].id == 2
    assert keys[0].name == "staging"
    assert keys[0].active is True


@responses.activate
def test_rotate_named_by_id():
    responses.add(
        responses.POST,
        f"{BASE}/keys/9/rotate",
        json={
            "id": 9,
            "name": "prod",
            "api_key": "m8_rotated",
            "prefix": "m8_rotated1",
            "expires_at": None,
        },
        status=200,
    )
    key = Keys(_http()).rotate(9)
    assert isinstance(key, ApiKeyCreated)
    assert key.id == 9
    assert key.api_key == "m8_rotated"


@responses.activate
def test_revoke_named_by_id():
    responses.add(
        responses.DELETE,
        f"{BASE}/keys/9",
        json={
            "id": 9,
            "name": "prod",
            "prefix": "m8_prod1234",
            "created_at": "2026-01-01T00:00:00+00:00",
            "last_used_at": None,
            "expires_at": None,
            "active": False,
        },
        status=200,
    )
    key = Keys(_http()).revoke(9)
    assert isinstance(key, NamedApiKey)
    assert key.id == 9
    assert key.active is False
