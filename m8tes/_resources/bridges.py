"""Bridges resource — per-account BlueBubbles (Apple Messages) server connections.

A bridge holds a customer's BlueBubbles server URL + password + webhook secret.
Bind a teammate to a bridge via ``teammates.create/update(bridge_id=...)``. The
webhook secret is generated server-side and returned ONCE (on create / rotate_secret);
the password is write-only and never returned.
"""

from __future__ import annotations

import builtins
from typing import TYPE_CHECKING

from .._types import Bridge, HandleLink

if TYPE_CHECKING:
    from .._http import HTTPClient


class Bridges:
    """client.bridges — manage Apple Messages (BlueBubbles) connections for the account."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def provision(self) -> Bridge:
        """Connect m8tes-hosted iMessage in one call (no server to run yourself).

        Idempotent — returns the account's hosted bridge if it already has one. The result
        carries ``bridge.m8tes_handle`` (the number your users text) and ``bridge.link_code``
        (the code each user texts once to link their phone). Raises if the platform's central
        BlueBubbles server isn't configured (HTTP 503)."""
        resp = self._http.request("POST", "/bridges/provision")
        return Bridge.from_dict(resp.json())

    def provision_blooio(
        self, number: str, *, api_key: str | None = None, user_id: str | None = None
    ) -> Bridge:
        """Connect a managed Blooio iMessage number (a dedicated line) to your account.

        ``number`` is the dedicated Blooio number in E.164 (e.g. ``"+15551234567"``). Pass
        ``api_key`` to bring your own Blooio account (stored encrypted; omit to use the platform
        account), and ``user_id`` to bind the line to a specific end-user for multi-tenant
        isolation. Registers the inbound webhook with Blooio and returns the bridge, whose
        ``provider_number`` is the connected number. Raises if Blooio isn't configured (HTTP 503)
        or the number is invalid / already claimed / not on the account (HTTP 400)."""
        body: dict = {"number": number}
        if api_key is not None:
            body["api_key"] = api_key
        if user_id is not None:
            body["user_id"] = user_id
        resp = self._http.request("POST", "/bridges/provision-blooio", json=body)
        return Bridge.from_dict(resp.json())

    def regenerate_link_code(self, bridge_id: int, single_use: bool = False) -> Bridge:
        """Rotate a hosted bridge's link code (previously shared codes stop working).

        ``single_use=True`` issues a one-shot code consumed on the first phone that links (the
        safest way to hand a code to a single person on the shared m8tes number); the default
        keeps the code multi-use for team onboarding.
        """
        # Only send a body when opting in, so a bodiless request still works against older servers.
        json = {"single_use": True} if single_use else None
        resp = self._http.request("POST", f"/bridges/{bridge_id}/link-code", json=json)
        return Bridge.from_dict(resp.json())

    def list_handles(self, bridge_id: int) -> builtins.list[HandleLink]:
        """List the phone numbers/emails verified (linked) to a hosted bridge."""
        resp = self._http.request("GET", f"/bridges/{bridge_id}/handles")
        return [HandleLink.from_dict(d) for d in resp.json()["data"]]

    def remove_handle(self, bridge_id: int, handle_id: int) -> None:
        """Unlink a verified handle so it can no longer reach the account over iMessage."""
        self._http.request("DELETE", f"/bridges/{bridge_id}/handles/{handle_id}")

    def create(
        self,
        *,
        server_url: str,
        password: str,
        name: str = "BlueBubbles",
        owner_handle: str | None = None,
    ) -> Bridge:
        """Register a bridge. The returned ``bridge.webhook_secret`` is shown once —
        configure it as the BlueBubbles webhook secret immediately.

        Pass ``owner_handle`` (your own iMessage phone/email) to text the Company Agent
        (your inbound-default teammate) right away, without editing its allowlist."""
        body: dict = {"name": name, "server_url": server_url, "password": password}
        if owner_handle is not None:
            body["owner_handle"] = owner_handle
        resp = self._http.request("POST", "/bridges", json=body)
        return Bridge.from_dict(resp.json())

    def list(self) -> builtins.list[Bridge]:
        resp = self._http.request("GET", "/bridges")
        return [Bridge.from_dict(d) for d in resp.json()["data"]]

    def get(self, bridge_id: int) -> Bridge:
        resp = self._http.request("GET", f"/bridges/{bridge_id}")
        return Bridge.from_dict(resp.json())

    def update(
        self,
        bridge_id: int,
        *,
        name: str | None = None,
        server_url: str | None = None,
        password: str | None = None,
        status: str | None = None,
        owner_handle: str | None = None,
    ) -> Bridge:
        body: dict = {}
        if name is not None:
            body["name"] = name
        if server_url is not None:
            body["server_url"] = server_url
        if password is not None:
            body["password"] = password
        if status is not None:
            body["status"] = status
        if owner_handle is not None:
            body["owner_handle"] = owner_handle
        resp = self._http.request("PATCH", f"/bridges/{bridge_id}", json=body)
        return Bridge.from_dict(resp.json())

    def rotate_secret(self, bridge_id: int) -> Bridge:
        """Rotate the webhook secret. The old secret stays valid (grace) until the
        next rotation; the new ``bridge.webhook_secret`` is returned once."""
        resp = self._http.request("POST", f"/bridges/{bridge_id}/rotate-secret")
        return Bridge.from_dict(resp.json())

    def test(self, bridge_id: int) -> dict:
        """Check the bridge's BlueBubbles server is reachable and the password is accepted.

        No message is sent (it pings the server). Returns ``{"ok": bool, "detail": str|None}``
        — use it to debug a bridge that isn't receiving or sending messages."""
        resp = self._http.request("POST", f"/bridges/{bridge_id}/test")
        result: dict = resp.json()
        return result

    def delete(self, bridge_id: int) -> None:
        """Delete a bridge. Fails (409) if teammates are still bound to it."""
        self._http.request("DELETE", f"/bridges/{bridge_id}")
