"""Account resource — account-level operations for the current account."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from .._http import HTTPClient


class Account:
    """client.account — manage the current account."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def export(self) -> dict[str, Any]:
        """Export all of the current account's data (GDPR/CCPA right to access).

        Returns a JSON document of the account's agents, tasks, runs, documents,
        memories, and integration metadata. Secrets are never included.
        """
        resp = self._http.request("GET", "/account/export")
        return cast("dict[str, Any]", resp.json())

    def delete(self) -> dict[str, Any]:
        """Request deletion of the current account.

        Soft-delete: the account is deactivated immediately (every bearer credential
        revoked, billing canceled, automation stopped) and its data is erased
        after a grace period. Returns the API's status payload.
        """
        resp = self._http.request("DELETE", "/account")
        return cast("dict[str, Any]", resp.json())

    def change_password(self, current_password: str, new_password: str) -> dict[str, Any]:
        """Change the account password, proving you know the current one.

        Returns a fresh `access_token` + `refresh_token`: a password change revokes every
        existing session, including the caller's own. When the account has 2FA enabled it
        returns `{"mfa_required": True, "mfa_token": ...}` instead — the password change
        still applied, but the new session has to clear the second factor first.

        API keys, task/agent webhook tokens, and iMessage bridges are NOT revoked — only a
        password RESET is treated as an account takeover, because it proves control of the
        mailbox rather than of the password, and so must assume an attacker is present.
        Use this whenever the current password is known; it is the non-destructive path.

        Raises on a wrong `current_password` (401), and the attempt counts toward the same
        brute-force lockout as signing in.
        """
        resp = self._http.request(
            "POST",
            "/account/password",
            json={"current_password": current_password, "new_password": new_password},
        )
        return cast("dict[str, Any]", resp.json())
