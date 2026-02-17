"""Webhooks resource — register URLs for event delivery (coming soon)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._types import SyncPage, Webhook

if TYPE_CHECKING:
    from .._http import HTTPClient


class Webhooks:
    """client.webhooks — register, list, delete webhook endpoints."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def create(self, *, url: str, events: list[str] | None = None) -> Webhook:
        """Register a webhook endpoint. Secret returned only on creation."""
        body: dict = {"url": url}
        if events is not None:
            body["events"] = events
        resp = self._http.request("POST", "/webhooks", json=body)
        return Webhook.from_dict(resp.json())

    def list(
        self,
        *,
        limit: int = 20,
        starting_after: int | None = None,
    ) -> SyncPage[Webhook]:
        """List registered webhook endpoints (secrets masked)."""
        params: dict = {}
        if limit != 20:
            params["limit"] = limit
        if starting_after is not None:
            params["starting_after"] = starting_after
        resp = self._http.request("GET", "/webhooks", params=params)
        body = resp.json()
        return SyncPage(
            data=[Webhook.from_dict(d) for d in body["data"]], has_more=body["has_more"]
        )

    def delete(self, webhook_id: int) -> None:
        """Delete a webhook endpoint."""
        self._http.request("DELETE", f"/webhooks/{webhook_id}")
