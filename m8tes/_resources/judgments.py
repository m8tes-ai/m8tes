"""Advisory typed judgments over caller-provided state and evidence."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, overload

from .._http import IDEMPOTENCY_HEADER, seg
from .._types import Judgment, JudgmentClaim, JudgmentConnection, JudgmentEvidence, JudgmentQuestion
from ._utils import _build_params

if TYPE_CHECKING:
    from .._http import HTTPClient


class Judgments:
    """client.judgments — advisory Jev judgments with optional account funding.

    Answers are advisory, not verified truth or approval to execute an action.
    Successful results are retrievable for 30 days within their original user scope,
    unless account or run metadata-only retention disables answer storage.
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
        run_id: int | None = None,
        idempotency_key: str | None = None,
    ) -> Judgment: ...

    @overload
    def create(
        self,
        *,
        mode: Literal["verify"],
        claims: list[JudgmentClaim],
        evidence: list[JudgmentEvidence],
        user_id: str | None = None,
        run_id: int | None = None,
        idempotency_key: str | None = None,
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
        run_id: int | None = None,
        idempotency_key: str | None = None,
    ) -> Judgment:
        """Judge typed questions, or check claims against explicitly linked evidence.

        ``decide`` requires ``state`` and ``questions``. ``verify`` requires
        ``claims`` and ``evidence``; each claim links evidence by ``evidence_ids``.
        Choice/Score confidence measures distribution concentration, not truth.
        A Noul is P(yes), without a separate confidence. Service failures raise
        normal SDK exceptions and never produce an approving fallback answer.

        Reuse ``idempotency_key`` for the same operation for 24 hours. A replay
        keeps its original ID and cost; it does not incur another provider charge.
        Conflicting bodies and pending attempts raise ConflictError. Without a
        key this POST is never automatically retried. Evidence accepts either
        inline ``text`` or a scoped platform ``source`` reference, not both.
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
                run_id=run_id,
            ),
            headers={IDEMPOTENCY_HEADER: idempotency_key} if idempotency_key is not None else {},
        )
        return Judgment.from_dict(response.json())

    def get(self, judgment_id: str, *, user_id: str | None = None) -> Judgment:
        """Retrieve a successful result for 30 days, without calling the provider.

        Use the same ``user_id`` as creation. The returned cost is the original
        estimate, not an additional charge. Unknown results raise NotFoundError;
        pending or unsuccessful attempts raise ConflictError. Expired results
        and metadata-only retention return HTTP 410 (result_not_retained).
        """
        response = self._http.request(
            "GET",
            f"/judgments/{seg(judgment_id)}",
            params=_build_params(user_id=user_id),
        )
        return Judgment.from_dict(response.json())

    def configure(self, *, api_key: str) -> JudgmentConnection:
        """Store a write-only TypeSafe key for this entire m8tes account.

        Configure once from a trusted server: all end-user and agent judgments
        then use your TypeSafe account. Never pass the key in prompts/tool args.
        Invalid customer credentials never fall back to platform funding.
        """
        response = self._http.request("PUT", "/judgments/connection", json={"api_key": api_key})
        return JudgmentConnection.from_dict(response.json())

    def connection(self) -> JudgmentConnection:
        """Read connection/availability metadata without returning the API key."""
        response = self._http.request("GET", "/judgments/connection")
        return JudgmentConnection.from_dict(response.json())

    def disconnect(self) -> None:
        """Remove the account key; restore platform funding if it is available."""
        self._http.request("DELETE", "/judgments/connection")
