"""Permissions resource — pre-configure tool allow-lists for end-users."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._types import PermissionPolicy, SyncPage
from ._utils import _build_params

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
        params = _build_params(user_id=user_id, limit=limit, starting_after=starting_after)
        resp = self._http.request("GET", "/permissions", params=params)
        body = resp.json()

        def _fetch_next(**kw: object) -> SyncPage[PermissionPolicy]:
            return self.list(user_id=user_id, **kw)  # type: ignore[arg-type]

        return SyncPage(
            data=[PermissionPolicy.from_dict(d) for d in body["data"]],
            has_more=body["has_more"],
            _fetch_next=_fetch_next,
        )

    def delete(self, permission_id: int, *, user_id: str) -> None:
        """Remove a tool permission policy."""
        self._http.request("DELETE", f"/permissions/{permission_id}", params={"user_id": user_id})
