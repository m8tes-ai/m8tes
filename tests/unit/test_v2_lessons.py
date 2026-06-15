"""Tests for the task-lessons methods on the Tasks resource."""

import pytest
import responses

from m8tes._exceptions import NotFoundError
from m8tes._http import HTTPClient
from m8tes._resources.tasks import Tasks
from m8tes._types import LessonList

BASE = "https://api.test/v2"


def _http() -> HTTPClient:
    return HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)


@responses.activate
def test_list_lessons():
    responses.add(
        responses.GET,
        f"{BASE}/tasks/5/lessons",
        json={
            "data": [
                {
                    "id": "l1",
                    "text": "prefer concise replies",
                    "when_applicable": "drafting emails",
                    "created_at": "2026-01-01T00:00:00Z",
                    "last_reaffirmed_at": "2026-01-02T00:00:00Z",
                    "source_run_id": 99,
                    "reaffirm_count": 2,
                }
            ],
            "capacity_used": 1,
            "capacity_limit": 20,
        },
        status=200,
    )

    ll = Tasks(_http()).lessons(5)

    assert isinstance(ll, LessonList)
    assert ll.capacity_used == 1
    assert ll.capacity_limit == 20
    assert ll.data[0].id == "l1"
    assert ll.data[0].source_run_id == 99
    assert ll.data[0].reaffirm_count == 2


@responses.activate
def test_delete_lesson_returns_remaining():
    responses.add(
        responses.DELETE,
        f"{BASE}/tasks/5/lessons/l1",
        json={"data": [], "capacity_used": 0, "capacity_limit": 20},
        status=200,
    )

    ll = Tasks(_http()).delete_lesson(5, "l1")

    assert ll.capacity_used == 0
    assert ll.data == []


@responses.activate
def test_delete_lesson_not_found_raises():
    """Deleting an unknown lesson surfaces a typed NotFoundError."""
    responses.add(
        responses.DELETE,
        f"{BASE}/tasks/5/lessons/missing",
        json={"error": {"type": "not_found", "message": "Lesson not found", "code": 404}},
        status=404,
    )

    with pytest.raises(NotFoundError):
        Tasks(_http()).delete_lesson(5, "missing")


@responses.activate
def test_clear_lessons_sends_confirm():
    responses.add(
        responses.POST,
        f"{BASE}/tasks/5/lessons:clear",
        json={"data": [], "capacity_used": 0, "capacity_limit": 20},
        status=200,
    )

    ll = Tasks(_http()).clear_lessons(5)

    assert ll.capacity_used == 0
    # The destructive clear must pass the backend's required confirm=true gate.
    assert "confirm=true" in responses.calls[0].request.url
