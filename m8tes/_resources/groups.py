"""Groups resource — flat Mate Group folders for organizing agents."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from .._http import seg
from .._types import Group, GroupShareResult, SyncPage
from ._utils import _build_params

if TYPE_CHECKING:
    from .._http import HTTPClient

# Sentinel so update(display_order=None) can clear ordering (JSON null).
_UNSET: Any = object()


class Groups:
    """client.groups — create, list, update, delete, share Mate Groups.

    ``user_id`` scopes a group to one end-user; omit it for account-level
    groups. Assign agents via ``client.agents.update(..., group_id=...)``.
    ``share`` bulk-sets mate visibility for members (selection set — not a
    group ACL).
    """

    def __init__(self, http: HTTPClient):
        self._http = http

    def create(
        self,
        *,
        name: str,
        user_id: str | None = None,
        display_order: int | None = None,
    ) -> Group:
        """Create a Mate Group (creator is added as a member automatically)."""
        body: dict = {"name": name}
        if user_id is not None:
            body["user_id"] = user_id
        if display_order is not None:
            body["display_order"] = display_order
        resp = self._http.request("POST", "/groups", json=body)
        return Group.from_dict(resp.json())

    def list(self, *, user_id: str | None = None) -> SyncPage[Group]:
        """List Mate Groups in one end-user scope (account-level when omitted)."""
        resp = self._http.request("GET", "/groups", params=_build_params(user_id=user_id))
        body = resp.json()
        return SyncPage(
            data=[Group.from_dict(d) for d in body["data"]],
            has_more=body["has_more"],
        )

    def get(self, group_id: int, *, user_id: str | None = None) -> Group:
        """Fetch one Mate Group by id in the given scope."""
        resp = self._http.request(
            "GET",
            f"/groups/{seg(group_id)}",
            params=_build_params(user_id=user_id),
        )
        return Group.from_dict(resp.json())

    def update(
        self,
        group_id: int,
        *,
        name: str | None = None,
        display_order: int | None = _UNSET,
        user_id: str | None = None,
    ) -> Group:
        """Rename or reorder a Mate Group.

        Pass ``display_order=None`` to clear ordering (sends JSON null). Omit
        the argument to leave it unchanged.
        """
        body: dict = {}
        if name is not None:
            body["name"] = name
        if display_order is not _UNSET:
            body["display_order"] = display_order
        if not body:
            raise ValueError("Pass name, display_order, or both.")
        resp = self._http.request(
            "PATCH",
            f"/groups/{seg(group_id)}",
            params=_build_params(user_id=user_id),
            json=body,
        )
        return Group.from_dict(resp.json())

    def delete(self, group_id: int, *, user_id: str | None = None) -> None:
        """Delete a Mate Group. Agents in it become ungrouped."""
        self._http.request(
            "DELETE",
            f"/groups/{seg(group_id)}",
            params=_build_params(user_id=user_id),
        )

    def share(
        self,
        group_id: int,
        *,
        visibility: Literal["personal", "organization"],
        user_id: str | None = None,
    ) -> GroupShareResult:
        """Set visibility for mates currently in this group (selection set).

        ``organization`` shares those mates with the org; ``personal`` makes
        them private again. The group organizes which mates flip — it is not
        itself an access-control list.
        """
        resp = self._http.request(
            "POST",
            f"/groups/{seg(group_id)}/share",
            params=_build_params(user_id=user_id),
            json={"visibility": visibility},
        )
        return GroupShareResult.from_dict(resp.json())
