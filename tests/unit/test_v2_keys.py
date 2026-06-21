"""Tests for the v2 keys resource (rotate / revoke / info)."""

import responses

from m8tes._http import HTTPClient
from m8tes._resources.keys import Keys
from m8tes._types import ApiKeyInfo, ApiKeyRotated

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
