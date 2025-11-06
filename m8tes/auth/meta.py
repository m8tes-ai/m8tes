"""Meta Ads OAuth authentication service for the m8tes SDK."""

from __future__ import annotations

from typing import Any

from ..http.client import HTTPClient


class MetaAuth:
    """Helper class for Meta (Facebook) OAuth operations."""

    # mypy: disable-error-code="no-untyped-def"
    def __init__(self, http_client: HTTPClient, client: object = None) -> None:
        """Initialize Meta OAuth service."""
        self.http = http_client
        self._client = client

    def start_connect(
        self,
        redirect_uri: str,
        state: str | None = None,
        scopes: list[str] | None = None,
    ) -> dict[str, Any]:
        """Start Meta OAuth connection flow."""
        payload: dict[str, Any] = {"redirect_uri": redirect_uri}

        if state:
            payload["state"] = state
        if scopes:
            payload["scopes"] = scopes

        response = self.http.post(
            "/api/v1/integrations/meta-ads/auth/init",
            json_data=payload,
        )

        return {
            "authorization_url": response["authorization_url"],
            "state": response["state"],
            "expires_in": response.get("expires_in", 600),
        }

    def finish_connect(
        self,
        code: str,
        state: str,
        redirect_uri: str,
        user_id: int | None = None,
        email: str | None = None,
        scopes: list[str] | None = None,
    ) -> dict[str, Any]:
        """Complete Meta OAuth flow with authorization code."""
        payload: dict[str, Any] = {
            "code": code,
            "state": state,
            "redirect_uri": redirect_uri,
        }

        if user_id is not None:
            payload["user_id"] = user_id
        if email is not None:
            payload["email"] = email
        if scopes is not None:
            payload["scopes"] = scopes

        return self.http.post(
            "/api/v1/integrations/meta-ads/auth/callback",
            json_data=payload,
        )

    def get_status(self) -> dict[str, Any]:
        """Retrieve Meta Ads integration status for authenticated user."""
        return self.http.get("/api/v1/integrations/meta-ads/status")

    def disconnect(self) -> dict[str, Any]:
        """Delete Meta Ads integration for authenticated user."""
        return self.http.delete("/api/v1/integrations/meta-ads")

    @property
    def client(self) -> object:
        """Backward compatibility property for tests."""
        return self._client
