"""Auth resource — account management for authenticated users."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._types import Usage

if TYPE_CHECKING:
    from .._http import HTTPClient


class Auth:
    """client.auth — check usage limits and resend email verification."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def get_usage(self) -> Usage:
        """Get current billing usage, run counts, and cost limits."""
        resp = self._http.request("GET", "/usage/")
        return Usage.from_dict(resp.json())

    def resend_verify(self) -> str:
        """Resend the email verification link. Returns a confirmation message."""
        resp = self._http.request("POST", "/verify/resend")
        return str(resp.json()["message"])

    def is_verified(self) -> bool:
        """Whether this account has verified its email.

        Poll after signup to learn when the user has clicked the one-tap activation
        link emailed to them (API accounts can't run until verified).
        """
        resp = self._http.request("GET", "/verify/status")
        return bool(resp.json()["is_verified"])
