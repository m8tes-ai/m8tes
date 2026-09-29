"""Feedback resource — send product feedback to the m8tes team."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._types import Feedback

if TYPE_CHECKING:
    from .._http import HTTPClient


class FeedbackResource:
    """client.feedback — submit operator product feedback (same as ``/feedback``)."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def create(
        self,
        *,
        message: str,
        run_id: int | None = None,
        title: str | None = None,
        user_id: str | None = None,
    ) -> Feedback:
        """Send feedback to the m8tes team, optionally attaching a run.

        The same chokepoint as typing ``/feedback …`` in chat — recorded in
        our DB and surfaced in Sentry + PostHog. Pass ``user_id`` when the
        account isolates end-users so an attached run must match that scope.
        """
        body: dict = {"message": message}
        if run_id is not None:
            body["run_id"] = run_id
        if title is not None:
            body["title"] = title
        if user_id is not None:
            body["user_id"] = user_id
        resp = self._http.request("POST", "/feedback/", json=body)
        return Feedback.from_dict(resp.json())
