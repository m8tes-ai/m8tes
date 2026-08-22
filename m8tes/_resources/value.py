"""Value resource — connect agent cost to evidence-backed customer outcomes."""

from __future__ import annotations

from datetime import date, datetime
from functools import partial
from typing import TYPE_CHECKING, Any, Literal, cast

from .._http import seg
from .._types import SyncPage, ValueObservation, ValueReport, ValueUseCase
from ._utils import _build_params

if TYPE_CHECKING:
    from .._http import HTTPClient


class Value:
    """client.value — maintain dynamic use cases, evidence, and value reports."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def create_use_case(
        self,
        *,
        name: str,
        goal: str,
        measurement_model: dict[str, Any] | None = None,
        responsible_user_id: int | None = None,
        source_run_id: int | None = None,
        user_id: str | None = None,
    ) -> ValueUseCase:
        response = self._http.request(
            "POST",
            "/value/use-cases",
            json=_build_params(
                name=name,
                goal=goal,
                measurement_model=measurement_model or {},
                responsible_user_id=responsible_user_id,
                source_run_id=source_run_id,
                user_id=user_id,
            ),
        )
        return ValueUseCase.from_dict(response.json())

    def list_use_cases(
        self,
        *,
        user_id: str | None = None,
        status: Literal["active", "paused", "stopped"] | None = None,
        limit: int = 20,
        starting_after: int | None = None,
    ) -> SyncPage[ValueUseCase]:
        response = self._http.request(
            "GET",
            "/value/use-cases",
            params=_build_params(
                user_id=user_id, status=status, limit=limit, starting_after=starting_after
            ),
        )
        body = response.json()
        return SyncPage(
            data=[ValueUseCase.from_dict(row) for row in body["data"]],
            has_more=body["has_more"],
            _fetch_next=partial(self.list_use_cases, user_id=user_id, status=status, limit=limit),
        )

    def get_use_case(self, use_case_id: int, *, user_id: str | None = None) -> ValueUseCase:
        response = self._http.request(
            "GET",
            f"/value/use-cases/{seg(use_case_id)}",
            params=_build_params(user_id=user_id),
        )
        return ValueUseCase.from_dict(response.json())

    def update_use_case(
        self,
        use_case_id: int,
        *,
        name: str | None = None,
        goal: str | None = None,
        measurement_model: dict[str, Any] | None = None,
        responsible_user_id: int | None = None,
        status: Literal["active", "paused", "stopped"] | None = None,
        user_id: str | None = None,
    ) -> ValueUseCase:
        body = _build_params(
            name=name,
            goal=goal,
            measurement_model=measurement_model,
            responsible_user_id=responsible_user_id,
            status=status,
        )
        if not body:
            raise ValueError("Pass at least one value use case field to update")
        response = self._http.request(
            "PATCH",
            f"/value/use-cases/{seg(use_case_id)}",
            params=_build_params(user_id=user_id),
            json=body,
        )
        return ValueUseCase.from_dict(response.json())

    def link_runs(
        self, use_case_id: int, run_ids: list[int], *, user_id: str | None = None
    ) -> list[int]:
        response = self._http.request(
            "POST",
            f"/value/use-cases/{seg(use_case_id)}/runs",
            params=_build_params(user_id=user_id),
            json={"run_ids": run_ids},
        )
        return cast(list[int], response.json()["linked_run_ids"])

    def create_observation(
        self,
        use_case_id: int,
        *,
        kind: Literal[
            "revenue_generated",
            "revenue_protected",
            "cash_saved",
            "capacity_unlocked",
            "operational",
        ],
        evidence_level: Literal["measured", "attributed", "estimated", "unquantified"],
        title: str,
        observed_at: datetime | str,
        amount_usd: str | None = None,
        metric_name: str | None = None,
        metric_value: str | None = None,
        metric_unit: str | None = None,
        evidence: list[dict[str, Any]] | None = None,
        source_run_id: int | None = None,
        user_id: str | None = None,
    ) -> ValueObservation:
        if evidence_level == "unquantified" and amount_usd is not None:
            raise ValueError("amount_usd must be omitted for unquantified evidence")
        if not evidence:
            raise ValueError("evidence must include at least one source for every outcome")
        response = self._http.request(
            "POST",
            f"/value/use-cases/{seg(use_case_id)}/observations",
            params=_build_params(user_id=user_id),
            json=_build_params(
                kind=kind,
                evidence_level=evidence_level,
                title=title,
                observed_at=(
                    observed_at.isoformat() if isinstance(observed_at, datetime) else observed_at
                ),
                amount_usd=amount_usd,
                metric_name=metric_name,
                metric_value=metric_value,
                metric_unit=metric_unit,
                evidence=evidence or [],
                source_run_id=source_run_id,
            ),
        )
        return ValueObservation.from_dict(response.json())

    def list_observations(
        self,
        use_case_id: int,
        *,
        user_id: str | None = None,
        limit: int = 20,
        starting_after: int | None = None,
    ) -> SyncPage[ValueObservation]:
        response = self._http.request(
            "GET",
            f"/value/use-cases/{seg(use_case_id)}/observations",
            params=_build_params(user_id=user_id, limit=limit, starting_after=starting_after),
        )
        body = response.json()
        return SyncPage(
            data=[ValueObservation.from_dict(row) for row in body["data"]],
            has_more=body["has_more"],
            _fetch_next=partial(self.list_observations, use_case_id, user_id=user_id, limit=limit),
        )

    def confirm_observation(
        self,
        observation_id: int,
        decision: Literal["confirmed", "rejected"],
        *,
        user_id: str | None = None,
    ) -> ValueObservation:
        response = self._http.request(
            "POST",
            f"/value/observations/{seg(observation_id)}/confirm",
            params=_build_params(user_id=user_id),
            json={"decision": decision},
        )
        return ValueObservation.from_dict(response.json())

    def report(
        self,
        *,
        start_date: date | str | None = None,
        end_date: date | str | None = None,
        user_id: str | None = None,
    ) -> ValueReport:
        response = self._http.request(
            "GET",
            "/value/report",
            params=_build_params(
                start_date=(start_date.isoformat() if isinstance(start_date, date) else start_date),
                end_date=end_date.isoformat() if isinstance(end_date, date) else end_date,
                user_id=user_id,
            ),
        )
        return ValueReport.from_dict(response.json())
