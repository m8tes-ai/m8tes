"""Advisory typed judgments over caller-provided state and evidence."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, overload

from .._types import Judgment, JudgmentClaim, JudgmentEvidence, JudgmentQuestion
from ._utils import _build_params

if TYPE_CHECKING:
    from .._http import HTTPClient


class Judgments:
    """client.judgments — stateless, platform-funded Jev judgments.

    Answers are advisory, not verified truth or approval to execute an action.
    This resource does not retrieve sources or retain a queryable judgment history.
    """

    def __init__(self, http: HTTPClient):
        self._http = http

    @overload
    def create(
        self,
        *,
        mode: Literal["decide"],
        state: str | dict[str, Any] | list[Any],
        questions: dict[str, JudgmentQuestion],
        user_id: str | None = None,
    ) -> Judgment: ...

    @overload
    def create(
        self,
        *,
        mode: Literal["verify"],
        claims: list[JudgmentClaim],
        evidence: list[JudgmentEvidence],
        user_id: str | None = None,
    ) -> Judgment: ...

    def create(
        self,
        *,
        mode: Literal["decide", "verify"],
        state: str | dict[str, Any] | list[Any] | None = None,
        questions: dict[str, JudgmentQuestion] | None = None,
        claims: list[JudgmentClaim] | None = None,
        evidence: list[JudgmentEvidence] | None = None,
        user_id: str | None = None,
    ) -> Judgment:
        """Judge typed questions, or check claims against explicitly linked evidence.

        ``decide`` requires ``state`` and ``questions``. ``verify`` requires
        ``claims`` and ``evidence``; each claim links evidence by ``evidence_ids``.
        Choice/Score confidence measures distribution concentration, not truth.
        A Noul is P(yes), without a separate confidence. Service failures raise
        normal SDK exceptions and never produce an approving fallback answer.
        """
        response = self._http.request(
            "POST",
            "/judgments",
            json=_build_params(
                mode=mode,
                state=state,
                questions=questions,
                claims=claims,
                evidence=evidence,
                user_id=user_id,
            ),
        )
        return Judgment.from_dict(response.json())
