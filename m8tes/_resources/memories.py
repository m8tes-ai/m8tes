"""Memories resource — manage end-user memories via API."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._types import Memory

if TYPE_CHECKING:
    from .._http import HTTPClient


class Memories:
    """client.memories — create, list, delete end-user memories."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def create(self, *, user_id: str, content: str) -> Memory:
        """Create a memory for an end-user."""
        resp = self._http.request("POST", "/memories", json={"user_id": user_id, "content": content})
        return Memory.from_dict(resp.json())

    def list(self, *, user_id: str, limit: int = 20) -> list[Memory]:
        """List memories for an end-user."""
        resp = self._http.request("GET", "/memories", params={"user_id": user_id, "limit": limit})
        return [Memory.from_dict(d) for d in resp.json()]

    def delete(self, memory_id: int, *, user_id: str) -> None:
        """Delete a specific end-user memory."""
        self._http.request("DELETE", f"/memories/{memory_id}", params={"user_id": user_id})
