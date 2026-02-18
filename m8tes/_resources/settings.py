"""Settings resource — account-level configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._types import AccountSettings

if TYPE_CHECKING:
    from .._http import HTTPClient


class Settings:
    """client.settings — account settings management."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def get(self) -> AccountSettings:
        resp = self._http.request("GET", "/settings")
        return AccountSettings.from_dict(resp.json())

    def update(self, *, company_research: bool | None = None) -> AccountSettings:
        body: dict = {}
        if company_research is not None:
            body["company_research"] = company_research
        resp = self._http.request("PATCH", "/settings", json=body)
        return AccountSettings.from_dict(resp.json())
