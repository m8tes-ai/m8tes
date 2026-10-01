"""Run.needs_me_run: the caller's run-level mark, separate from message marks.

needs_me is derived (the run-level mark or any message mark), so a client that only
reads the flag cannot tell what clearing the last message mark leaves behind.
"""

from m8tes._types import Run


def test_run_deserializes_the_run_level_mark_apart_from_message_marks():
    message_only = Run.from_dict(
        {
            "id": 1,
            "status": "completed",
            "needs_me": True,
            "needs_me_run": False,
            "needs_me_message_ids": [42],
        }
    )
    assert message_only.needs_me is True
    assert message_only.needs_me_run is False
    assert message_only.needs_me_message_ids == [42]

    both = Run.from_dict(
        {
            "id": 2,
            "status": "completed",
            "needs_me": True,
            "needs_me_run": True,
            "needs_me_message_ids": [42],
        }
    )
    assert both.needs_me_run is True


def test_old_run_response_defaults_to_no_run_level_mark():
    run = Run.from_dict({"id": 1, "status": "completed"})
    assert run.needs_me_run is False
    assert run.needs_me is False
