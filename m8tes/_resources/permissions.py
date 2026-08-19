"""Permissions resource — pre-configure tool allow-lists for end-users."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._http import seg
from .._types import PermissionPolicy, SyncPage
from ._utils import _build_params

if TYPE_CHECKING:
    from .._http import HTTPClient


class Permissions:
    """client.permissions — manage tool permission policies."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def create(self, *, user_id: str | None = None, tool: str) -> PermissionPolicy:
        """Pre-approve a tool. Idempotent.

        Omit ``user_id`` to target the account-level scope — the scope your runs
        match when they carry no ``user_id``. Same convention as ``client.memories``.
        """
        resp = self._http.request("POST", "/permissions/", json={"user_id": user_id, "tool": tool})
        return PermissionPolicy.from_dict(resp.json())

    def list(
        self,
        *,
        user_id: str | None = None,
        limit: int = 20,
        starting_after: int | None = None,
    ) -> SyncPage[PermissionPolicy]:
        """List tool permission policies for one scope.

        Omit ``user_id`` to list the account-level scope.
        """
        params = _build_params(user_id=user_id, limit=limit, starting_after=starting_after)
        resp = self._http.request("GET", "/permissions/", params=params)
        body = resp.json()

        def _fetch_next(**kw: object) -> SyncPage[PermissionPolicy]:
            return self.list(user_id=user_id, limit=limit, **kw)  # type: ignore[arg-type]

        return SyncPage(
            data=[PermissionPolicy.from_dict(d) for d in body["data"]],
            has_more=body["has_more"],
            next_starting_after=body.get("next_starting_after"),
            _fetch_next=_fetch_next,
        )

    def delete(self, permission_id: int, *, user_id: str | None = None) -> None:
        """Remove a tool permission policy from exactly one scope.

        Omit ``user_id`` to delete an account-level policy. The scope must match the
        policy, so an end-user-scoped delete cannot remove an account-level one (404).
        """
        self._http.request(
            "DELETE",
            f"/permissions/{seg(permission_id)}",
            params=_build_params(user_id=user_id),
        )
