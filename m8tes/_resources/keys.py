"""Keys resource — manage the account's API key (rotate / revoke / inspect)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._types import ApiKeyInfo, ApiKeyRotated

if TYPE_CHECKING:
    from .._http import HTTPClient


class Keys:
    """client.keys — API key rotation and revocation."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def info(self) -> ApiKeyInfo:
        """Get the current API key state (masked prefix only)."""
        resp = self._http.request("GET", "/keys/")
        return ApiKeyInfo.from_dict(resp.json())

    def rotate(self) -> ApiKeyRotated:
        """Rotate the API key. The old key stops working immediately; the returned
        key is shown ONCE — store it now."""
        resp = self._http.request("POST", "/keys/rotate")
        return ApiKeyRotated.from_dict(resp.json())

    def revoke(self) -> ApiKeyInfo:
        """Revoke the API key, ending all API-key access. If you authenticated with
        this key, programmatic access ends now — generate a new one via the dashboard."""
        resp = self._http.request("DELETE", "/keys/")
        return ApiKeyInfo.from_dict(resp.json())
