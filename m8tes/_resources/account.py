"""Account resource — account-level operations for the current account."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from .._http import HTTPClient


class Account:
    """client.account — manage the current account."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def export(self) -> dict[str, Any]:
        """Export all of the current account's data (GDPR/CCPA right to access).

        Returns a JSON document of the account's teammates, tasks, runs, documents,
        memories, and integration metadata. Secrets are never included.
        """
        resp = self._http.request("GET", "/account/export")
        return cast("dict[str, Any]", resp.json())

    def delete(self) -> dict[str, Any]:
        """Request deletion of the current account.

        Soft-delete: the account is deactivated immediately (sessions and API key
        revoked, billing canceled, automation stopped) and its data is erased
        after a grace period. Returns the API's status payload.
        """
        resp = self._http.request("DELETE", "/account")
        return cast("dict[str, Any]", resp.json())
