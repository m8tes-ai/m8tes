"""Tests for v2 account settings resource."""

import json

import responses

from m8tes._http import HTTPClient
from m8tes._resources.settings import Settings
from m8tes._types import AccountSettings

BASE = "https://api.test/v2"


def _http() -> HTTPClient:
    return HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)


@responses.activate
def test_get_settings():
    responses.add(
        responses.GET,
        f"{BASE}/settings",
        json={"company_research": True},
        status=200,
    )

    settings = Settings(_http()).get()

    assert isinstance(settings, AccountSettings)
    assert settings.company_research is True


@responses.activate
def test_update_settings_with_value():
    responses.add(
        responses.PATCH,
        f"{BASE}/settings",
        json={"company_research": False},
        status=200,
    )

    settings = Settings(_http()).update(company_research=False)

    assert settings.company_research is False
    assert json.loads(responses.calls[0].request.body) == {"company_research": False}


@responses.activate
def test_update_settings_without_changes_sends_empty_body():
    responses.add(
        responses.PATCH,
        f"{BASE}/settings",
        json={"company_research": True},
        status=200,
    )

    Settings(_http()).update()

    assert json.loads(responses.calls[0].request.body) == {}
