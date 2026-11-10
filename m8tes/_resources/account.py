"""Account resource — account-level operations for the current account."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from .._http import seg

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

    def revoke_sessions(self) -> dict[str, Any]:
        """Sign the account out everywhere: end every session, on every device.

        The revocation path for an account that has no password to change — an SSO-only
        account (Google sign-in) previously had to run a password RESET, which is treated
        as an account takeover and destroys every API key and webhook token with it.

        API keys, webhook tokens, and in-flight run-callback tokens are NOT revoked, so an
        agent mid-run keeps working. To revoke a key, use `client.keys.revoke(id)`.

        Session-authenticated only: an `m8_` key gets a 403, because a credential you paste
        into CI must not be able to sign the account owner out of their browser.
        """
        resp = self._http.request("POST", "/account/sessions/revoke")
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

    def add_reply_address(self, email: str) -> dict[str, Any]:
        """Add an address you write from that is not the one on your account.

        Your mail setup can send from another address (a send-as alias, or a mailbox whose
        provider rewrites the From), and a reply from it is refused as an unknown sender.
        We mail a confirmation link to ``email``, valid for 24 hours, and NOTHING is stored
        until its owner confirms on the page the link opens. Returns
        ``{"status": "confirmation_sent", "email": ...}``.

        Once confirmed, a reply from that address counts as you, but only on a mate's own
        reply address and only for a reply that names one of that mate's runs on your
        account: never on ``lead@``, a readable alias, or a fresh email that answers no run.
        An account holds up to 5. Raises 409 for your account address, an address already
        confirmed or a full list, 422 for something that is not a plain address, 429 after 10
        confirmation emails in a day.

        Session-authenticated only: an ``m8_`` key gets a 403, because this list decides who
        counts as the account owner.
        """
        resp = self._http.request("POST", "/account/reply-addresses", json={"email": email})
        return cast("dict[str, Any]", resp.json())

    def list_reply_addresses(self) -> dict[str, Any]:
        """The confirmed reply addresses: ``{"data": [{"id", "email", "verified_at"}], ...}``.

        Session-authenticated only: an ``m8_`` key gets a 403.
        """
        resp = self._http.request("GET", "/account/reply-addresses")
        return cast("dict[str, Any]", resp.json())

    def remove_reply_address(self, address_id: int) -> None:
        """Stop counting an address as you. Pass the ``id`` from ``list_reply_addresses``.

        A confirmation link sent before the removal can no longer bring it back. Raises 404
        for an address that is not on this account's list. Session-authenticated only.
        """
        self._http.request("DELETE", f"/account/reply-addresses/{seg(address_id)}")
