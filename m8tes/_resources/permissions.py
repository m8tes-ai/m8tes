"""Permissions resource — pre-configure tool allow-lists for end-users."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._types import PermissionPolicy, SyncPage

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

    def list(
        self,
        *,
        user_id: str,
        limit: int = 20,
        starting_after: int | None = None,
    ) -> SyncPage[PermissionPolicy]:
        """List tool permission policies for an end-user."""
        params: dict = {"user_id": user_id}
        if limit != 20:
            params["limit"] = limit
        if starting_after is not None:
            params["starting_after"] = starting_after
        resp = self._http.request("GET", "/permissions", params=params)
        body = resp.json()
        return SyncPage(
            data=[PermissionPolicy.from_dict(d) for d in body["data"]], has_more=body["has_more"]
        )

    def delete(self, permission_id: int, *, user_id: str) -> None:
        """Remove a tool permission policy."""
        self._http.request("DELETE", f"/permissions/{permission_id}", params={"user_id": user_id})
