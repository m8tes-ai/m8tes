"""Tests for v2 auth resource helpers."""

import responses

from m8tes._http import HTTPClient
from m8tes._resources.auth import Auth
from m8tes._types import Usage

BASE = "https://api.test/v2"


def _http() -> HTTPClient:
    return HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)


@responses.activate
def test_get_usage():
    responses.add(
        responses.GET,
        f"{BASE}/usage",
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
