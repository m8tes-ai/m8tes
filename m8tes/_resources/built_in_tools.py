"""Built-in tools resource — discover the platform's own MCP tools."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._types import BuiltInTool, SyncPage
from ._utils import _build_params

if TYPE_CHECKING:
    from .._http import HTTPClient


class BuiltInTools:
    """client.built_in_tools — discover the platform's built-in tools.

    These (memory, task history, task setup, feedback, and more) are NOT passed in
    the ``tools=[...]`` array. The four configurable ones are toggled via the
    ``enable_*`` fields on teammates/tasks/runs; this lists all of them with their
    resolved enabled state and multi-tenant availability.
    """

    def __init__(self, http: HTTPClient):
        self._http = http

    def list(
        self,
        *,
        teammate_id: int | None = None,
        user_id: str | None = None,
    ) -> SyncPage[BuiltInTool]:
        """List the built-in tools with resolved enabled state.

        Pass ``teammate_id`` to resolve the four configurable toggles against that
        teammate's defaults. Pass ``user_id`` to evaluate end-user (multi-tenant)
        availability: tools that aren't multi-tenant safe report ``enabled=False``.
        """
        params = _build_params(teammate_id=teammate_id, user_id=user_id)
        resp = self._http.request("GET", "/built-in-tools/", params=params)
        body = resp.json()
        return SyncPage(
            data=[BuiltInTool.from_dict(d) for d in body["data"]],
            has_more=body["has_more"],
        )
