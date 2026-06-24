"""Tests for v2 auth resource helpers."""

import pytest
import responses

from m8tes._auth import signup, signup_and_wait
from m8tes._http import HTTPClient
from m8tes._resources.auth import Auth
from m8tes._types import SignupResult, Usage

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
def test_signup_passwordless_omits_password_and_sends_product():
    """Passwordless signup: no 'password' key in the body; product passes through."""
    import json as _json

    responses.add(
        responses.POST,
        f"{BASE}/signup",
        json={"api_key": "m8_x", "email": "a@b.co", "verification": "pending", "message": "m"},
        status=201,
    )
    result = signup(email="a@b.co", first_name="Sam", product="platform", base_url=BASE)
    assert result.api_key == "m8_x"
    body = _json.loads(responses.calls[0].request.body)
    assert "password" not in body  # passwordless — agent never sets a credential
    assert body["product"] == "platform"
    assert body["email"] == "a@b.co"
    assert body["first_name"] == "Sam"


@responses.activate
def test_signup_with_password_is_backward_compatible():
    """Positional password still works and is sent; product defaults to 'api'."""
    import json as _json

    responses.add(
        responses.POST,
        f"{BASE}/signup",
        json={"api_key": "m8_x", "email": "a@b.co", "message": "m"},
        status=200,
    )
    signup("a@b.co", "pw12345678", "a", base_url=BASE)
    body = _json.loads(responses.calls[0].request.body)
    assert body["password"] == "pw12345678"
    assert body["product"] == "api"


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


@responses.activate
def test_is_verified_true():
    responses.add(responses.GET, f"{BASE}/verify/status", json={"is_verified": True}, status=200)
    assert Auth(_http()).is_verified() is True


@responses.activate
def test_is_verified_false():
    responses.add(responses.GET, f"{BASE}/verify/status", json={"is_verified": False}, status=200)
    assert Auth(_http()).is_verified() is False


def test_signup_result_defaults_verification_pending():
    """Old backend omits the field → SignupResult.from_dict defaults to 'pending'."""
    result = SignupResult.from_dict({"api_key": "m8_x", "email": "a@b.co", "message": "m"})
    assert result.verification == "pending"


@responses.activate
def test_signup_and_wait_returns_immediately_when_verified():
    """If signup already reports verified, no /verify/status poll happens."""
    responses.add(
        responses.POST,
        f"{BASE}/signup",
        json={"api_key": "m8_x", "email": "a@b.co", "verification": "verified", "message": "m"},
        status=201,
    )
    result = signup_and_wait("a@b.co", "pw12345678", "a", base_url=BASE, timeout=30)
    assert result.verification == "verified"
    assert not any("/verify/status" in c.request.url for c in responses.calls)


@responses.activate
def test_signup_and_wait_returns_when_poll_flips_verified(monkeypatch):
    """Polls /verify/status until it flips true, then returns a result marked verified."""
    monkeypatch.setattr("time.sleep", lambda *_: None)
    responses.add(
        responses.POST,
        f"{BASE}/signup",
        json={"api_key": "m8_x", "email": "a@b.co", "verification": "pending", "message": "m"},
        status=201,
    )
    responses.add(responses.GET, f"{BASE}/verify/status", json={"is_verified": False}, status=200)
    responses.add(responses.GET, f"{BASE}/verify/status", json={"is_verified": True}, status=200)

    result = signup_and_wait(
        "a@b.co", "pw12345678", "a", base_url=BASE, timeout=30, poll_interval=0.5
    )

    assert result.api_key == "m8_x"
    assert result.verification == "verified"  # not the stale "pending"


@responses.activate
def test_signup_and_wait_times_out(monkeypatch):
    """Past the deadline with no activation → TimeoutError (account still exists)."""
    monkeypatch.setattr("time.sleep", lambda *_: None)
    # deadline=0+30; first while sees 0 (<30, polls once), second while sees 100 (>=30, exits).
    ticks = iter([0.0, 0.0, 100.0])
    monkeypatch.setattr("time.monotonic", lambda: next(ticks))
    responses.add(
        responses.POST,
        f"{BASE}/signup",
        json={"api_key": "m8_x", "email": "a@b.co", "verification": "pending", "message": "m"},
        status=201,
    )
    responses.add(responses.GET, f"{BASE}/verify/status", json={"is_verified": False}, status=200)

    with pytest.raises(TimeoutError):
        signup_and_wait("a@b.co", "pw12345678", "a", base_url=BASE, timeout=30)
