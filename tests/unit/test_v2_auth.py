"""Tests for v2 auth resource helpers."""

import responses

from m8tes._auth import signup
from m8tes._http import HTTPClient
from m8tes._resources.auth import Auth
from m8tes._types import Usage

BASE = "https://api.test/v2"


def _http() -> HTTPClient:
    return HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)


@responses.activate
def test_signup_uses_canonical_default_base_url(monkeypatch):
    """m8tes.signup() without base_url must hit the hosted API, not the marketing host."""
    monkeypatch.delenv("M8TES_BASE_URL", raising=False)
    responses.add(
        responses.POST,
        "https://api.m8tes.ai/api/v2/signup",
        json={"api_key": "m8_new", "email": "a@b.co", "message": "Account created."},
        status=200,
    )
    result = signup(email="a@b.co", password="pw12345678", first_name="a")
    assert result.api_key == "m8_new"


@responses.activate
def test_get_usage():
    responses.add(
        responses.GET,
        f"{BASE}/usage/",
        json={
            "plan": "free",
            "runs_used": 1,
            "runs_limit": 1,
            "cost_used": "0.25",
            "cost_limit": "5.00",
            "period_end": "2026-03-31T00:00:00Z",
            "subscription_status": None,
        },
        status=200,
    )

    usage = Auth(_http()).get_usage()

    assert isinstance(usage, Usage)
    assert usage.plan == "free"
    assert usage.runs_used == 1


@responses.activate
def test_resend_verify():
    responses.add(
        responses.POST,
        f"{BASE}/verify/resend",
        json={"message": "Verification email sent."},
        status=200,
    )

    message = Auth(_http()).resend_verify()

    assert message == "Verification email sent."
