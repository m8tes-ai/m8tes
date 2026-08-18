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
        limit: int = 20,
        starting_after: str | None = None,
    ) -> SyncPage[Trigger]:
        """List triggers across the account, optionally scoped or filtered."""
        params = _build_params(
            user_id=user_id,
            type=type,
            task_id=task_id,
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
                limit=limit,
                **kwargs,  # type: ignore[arg-type]
            )

        return SyncPage(
            data=[Trigger.from_dict(item) for item in body["data"]],
            has_more=body["has_more"],
            _fetch_next=_fetch_next,
        )
