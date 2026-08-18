"""Audit logs resource — inspect account-scoped API request history."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from .._types import AuditLog, SyncPage
from ._utils import _build_params

if TYPE_CHECKING:
    from .._http import HTTPClient


class AuditLogs:
    """client.audit_logs — list API request audit logs for the current account."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def list(
        self,
        *,
        action: str | None = None,
        resource_type: str | None = None,
        method: str | None = None,
        status_code: int | None = None,
        auth: Literal["all", "api_key", "dashboard"] | None = None,
        limit: int = 20,
        starting_after: int | None = None,
    ) -> SyncPage[AuditLog]:
        """List audit logs with optional filters and cursor pagination.

        `auth` filters by how each request was authenticated: ``api_key`` for calls
        made with an ``m8_`` key (your SDK/API traffic), ``dashboard`` for web-app
        sessions and auth events, ``all`` (the server default) for the full trail.
        """
        params = _build_params(
            action=action,
            resource_type=resource_type,
            method=method.upper() if method is not None else None,
            status_code=status_code,
            auth=auth,
            limit=limit,
            starting_after=starting_after,
        )
        resp = self._http.request("GET", "/audit-logs/", params=params)
        body = resp.json()

        def _fetch_next(**kw: object) -> SyncPage[AuditLog]:
            # Every filter must be re-sent: page 2 onward would otherwise silently
            # widen to the unfiltered default.
            return self.list(
                action=action,
                resource_type=resource_type,
                method=method,
                status_code=status_code,
                auth=auth,
                limit=limit,
                **kw,  # type: ignore[arg-type]
            )

        return SyncPage(
            data=[AuditLog.from_dict(d) for d in body["data"]],
            has_more=body["has_more"],
            _fetch_next=_fetch_next,
        )
