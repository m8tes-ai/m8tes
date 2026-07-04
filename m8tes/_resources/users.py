"""Users resource — CRUD for end-user profiles."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._types import EndUser, EndUserUsage, SyncPage
from ._utils import _build_params

_list = list  # preserve builtin; shadowed by .list() method

# Distinguishes "omit field" from "clear override with None" (PATCH semantics).
_UNSET: object = object()

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
        run_limit: int | None = None,
        cost_limit_cents: int | None = None,
        rate_per_minute: int | None = None,
    ) -> EndUser:
        """Create an end-user profile. The optional per-individual sub-cap
        overrides (run_limit / cost_limit_cents / rate_per_minute) win over the
        account-wide ``client.settings`` defaults; ``run_limit=0`` blocks the
        end-user entirely."""
        body: dict = {"user_id": user_id}
        if name is not None:
            body["name"] = name
        if email is not None:
            body["email"] = email
        if company is not None:
            body["company"] = company
        if metadata is not None:
            body["metadata"] = metadata
        if run_limit is not None:
            body["run_limit"] = run_limit
        if cost_limit_cents is not None:
            body["cost_limit_cents"] = cost_limit_cents
        if rate_per_minute is not None:
            body["rate_per_minute"] = rate_per_minute
        resp = self._http.request("POST", "/users/", json=body)
        return EndUser.from_dict(resp.json())

    def usage(
        self,
        user_id: str | None = None,
        *,
        limit: int = 20,
        starting_after: int | None = None,
    ) -> SyncPage[EndUserUsage]:
        """Per-end-user usage rollup for the current billing period.

        Pass `user_id` to read one end-user's usage; omit it to page through all.
        """
        params = _build_params(limit=limit, starting_after=starting_after, user_id=user_id)
        resp = self._http.request("GET", "/usage/end-users", params=params)
        body = resp.json()

        def _fetch_next(**kw: object) -> SyncPage[EndUserUsage]:
            return self.usage(user_id, **kw)  # type: ignore[arg-type]

        return SyncPage(
            data=[EndUserUsage.from_dict(d) for d in body["data"]],
            has_more=body["has_more"],
            _fetch_next=_fetch_next,
        )

    def list(
        self,
        *,
        limit: int = 20,
        starting_after: int | None = None,
    ) -> SyncPage[EndUser]:
        params = _build_params(limit=limit, starting_after=starting_after)
        resp = self._http.request("GET", "/users/", params=params)
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
        run_limit: int | None = _UNSET,  # type: ignore[assignment]
        cost_limit_cents: int | None = _UNSET,  # type: ignore[assignment]
        rate_per_minute: int | None = _UNSET,  # type: ignore[assignment]
    ) -> EndUser:
        """Update an end-user profile. For the sub-cap overrides, pass an int to
        set, ``None`` to clear (inherit the account default), or omit to leave
        unchanged."""
        body: dict = {}
        if name is not None:
            body["name"] = name
        if email is not None:
            body["email"] = email
        if company is not None:
            body["company"] = company
        if metadata is not None:
            body["metadata"] = metadata
        if run_limit is not _UNSET:
            body["run_limit"] = run_limit
        if cost_limit_cents is not _UNSET:
            body["cost_limit_cents"] = cost_limit_cents
        if rate_per_minute is not _UNSET:
            body["rate_per_minute"] = rate_per_minute
        resp = self._http.request("PATCH", f"/users/{user_id}", json=body)
        return EndUser.from_dict(resp.json())

    def delete(self, user_id: str) -> None:
        self._http.request("DELETE", f"/users/{user_id}")
