"""Account-level model provider OAuth subscription connections."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, cast

from .._http import seg
from .._types import ApplyPreferredModelResult, ModelAuthorization, ModelConnection, SyncPage

if TYPE_CHECKING:
    from .._http import HTTPClient

ModelConnectionProvider = Literal["claude", "openai", "xai", "gemini"]
# What `apply_default` accepts: a connected provider, or "m8tes" (Teams) to skip your plans.
ModelDefaultChoice = Literal["claude", "openai", "xai", "gemini", "m8tes"]
# What `get_default` returns. "auto" is the default when nothing is chosen.
ModelDefault = Literal["auto", "claude", "openai", "xai", "gemini", "m8tes"]
AuthorizableModelConnectionProvider = Literal["claude", "openai", "xai", "gemini"]
DeviceModelConnectionProvider = Literal["openai", "xai"]
CodeModelConnectionProvider = Literal["claude", "gemini"]


class ModelConnections:
    """``client.model_connections`` — authorize model provider plans."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def list(self) -> SyncPage[ModelConnection]:
        body = self._http.request("GET", "/model-connections/").json()
        return SyncPage(
            data=[ModelConnection.from_dict(item) for item in body["data"]],
            has_more=body.get("has_more", False),
            next_starting_after=body.get("next_starting_after"),
        )

    def get_default(self) -> ModelDefault:
        """Read the account default for new runs.

        ``"auto"`` is the connected plans in order, then m8tes inference on Teams. ``"m8tes"`` is
        m8tes inference only (Teams). A provider name is that connected plan first, then the
        others as Auto does.
        """
        body = self._http.request("GET", "/model-connections/default").json()
        # The response is untyped JSON; the API returns one of the `ModelDefault` values.
        return cast("ModelDefault", body["default"])

    def apply_default(self, provider: ModelDefaultChoice) -> ApplyPreferredModelResult:
        """Set a connected provider, or ``"m8tes"`` (Teams), as the account default.

        Applies to platform mates with no model of their own. The provider runs first and your
        other plans follow it; ``"m8tes"`` skips your plans and runs on m8tes inference.
        """
        body = self._http.request(
            "POST", f"/model-connections/{seg(provider)}/apply-default"
        ).json()
        return ApplyPreferredModelResult.from_dict(body)

    def use_m8tes(self) -> ApplyPreferredModelResult:
        """Make m8tes inference the account default (Teams plans). Your plans are skipped."""
        return self.apply_default("m8tes")

    def set_default_model(
        self, provider: ModelConnectionProvider, *, model: str | None
    ) -> ModelConnection:
        """Choose this provider's model without switching the account's preferred provider.

        Pass ``None`` to follow the provider's platform default again. Explicit
        agent/run model selections keep precedence over this account preference.
        """
        body = self._http.request(
            "PATCH", f"/model-connections/{seg(provider)}/default-model", json={"model": model}
        ).json()
        return ModelConnection.from_dict(body)

    def clear_default(self) -> bool:
        """Return the account default to Auto.

        Clears a connected provider or m8tes inference chosen as the default. Auto asks the
        connected plans in order and, on Teams, uses m8tes inference when none is left. Explicit
        models and API/Embed billing are unchanged.
        """
        body = self._http.request("DELETE", "/model-connections/preferred-default").json()
        return bool(body.get("cleared"))

    def authorize(self, provider: AuthorizableModelConnectionProvider) -> ModelAuthorization:
        """Start provider-native authorization; show the returned URL and device code when used.

        Claude and Gemini return an ``authorization_url`` — open it, then pass the
        pasted code to ``complete_authorization``. OpenAI/xAI return a device
        ``user_code`` — poll ``authorization_status`` until connected.
        """
        body = self._http.request(
            "POST", f"/model-connections/{seg(provider)}/authorizations"
        ).json()
        return ModelAuthorization.from_dict(body)

    def authorization_status(
        self, provider: DeviceModelConnectionProvider, state: str
    ) -> ModelAuthorization:
        """Poll once; successful device authorization is saved automatically."""
        body = self._http.request(
            "GET", f"/model-connections/{seg(provider)}/authorizations/{seg(state)}"
        ).json()
        return ModelAuthorization.from_dict(body)

    def complete_authorization(
        self,
        provider: CodeModelConnectionProvider,
        state: str,
        *,
        code: str,
        project_id: str | None = None,
    ) -> ModelAuthorization:
        """Exchange a pasted authorization code and store the connection."""
        payload: dict = {"code": code}
        if project_id is not None:
            payload["project_id"] = project_id
        body = self._http.request(
            "POST",
            f"/model-connections/{seg(provider)}/authorizations/{seg(state)}",
            json=payload,
        ).json()
        return ModelAuthorization.from_dict(body)

    def paste_claude(
        self,
        *,
        access_token: str,
        refresh_token: str | None = None,
        expires_at_ms: int | None = None,
    ) -> ModelConnection:
        """Store a Claude OAuth token from ``~/.claude/.credentials.json`` (no browser)."""
        body: dict = {"access_token": access_token}
        if refresh_token is not None:
            body["refresh_token"] = refresh_token
        if expires_at_ms is not None:
            body["expires_at_ms"] = expires_at_ms
        resp = self._http.request("POST", "/model-connections/claude/paste", json=body)
        return ModelConnection.from_dict(resp.json())

    def cancel_authorization(
        self, provider: AuthorizableModelConnectionProvider, state: str
    ) -> None:
        self._http.request(
            "DELETE", f"/model-connections/{seg(provider)}/authorizations/{seg(state)}"
        )

    def disconnect(self, provider: ModelConnectionProvider) -> ModelConnection:
        """Disconnect every account connected for ``provider``."""
        body = self._http.request("DELETE", f"/model-connections/{seg(provider)}").json()
        return ModelConnection.from_dict(body)

    def disconnect_account(
        self, provider: ModelConnectionProvider, account_id: int
    ) -> ModelConnection:
        """Disconnect one account (``ModelConnection.accounts[i].id``); siblings stay."""
        body = self._http.request(
            "DELETE", f"/model-connections/{seg(provider)}/accounts/{seg(account_id)}"
        ).json()
        return ModelConnection.from_dict(body)
