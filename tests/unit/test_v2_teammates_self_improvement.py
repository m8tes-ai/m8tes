"""Tests for the SDK's enable_self_improvement plumbing on the Teammates resource."""

import json

import responses

from m8tes._http import HTTPClient
from m8tes._resources.teammates import Teammates
from m8tes._types import Teammate

BASE = "https://api.test/v2"


def _resp(**overrides):
    body = {"id": 1, "name": "Bot", "enable_self_improvement": True}
    body.update(overrides)
    return body


@responses.activate
def test_create_sends_flag_and_parses_response():
    responses.add(responses.POST, f"{BASE}/teammates/", json=_resp(), status=201)
    http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
    tm = Teammates(http).create(name="Bot", enable_self_improvement=True)
    assert isinstance(tm, Teammate)
    assert tm.enable_self_improvement is True
    body = json.loads(responses.calls[0].request.body)
    assert body["enable_self_improvement"] is True


@responses.activate
def test_create_omits_flag_when_not_set():
    responses.add(
        responses.POST,
        f"{BASE}/teammates/",
        json=_resp(enable_self_improvement=None),
        status=201,
    )
    http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
    Teammates(http).create(name="Bot")
    body = json.loads(responses.calls[0].request.body)
    assert "enable_self_improvement" not in body


@responses.activate
def test_update_sends_flag():
    responses.add(
        responses.PATCH,
        f"{BASE}/teammates/1",
        json=_resp(enable_self_improvement=False),
        status=200,
    )
    http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
    tm = Teammates(http).update(1, enable_self_improvement=False)
    assert tm.enable_self_improvement is False
    body = json.loads(responses.calls[0].request.body)
    assert body["enable_self_improvement"] is False
