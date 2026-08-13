"""Channels resource — white-label inbound channel identity (Slack + GitHub).

``list()`` shows whether this account uses the global apps or its own.
``install_links(user_id=...)`` mints Add-to-Slack and GitHub App install URLs.
``upsert_identity(...)`` stores Slack or GitHub App credentials (encrypted);
bot/App name and avatar stay in Slack/GitHub dashboards, not here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._types import Channel, ChannelInstallLinks, SyncPage
from ._utils import _build_params

if TYPE_CHECKING:
    from .._http import HTTPClient


class Channels:
    """client.channels — Slack/GitHub install links and white-label app identity."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def list(self) -> SyncPage[Channel]:
        """List inbound channels for this account (Slack and GitHub)."""
        resp = self._http.request("GET", "/channels")
        body = resp.json()
        return SyncPage(
            data=[Channel.from_dict(d) for d in body["data"]],
            has_more=body.get("has_more", False),
        )

    def install_links(self, user_id: str | None = None) -> ChannelInstallLinks:
        """Mint Add-to-Slack and GitHub App install URLs.

        ``user_id`` is the embed end-user for strict-mode isolation only. It is
        not written onto SlackInstall or GitHubAppInstallation — installs stay
        account-scoped. Returns 503 if Slack is unavailable even when GitHub is
        configured.
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
        github_app_id: str | None = None,
        github_app_slug: str | None = None,
        github_private_key: str | None = None,
    ) -> Channel:
        """Store this account's Slack or GitHub App credentials. Secrets are never returned."""
        payload: dict[str, str] = {
            "channel": channel,
            "client_id": client_id,
            "client_secret": client_secret,
            "signing_secret": signing_secret,
        }
        if github_app_id is not None:
            payload["github_app_id"] = github_app_id
        if github_app_slug is not None:
            payload["github_app_slug"] = github_app_slug
        if github_private_key is not None:
            payload["github_private_key"] = github_private_key
        resp = self._http.request(
            "PUT",
            "/channels/identities",
            json=payload,
        )
        return Channel.from_dict(resp.json())
