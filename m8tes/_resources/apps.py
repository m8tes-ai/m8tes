"""Apps resource — tools catalog and OAuth connections."""

from __future__ import annotations

import builtins
from typing import TYPE_CHECKING

from .._http import seg
from .._types import (
    App,
    AppAccountSelection,
    AppConnectionDetails,
    AppConnectionInitiation,
    AppConnectionResult,
    AppExternalOAuthInitiation,
    AppProvisionResult,
    AppTool,
    AppTriggerType,
    GoogleAdsCustomers,
    GoogleSearchConsoleSites,
    SlackChannel,
    SlackClaimResult,
    SlackInstallInitiation,
    SlackMember,
    SlackWorkspaces,
    SyncPage,
)
from ._utils import _build_params

if TYPE_CHECKING:
    from .._http import HTTPClient


class Apps:
    """client.apps — list tools, connect/disconnect integrations for end-users."""

    def __init__(self, http: HTTPClient):
        self._http = http
        self.connections = AppConnections(http)

    def list(
        self,
        *,
        user_id: str | None = None,
        limit: int | None = None,
        starting_after: int | str | None = None,
    ) -> SyncPage[App]:
        """List available tools with connection status.

        NOT paginated: ``GET /apps/`` accepts only ``user_id`` and returns the whole
        catalog in one response (``has_more`` is always False).

        ``limit`` and ``starting_after`` are accepted and IGNORED, and are never
        sent. They used to be, and the API rejects both with a 422
        ``unknown_query_parameter`` — but only a NON-DEFAULT value ever got that
        far: ``_build_params`` drops ``limit`` at its old default of 20, so
        ``apps.list()`` and ``apps.list(limit=20)`` both worked while
        ``apps.list(limit=50)`` did not. Deleting them would therefore break
        calls that were succeeding, so they stay as no-ops until a major
        release. A value that would previously have failed warns; ``limit=20``
        stays silent, because that call was already correct.

        A SyncPage is still returned so every resource iterates the same way; it
        simply has no next page to fetch.
        """
        if (limit is not None and limit != 20) or starting_after is not None:
            import warnings

            warnings.warn(
                "apps.list() ignores limit/starting_after: GET /apps/ is not paginated "
                "and returns the whole catalog. Passing a non-default limit used to "
                "fail with a 422; these parameters will be removed in the next major.",
                DeprecationWarning,
                stacklevel=2,
            )
        params = _build_params(user_id=user_id)
        resp = self._http.request("GET", "/apps/", params=params)
        body = resp.json()
        return SyncPage(
            data=[App.from_dict(d) for d in body["data"]],
            has_more=body["has_more"],
            next_starting_after=body.get("next_starting_after"),
        )

    def is_connected(self, app_name: str, *, user_id: str | None = None) -> bool:
        """True if the app is connected for this account or end-user."""
        page = self.list(user_id=user_id)
        return any(app_name in (a.name, a.key) and a.connected for a in page.data)

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
        resp = self._http.request("POST", f"/apps/{seg(app_name)}/connect", json=payload)
        return AppConnectionInitiation.from_dict(resp.json())

    def connect_api_key(
        self,
        app_name: str,
        api_key: str,
        *,
        user_id: str | None = None,
        options: dict | None = None,
        agent_id: int | None = None,
    ) -> AppConnectionResult:
        """Connect an API key-based app immediately."""
        payload: dict = {"api_key": api_key}
        if user_id:
            payload["user_id"] = user_id
        if options is not None:
            payload["options"] = options
        if agent_id is not None:
            payload["agent_id"] = agent_id
        resp = self._http.request("POST", f"/apps/{seg(app_name)}/connect/api-key", json=payload)
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
        self,
        app_name: str,
        connection_id: str = "",
        *,
        claim_ticket: str | None = None,
        user_id: str | None = None,
        agent_id: int | None = None,
        code: str | None = None,
        redirect_uri: str | None = None,
    ) -> AppConnectionResult:
        """Complete OAuth after user authorization. Returns status confirming connection.

        Account-level connections (no ``user_id``) require ``claim_ticket``: the connect
        step must send the user to a m8tes URL, that page comes back carrying a
        ``composio_claim`` query parameter, and passing it here is what proves the caller is
        the account that started the flow. Without it a connect link could be forwarded and
        the recipient's provider account bound to whoever sent it. ``connection_id`` is
        ignored in that case — the ticket names the connection.

        **So an account-level connect finishes in a browser, not in your backend.** If you
        want a connect flow your own app drives end to end, use ``user_id`` — an end-user
        connection keeps your own ``redirect_uri``, takes no ticket, and passes
        ``connection_id`` as before. That is the lane built for connecting on behalf of
        someone else, and it is unchanged.
        """
        payload: dict = {}
        if connection_id:
            payload["connection_id"] = connection_id
        if claim_ticket:
            payload["claim_ticket"] = claim_ticket
        if user_id:
            payload["user_id"] = user_id
        if agent_id is not None:
            payload["agent_id"] = agent_id
        if code is not None:
            payload["code"] = code
        if redirect_uri is not None:
            payload["redirect_uri"] = redirect_uri
        resp = self._http.request("POST", f"/apps/{seg(app_name)}/connect/complete", json=payload)
        return AppConnectionResult.from_dict(resp.json())

    def list_customers(
        self, app_name: str, *, refresh: bool = False, user_id: str | None = None
    ) -> GoogleAdsCustomers:
        """List Google Ads customers for the exact account or end-user scope."""
        resp = self._http.request(
            "GET",
            f"/apps/{seg(app_name)}/customers",
            params=_build_params(refresh=refresh, user_id=user_id),
        )
        return GoogleAdsCustomers.from_dict(resp.json())

    def select_customer(
        self, app_name: str, customer_id: str, *, user_id: str | None = None
    ) -> AppAccountSelection:
        payload = {"account_id": customer_id}
        if user_id:
            payload["user_id"] = user_id
        resp = self._http.request("PUT", f"/apps/{seg(app_name)}/customer", json=payload)
        return AppAccountSelection.from_dict(resp.json())

    def list_sites(
        self, app_name: str, *, refresh: bool = False, user_id: str | None = None
    ) -> GoogleSearchConsoleSites:
        """List Search Console properties for the exact account or end-user scope."""
        resp = self._http.request(
            "GET",
            f"/apps/{seg(app_name)}/sites",
            params=_build_params(refresh=refresh, user_id=user_id),
        )
        return GoogleSearchConsoleSites.from_dict(resp.json())

    def select_site(
        self, app_name: str, site_url: str, *, user_id: str | None = None
    ) -> AppAccountSelection:
        payload = {"account_id": site_url}
        if user_id:
            payload["user_id"] = user_id
        resp = self._http.request("PUT", f"/apps/{seg(app_name)}/site", json=payload)
        return AppAccountSelection.from_dict(resp.json())

    def list_workspaces(self, app_name: str) -> SlackWorkspaces:
        resp = self._http.request("GET", f"/apps/{seg(app_name)}/workspaces")
        return SlackWorkspaces.from_dict(resp.json())

    def list_members(self, app_name: str) -> builtins.list[SlackMember]:
        resp = self._http.request("GET", f"/apps/{seg(app_name)}/members")
        return [SlackMember.from_dict(item) for item in resp.json().get("data", [])]

    def list_channels(self, app_name: str) -> builtins.list[SlackChannel]:
        resp = self._http.request("GET", f"/apps/{seg(app_name)}/channels")
        return [SlackChannel.from_dict(item) for item in resp.json().get("data", [])]

    def install(self, app_name: str, *, return_to: str | None = None) -> SlackInstallInitiation:
        payload = {"return_to": return_to} if return_to is not None else {}
        resp = self._http.request("POST", f"/apps/{seg(app_name)}/install", json=payload)
        return SlackInstallInitiation.from_dict(resp.json())

    def claim(self, app_name: str, *, ticket: str) -> SlackClaimResult:
        resp = self._http.request("POST", f"/apps/{seg(app_name)}/claim", json={"ticket": ticket})
        return SlackClaimResult.from_dict(resp.json())

    def disconnect_workspace(self, app_name: str, team_id: str) -> None:
        self._http.request("DELETE", f"/apps/{seg(app_name)}/workspaces/{seg(team_id)}")

    def connect_external_oauth(
        self, app_name: str, redirect_uri: str
    ) -> AppExternalOAuthInitiation:
        """Start external MCP OAuth for this account (no end-user scope).

        redirect_uri must be the m8tes /apps page. The consenting authenticated
        browser completes the connection there; arbitrary external callbacks fail.
        """
        response = self._http.request(
            "POST",
            f"/apps/{seg(app_name)}/connect/external-oauth",
            json={"redirect_uri": redirect_uri},
        )
        return AppExternalOAuthInitiation.from_dict(response.json())

    def complete_external_oauth(
        self,
        app_name: str,
        *,
        code: str,
        state: str,
        redirect_uri: str,
        agent_id: int | None = None,
    ) -> AppConnectionResult:
        """Verify account-bound OAuth state and store credentials."""
        payload: dict = {"code": code, "state": state, "redirect_uri": redirect_uri}
        if agent_id is not None:
            payload["agent_id"] = agent_id
        response = self._http.request(
            "POST", f"/apps/{seg(app_name)}/connect/external-oauth/complete", json=payload
        )
        return AppConnectionResult.from_dict(response.json())

    def provision(self, app_name: str, *, user_id: str | None = None) -> AppProvisionResult:
        """Provision a platform-managed resource (e.g. a Twilio phone number).

        For apps with auth_type='platform_provisioned'. Pass user_id= to provision a
        dedicated resource for a specific end-user (strictly isolated at run time);
        omit it for an account-level resource. Returns the provisioned details, e.g.
        ``result.phone_number``.
        """
        payload: dict = {}
        if user_id:
            payload["user_id"] = user_id
        resp = self._http.request("POST", f"/apps/{seg(app_name)}/provision", json=payload)
        return AppProvisionResult.from_dict(resp.json())

    def release(self, app_name: str, *, user_id: str | None = None) -> None:
        """Release a platform-provisioned resource (e.g. a Twilio number).

        Semantic alias of disconnect() for platform-provisioned apps: the resource is
        released back to the provider and the connection removed.
        """
        self.disconnect(app_name, user_id=user_id)

    def list_triggers(self, app_name: str) -> builtins.list[AppTriggerType]:
        """List available trigger types for an app (Composio discovery)."""
        resp = self._http.request("GET", f"/apps/{seg(app_name)}/triggers")
        body = resp.json()
        items = body["data"] if isinstance(body, dict) and "data" in body else body
        return [AppTriggerType.from_dict(d) for d in items]

    def list_tools(self, app_name: str) -> SyncPage[AppTool]:
        """List an app's tools with side-effect and approval metadata.

        ``read_only`` says whether the tool changes external state. ``approval_mode``
        says whether approval/plan mode asks: never, always, or only for some inputs.
        """
        resp = self._http.request("GET", f"/apps/{seg(app_name)}/tools")
        body = resp.json()
        return SyncPage(
            data=[AppTool.from_dict(d) for d in body["data"]],
            has_more=body["has_more"],
            next_starting_after=body.get("next_starting_after"),
        )

    def disconnect(self, app_name: str, *, user_id: str | None = None) -> None:
        """Disconnect an app, optionally scoped to an end-user."""
        params = {}
        if user_id:
            params["user_id"] = user_id
        self._http.request("DELETE", f"/apps/{seg(app_name)}/connections", params=params)


class AppConnections:
    """``client.apps.connections`` — inspect saved app connections."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def list(
        self, app_name: str | None = None, *, user_id: str | None = None
    ) -> SyncPage[AppConnectionDetails]:
        """List all connections, or one app, in the exact account or end-user scope."""
        if app_name is None:
            resp = self._http.request(
                "GET", "/apps/connections", params=_build_params(user_id=user_id)
            )
        else:
            resp = self._http.request(
                "GET", f"/apps/{seg(app_name)}/connections", params=_build_params(user_id=user_id)
            )
        body = resp.json()
        return SyncPage(
            data=[AppConnectionDetails.from_dict(item) for item in body["data"]],
            has_more=body["has_more"],
        )
