"""Account-level model provider OAuth subscription connections."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from .._http import seg
from .._types import ApplyPreferredModelResult, ModelAuthorization, ModelConnection, SyncPage

if TYPE_CHECKING:
    from .._http import HTTPClient

ModelConnectionProvider = Literal["claude", "openai", "xai", "gemini"]
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
        )

    def apply_default(self, provider: ModelConnectionProvider) -> ApplyPreferredModelResult:
        """Set this connected provider as the account default for NULL-alias platform mates."""
        body = self._http.request(
            "POST", f"/model-connections/{seg(provider)}/apply-default"
        ).json()
        return ApplyPreferredModelResult.from_dict(body)

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
        self, provider: CodeModelConnectionProvider, state: str, *, code: str
    ) -> ModelAuthorization:
        """Exchange a pasted authorization code and store the connection."""
        body = self._http.request(
            "POST",
            f"/model-connections/{seg(provider)}/authorizations/{seg(state)}",
            json={"code": code},
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
        body = self._http.request("DELETE", f"/model-connections/{seg(provider)}").json()
        return ModelConnection.from_dict(body)
