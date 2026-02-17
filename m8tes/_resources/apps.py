"""Apps resource — available tools catalog."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._types import App, SyncPage

if TYPE_CHECKING:
    from .._http import HTTPClient


class Apps:
    """client.apps — list available tools and integrations."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def list(self) -> SyncPage[App]:
        resp = self._http.request("GET", "/apps")
        body = resp.json()
        return SyncPage(data=[App.from_dict(d) for d in body["data"]], has_more=body["has_more"])
