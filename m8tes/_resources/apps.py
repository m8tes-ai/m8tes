"""Apps resource — tools catalog and OAuth connections."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._types import App, AppConnection, SyncPage

if TYPE_CHECKING:
    from .._http import HTTPClient


class Apps:
    """client.apps — list tools, connect/disconnect integrations for end-users."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def list(self, *, user_id: str | None = None) -> SyncPage[App]:
        """List available tools with connection status."""
        params = {}
        if user_id:
            params["user_id"] = user_id
        resp = self._http.request("GET", "/apps", params=params)
        body = resp.json()
        return SyncPage(data=[App.from_dict(d) for d in body["data"]], has_more=body["has_more"])

    def connect(
        self, app_name: str, redirect_uri: str, *, user_id: str | None = None
    ) -> AppConnection:
        """Initiate OAuth connection. Returns authorization_url for the user."""
        payload: dict = {"redirect_uri": redirect_uri}
        if user_id:
            payload["user_id"] = user_id
        resp = self._http.request("POST", f"/apps/{app_name}/connect", json=payload)
        return AppConnection.from_dict(resp.json())

    def connect_complete(
        self, app_name: str, connection_id: str, *, user_id: str | None = None
    ) -> AppConnection:
        """Complete OAuth after user authorization."""
        payload: dict = {"connection_id": connection_id}
        if user_id:
            payload["user_id"] = user_id
        resp = self._http.request("POST", f"/apps/{app_name}/connect/complete", json=payload)
        return AppConnection.from_dict(resp.json())

    def disconnect(self, app_name: str, *, user_id: str | None = None) -> None:
        """Disconnect an app, optionally scoped to an end-user."""
        params = {}
        if user_id:
            params["user_id"] = user_id
        self._http.request("DELETE", f"/apps/{app_name}/connections", params=params)
