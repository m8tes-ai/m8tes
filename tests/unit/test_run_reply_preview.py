from m8tes._types import Run


def test_run_deserializes_reply_request_and_message_preview():
    run = Run.from_dict(
        {
            "id": 1,
            "status": "completed",
            "needs_reply": True,
            "closing_preview": "A simpler email",
            "latest_message_preview": "Reply yes to proceed.",
        }
    )
    assert run.needs_reply is True
    assert run.latest_message_preview == "Reply yes to proceed."
    assert run.closing_preview == "A simpler email"


def test_old_run_response_defaults_to_no_reply_request():
    run = Run.from_dict({"id": 1, "status": "completed"})
    assert run.needs_reply is False
    assert run.latest_message_preview is None
