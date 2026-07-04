"""The run detail/conversation/usage/tools surface hits REAL v1 endpoints.

Regression guard: services/runs.py shipped calling four endpoints that never
existed (/details, /conversation, /usage, /tools) — every `m8tes run get/usage/
conversation/tools` and the `mate task` run summary 404'd. The real endpoints
are /detail (flat metrics) and /messages (transcript); tool calls are derived
from message content blocks.
"""

from unittest.mock import Mock

from m8tes.services.runs import RunService


def _service_with(response):
    http = Mock()
    http.request.return_value = response
    svc = RunService(http)
    return svc, http


def test_get_details_hits_detail_endpoint_flat_shape():
    svc, http = _service_with({"id": 7, "message_count": 3, "total_tokens": 900})
    details = svc.get_details(7)
    http.request.assert_called_once_with("GET", "/api/v1/runs/7/detail")
    assert details["message_count"] == 3  # flat — no nested conversation/usage keys


def test_get_conversation_hits_messages_endpoint_list_response():
    svc, http = _service_with([{"role": "assistant", "content": "hi"}])
    messages = svc.get_conversation(7)
    http.request.assert_called_once_with("GET", "/api/v1/runs/7/messages")
    assert messages[0]["role"] == "assistant"


def test_get_usage_derives_from_detail():
    svc, http = _service_with(
        {"id": 7, "message_count": 2, "total_tokens": 500, "total_cost_usd": "0.0123"}
    )
    usage = svc.get_usage(7)
    http.request.assert_called_once_with("GET", "/api/v1/runs/7/detail")
    assert usage == {"message_count": 2, "total_tokens": 500, "total_cost_usd": "0.0123"}


def test_get_tool_executions_derived_from_content_blocks():
    svc, http = _service_with(
        [
            {
                "role": "assistant",
                "content": "",
                "content_blocks": [
                    {"type": "text", "text": "thinking"},
                    {"type": "tool_use", "name": "gmail_search", "input": {"q": "is:open"}},
                ],
            },
            {"role": "user", "content": "ok", "content_blocks": None},
        ]
    )
    tools = svc.get_tool_executions(7)
    http.request.assert_called_once_with("GET", "/api/v1/runs/7/messages")
    assert tools == [{"tool_name": "gmail_search", "arguments": {"q": "is:open"}}]
