"""Top-level trigger resource for bounded account-wide discovery."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from .._types import SyncPage, Trigger
from ._utils import _build_params

if TYPE_CHECKING:
    from .._http import HTTPClient


class Triggers:
    """client.triggers — list schedule, webhook, email, and app triggers."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def list(
        self,
        *,
        user_id: str | None = None,
        type: Literal["schedule", "webhook", "email", "app"] | None = None,
        task_id: int | None = None,
        include_last_run: bool | None = None,
        limit: int = 20,
        starting_after: str | None = None,
    ) -> SyncPage[Trigger]:
        """List triggers across the account, optionally scoped or filtered.

        A schedule the system paused says why in ``pause_reason``. Pass
        ``include_last_run=True`` to fill ``last_run`` and ``failure_streak`` on each
        schedule: its newest run and how many scheduled occurrences failed in a row, from
        the last 14 days. It is off by default because it reads run history.
        """
        params = _build_params(
            user_id=user_id,
            type=type,
            task_id=task_id,
            include_last_run=(None if include_last_run is None else str(include_last_run).lower()),
            limit=limit,
            starting_after=starting_after,
        )
        response = self._http.request("GET", "/triggers/", params=params)
        body = response.json()

        def _fetch_next(**kwargs: object) -> SyncPage[Trigger]:
            return self.list(
                user_id=user_id,
                type=type,
                task_id=task_id,
                include_last_run=include_last_run,
                limit=limit,
                **kwargs,  # type: ignore[arg-type]
            )

        return SyncPage(
            data=[Trigger.from_dict(item) for item in body["data"]],
            has_more=body["has_more"],
            _fetch_next=_fetch_next,
        )
