"""Groups resource — recursive Teams for organizing and sharing agents."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from .._http import seg
from .._types import (
    Group,
    GroupInvite,
    GroupInvitePreview,
    GroupMember,
    GroupMemberRole,
    GroupShareResult,
    SyncPage,
)
from ._utils import _build_params

if TYPE_CHECKING:
    from .._http import HTTPClient

# Sentinel so update(display_order=None) can clear ordering (JSON null).
_UNSET: Any = object()


class Groups:
    """client.groups — recursive Team folders and role-based members.

    ``user_id`` scopes a group to one end-user; omit it for account-level
    groups. Assign agents via ``client.agents.update(..., group_id=...)``.
    Invitation membership is account-scoped. Viewer, runner, and editor roles
    apply through a group's subtree. ``share`` remains the independent legacy
    bulk visibility operation for Mates currently in a group.
    """

    def __init__(self, http: HTTPClient):
        self._http = http

    def create(
        self,
        *,
        name: str,
        user_id: str | None = None,
        display_order: int | None = None,
        parent_id: int | None = None,
    ) -> Group:
        """Create a Mate Group (creator is added as a member automatically)."""
        body: dict = {"name": name}
        if user_id is not None:
            body["user_id"] = user_id
        if display_order is not None:
            body["display_order"] = display_order
        if parent_id is not None:
            body["parent_id"] = parent_id
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
        parent_id: int | None = _UNSET,
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
        if parent_id is not _UNSET:
            body["parent_id"] = parent_id
        if not body:
            raise ValueError("Pass name, display_order, parent_id, or a combination of them.")
        resp = self._http.request(
            "PATCH",
            f"/groups/{seg(group_id)}",
            params=_build_params(user_id=user_id),
            json=body,
        )
        return Group.from_dict(resp.json())

    def delete(self, group_id: int, *, user_id: str | None = None) -> None:
        """Delete a Team subtree. Mates in it become ungrouped."""
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

    def members(self, group_id: int) -> SyncPage[GroupMember]:
        """List direct and inherited member roles. Managers only; account scope."""
        resp = self._http.request("GET", f"/groups/{seg(group_id)}/members")
        body = resp.json()
        return SyncPage(
            data=[GroupMember.from_dict(row) for row in body["data"]],
            has_more=body["has_more"],
        )

    list_members = members

    def update_member(self, group_id: int, member_id: int, *, role: GroupMemberRole) -> GroupMember:
        """Change a direct grant's role. Managers only; account scope."""
        resp = self._http.request(
            "PATCH",
            f"/groups/{seg(group_id)}/members/{seg(member_id)}",
            json={"role": role},
        )
        return GroupMember.from_dict(resp.json())

    def remove_member(self, group_id: int, member_id: int) -> None:
        """Remove a direct role grant. Managers or the member themself may call it."""
        self._http.request(
            "DELETE",
            f"/groups/{seg(group_id)}/members/{seg(member_id)}",
        )

    def invites(self, group_id: int) -> SyncPage[GroupInvite]:
        """List invitations for a Team. Managers only; account scope."""
        resp = self._http.request("GET", f"/groups/{seg(group_id)}/invites")
        body = resp.json()
        return SyncPage(
            data=[GroupInvite.from_dict(row) for row in body["data"]],
            has_more=body["has_more"],
        )

    list_invites = invites

    def invite(self, group_id: int, *, email: str, role: GroupMemberRole = "editor") -> GroupInvite:
        """Invite one email address with a role across a Team subtree."""
        resp = self._http.request(
            "POST",
            f"/groups/{seg(group_id)}/invites",
            json={"email": email, "role": role},
        )
        return GroupInvite.from_dict(resp.json())

    def cancel_invite(self, invite_id: int) -> None:
        """Revoke a pending Team invitation."""
        self._http.request("DELETE", f"/groups/invites/{seg(invite_id)}")

    def preview_invite(self, token: str) -> GroupInvitePreview:
        """Preview an invitation for the authenticated user."""
        resp = self._http.request("GET", f"/groups/invites/{seg(token)}")
        return GroupInvitePreview.from_dict(resp.json())

    def accept_invite(self, token: str) -> Group:
        """Accept an invitation after verified-email matching."""
        resp = self._http.request("POST", "/groups/invites/accept", json={"token": token})
        return Group.from_dict(resp.json())
