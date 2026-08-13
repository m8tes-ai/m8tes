"""Channels resource — white-label inbound channel identity (Slack D1).

``list()`` shows whether this account uses the global @m8tes Slack app or its own.
``install_links(user_id=...)`` mints an Add-to-Slack URL for an embed end-user.
``upsert_identity(...)`` stores the Slack app credentials (encrypted); bot name
and avatar are configured in Slack's dashboard, not here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._types import Channel, ChannelInstallLinks, SyncPage
from ._utils import _build_params

if TYPE_CHECKING:
    from .._http import HTTPClient


class Channels:
    """client.channels — Slack install links and white-label bot identity."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def list(self) -> SyncPage[Channel]:
        """List inbound channels for this account (Slack only in this release)."""
        resp = self._http.request("GET", "/channels")
        body = resp.json()
        return SyncPage(
            data=[Channel.from_dict(d) for d in body["data"]],
            has_more=body.get("has_more", False),
        )

    def install_links(self, user_id: str | None = None) -> ChannelInstallLinks:
        """Mint an Add-to-Slack URL.

        ``user_id`` is the embed end-user for strict-mode isolation only. It is
        not written onto the SlackInstall — workspace installs stay account-scoped.
        """
        params = _build_params(user_id=user_id)
        resp = self._http.request("GET", "/channels/install-links", params=params)
        return ChannelInstallLinks.from_dict(resp.json())

    def upsert_identity(
        self,
        *,
        channel: str,
        client_id: str,
        client_secret: str,
        signing_secret: str,
    ) -> Channel:
        """Store this account's Slack app credentials. Secrets are never returned."""
        resp = self._http.request(
            "PUT",
            "/channels/identities",
            json={
                "channel": channel,
                "client_id": client_id,
                "client_secret": client_secret,
                "signing_secret": signing_secret,
            },
        )
        return Channel.from_dict(resp.json())
