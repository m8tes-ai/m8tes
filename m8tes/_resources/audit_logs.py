"""Audit logs resource — inspect account-scoped API request history."""

from __future__ import annotations

from typing import TYPE_CHECKING

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
        limit: int = 20,
        starting_after: int | None = None,
    ) -> SyncPage[AuditLog]:
        """List audit logs with optional filters and cursor pagination."""
        params = _build_params(
            action=action,
            resource_type=resource_type,
            method=method.upper() if method is not None else None,
            status_code=status_code,
            limit=limit,
            starting_after=starting_after,
        )
        resp = self._http.request("GET", "/audit-logs", params=params)
        body = resp.json()

        def _fetch_next(**kw: object) -> SyncPage[AuditLog]:
            return self.list(
                action=action,
                resource_type=resource_type,
                method=method,
                status_code=status_code,
                **kw,  # type: ignore[arg-type]
            )

        return SyncPage(
            data=[AuditLog.from_dict(d) for d in body["data"]],
            has_more=body["has_more"],
            _fetch_next=_fetch_next,
        )
