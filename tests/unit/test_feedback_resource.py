"""Unit tests for client.feedback.create."""

from __future__ import annotations

from m8tes import M8tes
from m8tes._http import HTTPClient


class _Resp:
    def __init__(self, payload: dict):
        self._payload = payload

    def json(self) -> dict:
        return self._payload


def test_feedback_create_posts_message_and_run_id():
    calls: list[tuple[str, str, dict]] = []

    class _Http(HTTPClient):
        def __init__(self) -> None:
            pass

        def request(self, method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
            calls.append((method, path, kwargs.get("json") or {}))
            return _Resp(
                {
                    "id": 9,
                    "title": "stalled",
                    "run_id": 42,
                    "created_at": "2026-09-27T12:00:00Z",
                }
            )

    client = M8tes.__new__(M8tes)
    client._http = _Http()  # type: ignore[attr-defined]
    from m8tes._resources.feedback import FeedbackResource

    client.feedback = FeedbackResource(client._http)  # type: ignore[attr-defined]
    result = client.feedback.create(message="stalled on connect", run_id=42, user_id="customer_123")
    assert calls == [
        (
            "POST",
            "/feedback/",
            {"message": "stalled on connect", "run_id": 42, "user_id": "customer_123"},
        )
    ]
    assert result.id == 9
    assert result.run_id == 42
