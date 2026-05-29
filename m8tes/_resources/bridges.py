"""Bridges resource — per-account BlueBubbles (Apple Messages) server connections.

A bridge holds a customer's BlueBubbles server URL + password + webhook secret.
Bind a teammate to a bridge via ``teammates.create/update(bridge_id=...)``. The
webhook secret is generated server-side and returned ONCE (on create / rotate_secret);
the password is write-only and never returned.
"""

from __future__ import annotations

import builtins
from typing import TYPE_CHECKING

from .._types import Bridge

if TYPE_CHECKING:
    from .._http import HTTPClient


class Bridges:
    """client.bridges — manage BlueBubbles bridges for the account."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def create(self, *, server_url: str, password: str, name: str = "BlueBubbles") -> Bridge:
        """Register a bridge. The returned ``bridge.webhook_secret`` is shown once —
        configure it as the BlueBubbles webhook secret immediately."""
        body = {"name": name, "server_url": server_url, "password": password}
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
        resp = self._http.request("PATCH", f"/bridges/{bridge_id}", json=body)
        return Bridge.from_dict(resp.json())

    def rotate_secret(self, bridge_id: int) -> Bridge:
        """Rotate the webhook secret. The old secret stays valid (grace) until the
        next rotation; the new ``bridge.webhook_secret`` is returned once."""
        resp = self._http.request("POST", f"/bridges/{bridge_id}/rotate-secret")
        return Bridge.from_dict(resp.json())

    def delete(self, bridge_id: int) -> None:
        """Delete a bridge. Fails (409) if teammates are still bound to it."""
        self._http.request("DELETE", f"/bridges/{bridge_id}")
