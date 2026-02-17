"""Webhooks resource — register, update, list, delete webhook endpoints and view deliveries."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._types import SyncPage, Webhook, WebhookDelivery

if TYPE_CHECKING:
    from .._http import HTTPClient


class Webhooks:
    """client.webhooks — manage webhook endpoints and delivery logs."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def create(self, *, url: str, events: list[str] | None = None) -> Webhook:
        """Register a webhook endpoint. Secret returned only on creation."""
        body: dict = {"url": url}
        if events is not None:
            body["events"] = events
        resp = self._http.request("POST", "/webhooks", json=body)
        return Webhook.from_dict(resp.json())

    def get(self, webhook_id: int) -> Webhook:
        """Get a single webhook endpoint (secret masked)."""
        resp = self._http.request("GET", f"/webhooks/{webhook_id}")
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

    def update(
        self,
        webhook_id: int,
        *,
        url: str | None = None,
        events: list[str] | None = None,
        active: bool | None = None,
        rotate_secret: bool = False,
    ) -> Webhook:
        """Update a webhook endpoint. Set rotate_secret=True to generate a new signing secret."""
        body: dict = {}
        if url is not None:
            body["url"] = url
        if events is not None:
            body["events"] = events
        if active is not None:
            body["active"] = active
        if rotate_secret:
            body["rotate_secret"] = True
        resp = self._http.request("PATCH", f"/webhooks/{webhook_id}", json=body)
        return Webhook.from_dict(resp.json())

    def list_deliveries(
        self,
        webhook_id: int,
        *,
        limit: int = 20,
        starting_after: int | None = None,
    ) -> SyncPage[WebhookDelivery]:
        """List delivery attempts for a webhook endpoint."""
        params: dict = {}
        if limit != 20:
            params["limit"] = limit
        if starting_after is not None:
            params["starting_after"] = starting_after
        resp = self._http.request("GET", f"/webhooks/{webhook_id}/deliveries", params=params)
        body = resp.json()
        return SyncPage(
            data=[WebhookDelivery.from_dict(d) for d in body["data"]],
            has_more=body["has_more"],
        )

    def delete(self, webhook_id: int) -> None:
        """Delete a webhook endpoint."""
        self._http.request("DELETE", f"/webhooks/{webhook_id}")
