"""Teams resource — the organizations an account belongs to, their seats, and invites.

Backs `client.teams`. Invite and accept are gated by the Teams beta flag on the server
(404 while paused); listing, revoking, and removing a member always work for an
existing organization.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from .._http import seg
from .._types import SyncPage, TeamInvite, TeamInvitePreview, TeamMembership, TeamOrg

if TYPE_CHECKING:
    from .._http import HTTPClient


class Teams:
    """client.teams — organizations, members, invites."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def list(self) -> SyncPage[TeamOrg]:
        """Every organization the account belongs to, with members (and pending invites on
        seats that can manage the org)."""
        body = self._http.request("GET", "/teams/").json()
        # Not paginated server-side (an account belongs to a handful of orgs), so there is
        # no cursor fetcher to hand SyncPage.
        return SyncPage(
            data=[TeamOrg.from_dict(d) for d in body["data"]],
            has_more=body["has_more"],
            next_starting_after=body.get("next_starting_after"),
        )

    def invite(
        self, org_id: int, *, email: str, role: Literal["admin", "member"] = "member"
    ) -> TeamInvite:
        """Email an invite into `org_id` (owner/admin only). Re-sends if one is pending."""
        resp = self._http.request(
            "POST", f"/teams/{seg(org_id)}/invites", json={"email": email, "role": role}
        )
        return TeamInvite.from_dict(resp.json())

    def revoke_invite(self, invite_id: int) -> None:
        """Revoke a pending invite (owner/admin only)."""
        self._http.request("DELETE", f"/teams/invites/{seg(invite_id)}")

    def invite_preview(self, token: str) -> TeamInvitePreview:
        """What an invite token grants, before accepting it."""
        resp = self._http.request("GET", f"/teams/invites/{seg(token)}")
        return TeamInvitePreview.from_dict(resp.json())

    def accept_invite(self, token: str) -> TeamMembership:
        """Accept an invite; the caller's email must match the invited address."""
        resp = self._http.request("POST", "/teams/invites/accept", json={"token": token})
        return TeamMembership.from_dict(resp.json())

    def remove_member(self, org_id: int, member_id: int) -> None:
        """Remove a seat by the member's `user_id`. The owner seat is never removable."""
        self._http.request("DELETE", f"/teams/{seg(org_id)}/members/{seg(member_id)}")
