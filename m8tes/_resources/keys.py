"""Keys resource — manage the account's API key(s).

The account's single "default" key: ``info()`` / ``rotate()`` / ``revoke()`` (no id).
Named, multiple keys (with optional expiry, independently revocable): ``create()`` /
``list()`` / ``rotate(key_id)`` / ``revoke(key_id)``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._types import ApiKeyCreated, ApiKeyInfo, ApiKeyRotated, NamedApiKey

if TYPE_CHECKING:
    from .._http import HTTPClient


class Keys:
    """client.keys — API key management."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def info(self) -> ApiKeyInfo:
        """Get the default key's state (masked prefix only)."""
        resp = self._http.request("GET", "/keys/")
        return ApiKeyInfo.from_dict(resp.json())

    def create(self, *, name: str, expires_in_days: int | None = None) -> ApiKeyCreated:
        """Create a named key. The full key is returned ONCE — store it now.

        Raises RateLimitError (429) at the active named-key cap (50 per
        account), and PermissionDeniedError (403) on an unclaimed
        agent-signup account (claim the account by verifying email + setting
        a password first).
        """
        body: dict = {"name": name}
        if expires_in_days is not None:
            body["expires_in_days"] = expires_in_days
        resp = self._http.request("POST", "/keys/", json=body)
        return ApiKeyCreated.from_dict(resp.json())

    def list(self) -> list[NamedApiKey]:
        """List the account's named keys (newest first). Secrets are never returned."""
        resp = self._http.request("GET", "/keys/all")
        return [NamedApiKey.from_dict(r) for r in resp.json()]

    def rotate(self, key_id: int | None = None) -> ApiKeyRotated | ApiKeyCreated:
        """Rotate a key — the named key ``key_id`` if given, else the default key. The
        old secret dies immediately; the new one is returned ONCE.

        Raises ConflictError (409) when the named key is already revoked, and
        PermissionDeniedError (403) on an unclaimed agent-signup account.
        """
        if key_id is None:
            return ApiKeyRotated.from_dict(self._http.request("POST", "/keys/rotate").json())
        return ApiKeyCreated.from_dict(self._http.request("POST", f"/keys/{key_id}/rotate").json())

    def revoke(self, key_id: int | None = None) -> ApiKeyInfo | NamedApiKey:
        """Revoke a key — the named key ``key_id`` if given, else the default key. It
        stops authenticating immediately."""
        if key_id is None:
            return ApiKeyInfo.from_dict(self._http.request("DELETE", "/keys/").json())
        return NamedApiKey.from_dict(self._http.request("DELETE", f"/keys/{key_id}").json())
