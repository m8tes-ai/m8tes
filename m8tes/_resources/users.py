"""Users resource — CRUD for end-user profiles."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._types import EndUser, SyncPage
from ._utils import _build_params

_list = list  # preserve builtin; shadowed by .list() method

if TYPE_CHECKING:
    from .._http import HTTPClient


class Users:
    """client.users — end-user profile CRUD."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def create(
        self,
        *,
        user_id: str,
        name: str | None = None,
        email: str | None = None,
        company: str | None = None,
        metadata: dict | None = None,
    ) -> EndUser:
        body: dict = {"user_id": user_id}
        if name is not None:
            body["name"] = name
        if email is not None:
            body["email"] = email
        if company is not None:
            body["company"] = company
        if metadata is not None:
            body["metadata"] = metadata
        resp = self._http.request("POST", "/users", json=body)
        return EndUser.from_dict(resp.json())

    def list(
        self,
        *,
        limit: int = 20,
        starting_after: int | None = None,
    ) -> SyncPage[EndUser]:
        params = _build_params(limit=limit, starting_after=starting_after)
        resp = self._http.request("GET", "/users", params=params)
        body = resp.json()

        def _fetch_next(**kw: object) -> SyncPage[EndUser]:
            return self.list(**kw)  # type: ignore[arg-type]

        return SyncPage(
            data=[EndUser.from_dict(d) for d in body["data"]],
            has_more=body["has_more"],
            _fetch_next=_fetch_next,
        )

    def get(self, user_id: str) -> EndUser:
        resp = self._http.request("GET", f"/users/{user_id}")
        return EndUser.from_dict(resp.json())

    def update(
        self,
        user_id: str,
        *,
        name: str | None = None,
        email: str | None = None,
        company: str | None = None,
        metadata: dict | None = None,
    ) -> EndUser:
        body: dict = {}
        if name is not None:
            body["name"] = name
        if email is not None:
            body["email"] = email
        if company is not None:
            body["company"] = company
        if metadata is not None:
            body["metadata"] = metadata
        resp = self._http.request("PATCH", f"/users/{user_id}", json=body)
        return EndUser.from_dict(resp.json())

    def delete(self, user_id: str) -> None:
        self._http.request("DELETE", f"/users/{user_id}")
