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

from ._http import DEFAULT_BASE_URL as _DEFAULT_BASE_URL, _raise_for_status
from ._types import SignupResult, TokenResult


def signup(
    email: str,
    password: str | None = None,
    first_name: str = "",
    last_name: str = "",
    *,
    product: str = "api",
    require_end_user_id: bool | None = None,
    base_url: str | None = None,
) -> SignupResult:
    """Create an account and return an API key immediately. No authentication required.

    Omit ``password`` for a passwordless, agent-created account: m8tes emails the person a
    link to set their own password and activate it, and the returned key is setup-only until
    they do (revoked on activation). This is the recommended flow when an agent onboards a
    human — the agent never holds a login credential. Pass a ``password`` to create a normal
    account. ``product``: "api" (developer/prepaid) or "platform" (team product). Either way,
    verify/activate before unrestricted runs (a small preview allowance runs first).

    ``require_end_user_id`` (strict multi-tenant mode): omit for the product default —
    ON for "api" signups (a forgotten ``user_id`` fails loudly instead of writing to the
    account scope), OFF for "platform". Pass ``False`` if you're building for yourself
    (single-tenant); changeable any time via ``client.settings.update()``.
    """
    if not first_name:
        raise ValueError("first_name is required")
    url = (base_url or os.environ.get("M8TES_BASE_URL") or _DEFAULT_BASE_URL).rstrip("/")
    payload: dict = {
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "product": product,
    }
    if password is not None:
        payload["password"] = password
    if require_end_user_id is not None:
        payload["require_end_user_id"] = require_end_user_id
    resp = requests.post(f"{url}/signup", json=payload, timeout=30)
    if not resp.ok:
        _raise_for_status(resp, method="POST", path="/signup")
    return SignupResult.from_dict(resp.json())


def signup_and_wait(
    email: str,
    password: str | None = None,
    first_name: str = "",
    last_name: str = "",
    *,
    product: str = "api",
    base_url: str | None = None,
    timeout: float = 300.0,
    poll_interval: float = 3.0,
) -> SignupResult:
    """Create an account, then block until the user activates it, and return the result.

    m8tes emails the user a one-tap activation link; this never receives that link, it
    only polls verification status (so the caller can't log in as the user). Use this
    when onboarding a user end to end: create the account, then wait for them to click.
    Omit ``password`` (recommended) so the user sets their own at activation; the returned
    key is setup-only until then and revoked once they activate.

    Raises TimeoutError if the user has not activated within `timeout` seconds. The account
    still exists when that happens; to survive longer waits, call signup() yourself and poll
    client.auth.is_verified() so you keep the API key. Requires a backend exposing
    GET /verify/status (raises RuntimeError against older backends).
    """
    import time

    from ._client import M8tes
    from ._exceptions import NotFoundError

    poll_interval = max(poll_interval, 0.5)  # guard against a busy-loop on poll_interval=0
    result = signup(email, password, first_name, last_name, product=product, base_url=base_url)
    if result.verification == "verified":
        return result

    deadline = time.monotonic() + timeout
    with M8tes(api_key=result.api_key, base_url=base_url) as client:  # close the HTTP session
        while time.monotonic() < deadline:
            try:
                verified = client.auth.is_verified()
            except NotFoundError as exc:
                raise RuntimeError(
                    "signup_and_wait requires a backend exposing GET /verify/status; "
                    f"the account for {result.email} was created but cannot be polled."
                ) from exc
            if verified:
                result.verification = "verified"  # reflect the observed state, not stale "pending"
                return result
            time.sleep(poll_interval)
    raise TimeoutError(
        f"Account {result.email} was not verified within {timeout:.0f}s. "
        "The user must click the one-tap activation link emailed to them."
    )


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
