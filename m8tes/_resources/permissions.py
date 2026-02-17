"""Permissions resource — pre-configure tool allow-lists for end-users."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._types import PermissionPolicy

if TYPE_CHECKING:
    from .._http import HTTPClient


class Permissions:
    """client.permissions — manage tool permission policies."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def create(self, *, user_id: str, tool: str) -> PermissionPolicy:
        """Pre-approve a tool. Idempotent."""
        resp = self._http.request("POST", "/permissions", json={"user_id": user_id, "tool": tool})
        return PermissionPolicy.from_dict(resp.json())

    def list(self, *, user_id: str | None = None) -> list[PermissionPolicy]:
        """List tool permission policies."""
        params = {}
        if user_id is not None:
            params["user_id"] = user_id
        resp = self._http.request("GET", "/permissions", params=params)
        return [PermissionPolicy.from_dict(d) for d in resp.json()]

    def delete(self, permission_id: int) -> None:
        """Remove a tool permission policy."""
        self._http.request("DELETE", f"/permissions/{permission_id}")
