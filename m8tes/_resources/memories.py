"""Memories resource — manage account-level and end-user memories via API."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._types import Memory, SyncPage
from ._utils import _build_params

if TYPE_CHECKING:
    from .._http import HTTPClient


class Memories:
    """client.memories — create, list, update, delete memories.

    ``user_id`` scopes a memory to one end-user; omit it for account-level
    memories (seen by runs that carry no ``user_id``). The scopes never mix.
    """

    def __init__(self, http: HTTPClient):
        self._http = http

    def create(self, *, content: str, user_id: str | None = None) -> Memory:
        """Create a memory (account-level when ``user_id`` is omitted).

        Raises ConflictError (409) when the scope is at the memory capacity
        limit, or when a memory with identical content already exists in it.
        """
        body: dict = {"content": content}
        if user_id is not None:
            body["user_id"] = user_id
        resp = self._http.request("POST", "/memories/", json=body)
        return Memory.from_dict(resp.json())

    def list(
        self,
        *,
        user_id: str | None = None,
        query: str | None = None,
        limit: int = 20,
        starting_after: int | None = None,
    ) -> SyncPage[Memory]:
        """List one scope's memories (account-level when ``user_id`` is omitted).

        Pass ``query`` to keyword-filter by content (case-insensitive substring);
        the filter never widens the scope and pagination applies to the
        filtered set.
        """
        params = _build_params(
            user_id=user_id, query=query, limit=limit, starting_after=starting_after
        )
        resp = self._http.request("GET", "/memories/", params=params)
        body = resp.json()

        def _fetch_next(**kw: object) -> SyncPage[Memory]:
            return self.list(user_id=user_id, query=query, **kw)  # type: ignore[arg-type]

        return SyncPage(
            data=[Memory.from_dict(d) for d in body["data"]],
            has_more=body["has_more"],
            _fetch_next=_fetch_next,
        )

    def update(self, memory_id: int, *, content: str, user_id: str | None = None) -> Memory:
        """Correct a memory's content in place (instead of delete + re-create)."""
        resp = self._http.request(
            "PATCH",
            f"/memories/{memory_id}",
            params=_build_params(user_id=user_id),
            json={"content": content},
        )
        return Memory.from_dict(resp.json())

    def delete(self, memory_id: int, *, user_id: str | None = None) -> None:
        """Delete a memory in exactly the given scope."""
        self._http.request(
            "DELETE", f"/memories/{memory_id}", params=_build_params(user_id=user_id)
        )
