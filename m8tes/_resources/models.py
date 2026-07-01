"""Models resource — discover the selectable models and their per-token prices."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._types import Model, SyncPage

if TYPE_CHECKING:
    from .._http import HTTPClient


class Models:
    """client.models — list the models you can pass as ``model`` on a teammate or run.

    The set is the publicly selectable models (it grows, incl. non-Anthropic and open-source
    models, as they're enabled — no SDK change needed since ``model`` is a plain string).
    """

    def __init__(self, http: HTTPClient):
        self._http = http

    def list(self) -> SyncPage[Model]:
        """List selectable models with USD price per million tokens.

        Pass a returned ``id`` as ``model`` on a teammate or run; omit ``model`` to use the
        one with ``default=True``.
        """
        body = self._http.request("GET", "/models/").json()
        return SyncPage(
            data=[Model.from_dict(d) for d in body["data"]],
            has_more=body["has_more"],
        )
