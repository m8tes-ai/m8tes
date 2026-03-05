"""Apps resource — tools catalog and OAuth connections."""

from __future__ import annotations

import builtins
from typing import TYPE_CHECKING

from .._types import App, AppConnectionInitiation, AppConnectionResult, AppTriggerType, SyncPage
from ._utils import _build_params

if TYPE_CHECKING:
    from .._http import HTTPClient


class Apps:
    """client.apps — list tools, connect/disconnect integrations for end-users."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def list(
        self,
        *,
        user_id: str | None = None,
        limit: int = 20,
        starting_after: int | str | None = None,
    ) -> SyncPage[App]:
        """List available tools with connection status."""
        params = _build_params(limit=limit, starting_after=starting_after)
        if user_id:
            params["user_id"] = user_id
        resp = self._http.request("GET", "/apps", params=params)
        body = resp.json()

        def _fetch_next(**kw: object) -> SyncPage[App]:
            return self.list(user_id=user_id, **kw)  # type: ignore[arg-type]

        return SyncPage(
            data=[App.from_dict(d) for d in body["data"]],
            has_more=body["has_more"],
            _fetch_next=_fetch_next,
        )

    def is_connected(self, app_name: str, *, user_id: str | None = None) -> bool:
        """True if the app is connected for this account or end-user."""
        page = self.list(user_id=user_id)
        return any(a.name == app_name and a.connected for a in page.data)

    def connect_oauth(
        self,
        app_name: str,
        redirect_uri: str,
        *,
        user_id: str | None = None,
    ) -> AppConnectionInitiation:
        """Start an OAuth connection flow for an app."""
        payload: dict = {"redirect_uri": redirect_uri}
        if user_id:
            payload["user_id"] = user_id
        resp = self._http.request("POST", f"/apps/{app_name}/connect", json=payload)
        return AppConnectionInitiation.from_dict(resp.json())

    def connect_api_key(
        self,
        app_name: str,
        api_key: str,
        *,
        user_id: str | None = None,
    ) -> AppConnectionResult:
        """Connect an API key-based app immediately."""
        payload: dict = {"api_key": api_key}
        if user_id:
            payload["user_id"] = user_id
        resp = self._http.request("POST", f"/apps/{app_name}/connect/api-key", json=payload)
        return AppConnectionResult.from_dict(resp.json())

    def connect(
        self,
        app_name: str,
        redirect_uri: str | None = None,
        *,
        api_key: str | None = None,
        user_id: str | None = None,
    ) -> AppConnectionInitiation | AppConnectionResult:
        """Connect an app via OAuth or API key.

        OAuth apps (Gmail, Slack, etc.): pass redirect_uri= to start the flow.
            Returns authorization_url — redirect your user there to authorize.
            Call connect_complete() after the user is redirected back.

        API key apps (Gemini, OpenAI, Stripe, etc.): pass api_key=.
            Returns status confirming the connection immediately.
        """
        if api_key is not None:
            return self.connect_api_key(app_name, api_key, user_id=user_id)

        if redirect_uri is None:
            raise ValueError(
                "Pass redirect_uri= for OAuth apps or api_key= for API key apps. "
                "Check app.auth_type from apps.list() to know which to use."
            )
        return self.connect_oauth(app_name, redirect_uri, user_id=user_id)

    def connect_complete(
        self, app_name: str, connection_id: str, *, user_id: str | None = None
    ) -> AppConnectionResult:
        """Complete OAuth after user authorization. Returns status confirming connection."""
        payload: dict = {"connection_id": connection_id}
        if user_id:
            payload["user_id"] = user_id
        resp = self._http.request("POST", f"/apps/{app_name}/connect/complete", json=payload)
        return AppConnectionResult.from_dict(resp.json())

    def list_triggers(self, app_name: str) -> builtins.list[AppTriggerType]:
        """List available trigger types for an app (Composio discovery)."""
        resp = self._http.request("GET", f"/apps/{app_name}/triggers")
        body = resp.json()
        items = body["data"] if isinstance(body, dict) and "data" in body else body
        return [AppTriggerType.from_dict(d) for d in items]

    def disconnect(self, app_name: str, *, user_id: str | None = None) -> None:
        """Disconnect an app, optionally scoped to an end-user."""
        params = {}
        if user_id:
            params["user_id"] = user_id
        self._http.request("DELETE", f"/apps/{app_name}/connections", params=params)
