"""Apps resource — available tools catalog."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._types import App

if TYPE_CHECKING:
    from .._http import HTTPClient


class Apps:
    """client.apps — list available tools and integrations."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def list(self) -> list[App]:
        resp = self._http.request("GET", "/apps")
        return [App.from_dict(d) for d in resp.json()]
