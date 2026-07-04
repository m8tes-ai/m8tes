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
        f"{BASE}/settings/",
        json={"retention_mode": "standard"},
        status=200,
    )

    settings = Settings(_http()).get()

    assert isinstance(settings, AccountSettings)
    assert settings.retention_mode == "standard"


@responses.activate
def test_update_settings_without_changes_sends_empty_body():
    responses.add(
        responses.PATCH,
        f"{BASE}/settings/",
        json={"retention_mode": "standard"},
        status=200,
    )

    Settings(_http()).update()

    assert json.loads(responses.calls[0].request.body) == {}


@responses.activate
def test_get_settings_includes_sub_caps():
    responses.add(
        responses.GET,
        f"{BASE}/settings/",
        json={
            "per_end_user_run_limit": 25,
            "per_end_user_cost_limit_cents": 500,
        },
        status=200,
    )

    settings = Settings(_http()).get()

    assert settings.per_end_user_run_limit == 25
    assert settings.per_end_user_cost_limit_cents == 500


@responses.activate
def test_update_sub_caps_set_value():
    responses.add(
        responses.PATCH,
        f"{BASE}/settings/",
        json={
            "per_end_user_run_limit": 25,
            "per_end_user_cost_limit_cents": None,
        },
        status=200,
    )

    settings = Settings(_http()).update(per_end_user_run_limit=25)

    assert settings.per_end_user_run_limit == 25
    assert json.loads(responses.calls[0].request.body) == {"per_end_user_run_limit": 25}


@responses.activate
def test_update_retention_mode():
    responses.add(
        responses.PATCH,
        f"{BASE}/settings/",
        json={"retention_mode": "metadata_only"},
        status=200,
    )

    settings = Settings(_http()).update(retention_mode="metadata_only")

    assert settings.retention_mode == "metadata_only"
    assert json.loads(responses.calls[0].request.body) == {"retention_mode": "metadata_only"}


@responses.activate
def test_get_defaults_retention_standard():
    responses.add(
        responses.GET,
        f"{BASE}/settings/",
        json={},  # older backend without the field
        status=200,
    )

    assert Settings(_http()).get().retention_mode == "standard"


@responses.activate
def test_update_sub_cap_clear_sends_explicit_null():
    """Passing None clears the cap (sent as explicit null); omitting would not."""
    responses.add(
        responses.PATCH,
        f"{BASE}/settings/",
        json={
            "per_end_user_run_limit": None,
            "per_end_user_cost_limit_cents": None,
        },
        status=200,
    )

    Settings(_http()).update(per_end_user_run_limit=None)

    assert json.loads(responses.calls[0].request.body) == {"per_end_user_run_limit": None}


@responses.activate
def test_update_rate_per_minute():
    responses.add(
        responses.PATCH,
        f"{BASE}/settings/",
        json={"per_end_user_rate_per_minute": 10, "retention_mode": "standard"},
        status=200,
    )

    settings = Settings(_http()).update(per_end_user_rate_per_minute=10)

    assert settings.per_end_user_rate_per_minute == 10
    assert json.loads(responses.calls[0].request.body) == {"per_end_user_rate_per_minute": 10}
