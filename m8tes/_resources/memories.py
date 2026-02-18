"""Memories resource — manage end-user memories via API."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._types import Memory, SyncPage
from ._utils import _build_params

if TYPE_CHECKING:
    from .._http import HTTPClient


class Memories:
    """client.memories — create, list, delete end-user memories."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def create(self, *, user_id: str, content: str) -> Memory:
        """Create a memory for an end-user."""
        resp = self._http.request(
            "POST", "/memories", json={"user_id": user_id, "content": content}
        )
        return Memory.from_dict(resp.json())

    def list(
        self,
        *,
        user_id: str,
        limit: int = 20,
        starting_after: int | None = None,
    ) -> SyncPage[Memory]:
        """List memories for an end-user."""
        params = _build_params(user_id=user_id, limit=limit, starting_after=starting_after)
        resp = self._http.request("GET", "/memories", params=params)
        body = resp.json()

        def _fetch_next(**kw: object) -> SyncPage[Memory]:
            return self.list(user_id=user_id, **kw)  # type: ignore[arg-type]

        return SyncPage(
            data=[Memory.from_dict(d) for d in body["data"]],
            has_more=body["has_more"],
            _fetch_next=_fetch_next,
        )

    def delete(self, memory_id: int, *, user_id: str) -> None:
        """Delete a specific end-user memory."""
        self._http.request("DELETE", f"/memories/{memory_id}", params={"user_id": user_id})
