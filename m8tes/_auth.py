"""Module-level auth helpers — signup and token exchange (no authentication required).

Use these before you have an API key. Once you have a key, use the M8tes client directly:
    from m8tes import M8tes
    client = M8tes(api_key="m8_...")
    usage = client.auth.get_usage()

These functions use raw requests (not HTTPClient) because no API key exists yet to
construct one. As a result they do not retry on transient 5xx — these calls are
short-lived and a simple retry by the caller is sufficient.
"""

from __future__ import annotations

import os

import requests

from ._http import _raise_for_status
from ._types import SignupResult, TokenResult

_DEFAULT_BASE_URL = "https://m8tes.ai/api/v2"


def signup(
    email: str,
    password: str,
    first_name: str,
    last_name: str = "",
    *,
    base_url: str | None = None,
) -> SignupResult:
    """Create an account and return an API key immediately.

    No authentication required. Verify your email before making runs.
    """
    url = (base_url or os.environ.get("M8TES_BASE_URL") or _DEFAULT_BASE_URL).rstrip("/")
    resp = requests.post(
        f"{url}/signup",
        json={
            "email": email,
            "password": password,
            "first_name": first_name,
            "last_name": last_name,
        },
        timeout=30,
    )
    if not resp.ok:
        _raise_for_status(resp, method="POST", path="/signup")
    return SignupResult.from_dict(resp.json())


def get_token(
    email: str,
    password: str,
    *,
    base_url: str | None = None,
) -> TokenResult:
    """Exchange email and password for a new API key.

    Generates a new key on every call — the previous key is immediately invalidated.
    """
    url = (base_url or os.environ.get("M8TES_BASE_URL") or _DEFAULT_BASE_URL).rstrip("/")
    resp = requests.post(
        f"{url}/token",
        json={"email": email, "password": password},
        timeout=30,
    )
    if not resp.ok:
        _raise_for_status(resp, method="POST", path="/token")
    return TokenResult.from_dict(resp.json())
