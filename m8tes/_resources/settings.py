"""Settings resource — account-level configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .._types import AccountSettings

if TYPE_CHECKING:
    from .._http import HTTPClient

# Sentinel so update() can distinguish "omit" from "explicitly set to None"
# (passing None clears a per-end-user cap; omitting leaves it unchanged).
_UNSET: Any = object()


class Settings:
    """client.settings — account settings management."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def get(self) -> AccountSettings:
        resp = self._http.request("GET", "/settings/")
        return AccountSettings.from_dict(resp.json())

    def update(
        self,
        *,
        per_end_user_run_limit: int | None = _UNSET,
        per_end_user_cost_limit_cents: int | None = _UNSET,
        per_end_user_rate_per_minute: int | None = _UNSET,
        retention_mode: str | None = None,
    ) -> AccountSettings:
        """Update account settings.

        The per-end-user sub-caps bound each of your end-users' (``user_id``) monthly
        runs / metered cost / run-starts-per-minute so one end-user can't drain the
        account budget or burst it — pass
        an int to set, ``None`` to clear, or omit to leave unchanged.
        ``retention_mode`` is ``"standard"`` or ``"metadata_only"`` (zero data
        retention — we never persist message content, tool I/O, or generated reports).
        """
        body: dict = {}
        if per_end_user_run_limit is not _UNSET:
            body["per_end_user_run_limit"] = per_end_user_run_limit
        if per_end_user_cost_limit_cents is not _UNSET:
            body["per_end_user_cost_limit_cents"] = per_end_user_cost_limit_cents
        if per_end_user_rate_per_minute is not _UNSET:
            body["per_end_user_rate_per_minute"] = per_end_user_rate_per_minute
        if retention_mode is not None:
            body["retention_mode"] = retention_mode
        resp = self._http.request("PATCH", "/settings/", json=body)
        return AccountSettings.from_dict(resp.json())
