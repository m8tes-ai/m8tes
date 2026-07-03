"""Tests for v2 SDK resource classes — verify correct HTTP calls and response parsing."""

import json

import pytest
import responses

from m8tes._exceptions import NotFoundError
from m8tes._http import HTTPClient
from m8tes._resources.apps import Apps
from m8tes._resources.audit_logs import AuditLogs
from m8tes._resources.bridges import Bridges
from m8tes._resources.memories import Memories
from m8tes._resources.permissions import Permissions
from m8tes._resources.runs import Runs
from m8tes._resources.tasks import Tasks, TaskTriggers
from m8tes._resources.teammates import Teammates
from m8tes._streaming import RunStream
from m8tes._types import (
    App,
    AppConnectionInitiation,
    AppConnectionResult,
    AuditLog,
    PermissionMode,
    PermissionRequest,
    Run,
    RunFile,
    SyncPage,
    Task,
    Teammate,
    TeammateWebhook,
    Trigger,
)

BASE = "https://api.test/v2"


@pytest.fixture
def http():
    return HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)


# ── Teammates ────────────────────────────────────────────────────────


class TestTeammates:
    @responses.activate
    def test_create(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/teammates/",
            json={
                "id": 1,
                "name": "Bot",
                "default_permission_mode": "autonomous",
                "status": "enabled",
                "tools": [],
                "created_at": "",
                "updated_at": "",
            },
            status=201,
        )
        t = Teammates(http).create(name="Bot")
        assert isinstance(t, Teammate)
        assert t.id == 1
        body = json.loads(responses.calls[0].request.body)
        assert body == {"name": "Bot"}

    @responses.activate
    def test_create_with_all_fields(self, http):
        responses.add(
            responses.POST, f"{BASE}/teammates/", json={"id": 2, "name": "Full"}, status=201
        )
        Teammates(http).create(
            name="Full",
            tools=["gmail"],
            instructions="Help",
            role="support",
            goals="Resolve",
            user_id="u_1",
            metadata={"k": "v"},
            allowed_senders=["@acme.com"],
            default_permission_mode="approval",
        )
        body = json.loads(responses.calls[0].request.body)
        assert body["tools"] == ["gmail"]
        assert body["allowed_senders"] == ["@acme.com"]
        assert body["default_permission_mode"] == "approval"

    @responses.activate
    def test_create_with_model(self, http):
        responses.add(responses.POST, f"{BASE}/teammates/", json={"id": 4, "name": "M"}, status=201)
        Teammates(http).create(name="M", model="sonnet")
        body = json.loads(responses.calls[0].request.body)
        assert body["model"] == "sonnet"

    @responses.activate
    def test_create_with_imessage_fields(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/teammates/",
            json={
                "id": 3,
                "name": "Messages Bot",
                "inbound_imessage_enabled": True,
                "imessage_chat_guid": "iMessage;-;+15551231234",
            },
            status=201,
        )
        teammate = Teammates(http).create(
            name="Messages Bot",
            inbound_imessage_enabled=True,
            imessage_chat_guid="iMessage;-;+15551231234",
        )
        body = json.loads(responses.calls[0].request.body)
        assert body["inbound_imessage_enabled"] is True
        assert body["imessage_chat_guid"] == "iMessage;-;+15551231234"
        assert teammate.inbound_imessage_enabled is True
        assert teammate.imessage_chat_guid == "iMessage;-;+15551231234"

    @responses.activate
    def test_list(self, http):
        responses.add(
            responses.GET,
            f"{BASE}/teammates/",
            json={"data": [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}], "has_more": False},
        )
        result = Teammates(http).list()
        assert isinstance(result, SyncPage)
        assert len(result.data) == 2
        assert all(isinstance(t, Teammate) for t in result.data)
        assert result.has_more is False

    @responses.activate
    def test_list_with_user_id(self, http):
        responses.add(responses.GET, f"{BASE}/teammates/", json={"data": [], "has_more": False})
        Teammates(http).list(user_id="u_1")
        assert "user_id=u_1" in responses.calls[0].request.url

    @responses.activate
    def test_get(self, http):
        responses.add(responses.GET, f"{BASE}/teammates/42", json={"id": 42, "name": "Bot"})
        t = Teammates(http).get(42)
        assert t.id == 42

    @responses.activate
    def test_get_forwards_user_id(self, http):
        responses.add(responses.GET, f"{BASE}/teammates/42", json={"id": 42, "name": "Bot"})
        Teammates(http).get(42, user_id="alice")
        assert responses.calls[0].request.params.get("user_id") == "alice"

    @responses.activate
    def test_update_and_delete_forward_user_id(self, http):
        responses.add(responses.PATCH, f"{BASE}/teammates/1", json={"id": 1, "name": "N"})
        responses.add(responses.DELETE, f"{BASE}/teammates/1", status=204)
        Teammates(http).update(1, user_id="alice", name="N")
        assert responses.calls[0].request.params.get("user_id") == "alice"
        Teammates(http).delete(1, user_id="alice")
        assert responses.calls[1].request.params.get("user_id") == "alice"

    @responses.activate
    def test_update(self, http):
        responses.add(responses.PATCH, f"{BASE}/teammates/1", json={"id": 1, "name": "New"})
        t = Teammates(http).update(1, name="New")
        assert t.name == "New"

    @responses.activate
    def test_update_sends_only_provided_fields(self, http):
        responses.add(responses.PATCH, f"{BASE}/teammates/1", json={"id": 1, "name": "X"})
        Teammates(http).update(
            1,
            name="X",
            tools=["gmail"],
            allowed_senders=["@a.com"],
            default_permission_mode="plan",
        )
        body = json.loads(responses.calls[0].request.body)
        assert body == {
            "name": "X",
            "tools": ["gmail"],
            "allowed_senders": ["@a.com"],
            "default_permission_mode": "plan",
        }

    @responses.activate
    def test_update_with_model_sends_only_model(self, http):
        responses.add(responses.PATCH, f"{BASE}/teammates/1", json={"id": 1, "name": "X"})
        Teammates(http).update(1, model="sonnet")
        body = json.loads(responses.calls[0].request.body)
        assert body == {"model": "sonnet"}

    @responses.activate
    def test_update_model_explicit_none_sends_null_to_clear(self, http):
        """model=None must send JSON null — the documented clear-to-platform-default.

        Deliberately unlike other optional fields (omit-if-None): the v2 contract
        makes null a meaningful model state (D4).
        """
        responses.add(responses.PATCH, f"{BASE}/teammates/1", json={"id": 1, "name": "X"})
        Teammates(http).update(1, model=None)
        body = json.loads(responses.calls[0].request.body)
        assert body == {"model": None}

    @responses.activate
    def test_update_without_model_omits_the_key(self, http):
        responses.add(responses.PATCH, f"{BASE}/teammates/1", json={"id": 1, "name": "X"})
        Teammates(http).update(1, name="X")
        body = json.loads(responses.calls[0].request.body)
        assert "model" not in body

    @responses.activate
    def test_update_can_set_imessage_fields(self, http):
        responses.add(
            responses.PATCH,
            f"{BASE}/teammates/1",
            json={
                "id": 1,
                "name": "Bot",
                "inbound_imessage_enabled": True,
                "imessage_chat_guid": "iMessage;-;+15551231234",
            },
        )
        teammate = Teammates(http).update(
            1,
            inbound_imessage_enabled=True,
            imessage_chat_guid="iMessage;-;+15551231234",
        )
        body = json.loads(responses.calls[0].request.body)
        assert body == {
            "inbound_imessage_enabled": True,
            "imessage_chat_guid": "iMessage;-;+15551231234",
        }
        assert teammate.inbound_imessage_enabled is True
        assert teammate.imessage_chat_guid == "iMessage;-;+15551231234"

    @responses.activate
    def test_delete(self, http):
        responses.add(responses.DELETE, f"{BASE}/teammates/1", status=204)
        Teammates(http).delete(1)
        assert responses.calls[0].request.method == "DELETE"

    @responses.activate
    def test_enable_webhook(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/teammates/1/webhook",
            json={"enabled": True, "url": "https://api.m8tes.ai/api/v1/webhooks/mates/1/tok_abc"},
            status=201,
        )
        result = Teammates(http).enable_webhook(1)
        assert isinstance(result, TeammateWebhook)
        assert result.enabled is True
        assert "tok_abc" in result.url

    @responses.activate
    def test_disable_webhook(self, http):
        responses.add(responses.DELETE, f"{BASE}/teammates/1/webhook", status=204)
        Teammates(http).disable_webhook(1)
        assert responses.calls[0].request.method == "DELETE"

    @responses.activate
    def test_enable_webhook_not_found(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/teammates/999/webhook",
            json={"error": {"message": "Teammate not found"}},
            status=404,
        )
        with pytest.raises(NotFoundError):
            Teammates(http).enable_webhook(999)

    @responses.activate
    def test_enable_email_inbox(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/teammates/1/email-inbox",
            json={"enabled": True, "address": "abc123@notifications.m8tes.ai"},
            status=201,
        )
        from m8tes._types import EmailInbox

        result = Teammates(http).enable_email_inbox(1)
        assert isinstance(result, EmailInbox)
        assert result.enabled is True
        assert result.address == "abc123@notifications.m8tes.ai"

    @responses.activate
    def test_disable_email_inbox(self, http):
        responses.add(responses.DELETE, f"{BASE}/teammates/1/email-inbox", status=204)
        Teammates(http).disable_email_inbox(1)
        assert responses.calls[0].request.method == "DELETE"


# ── Runs ─────────────────────────────────────────────────────────────


class TestAuditLogs:
    @responses.activate
    def test_list(self, http):
        responses.add(
            responses.GET,
            f"{BASE}/audit-logs/",
            json={
                "data": [
                    {
                        "id": 1,
                        "method": "POST",
                        "path": "/api/v2/runs",
                        "status_code": 200,
                        "duration_ms": 45,
                        "action": "create",
                        "resource_type": "run",
                        "resource_id": None,
                        "api_key_prefix": "m8_test_pref",
                        "created_at": "2026-03-05T10:00:00Z",
                    }
                ],
                "has_more": False,
            },
        )
        page = AuditLogs(http).list()
        assert isinstance(page, SyncPage)
        assert len(page.data) == 1
        assert isinstance(page.data[0], AuditLog)
        assert page.data[0].resource_type == "run"

    @responses.activate
    def test_list_with_filters(self, http):
        responses.add(
            responses.GET,
            f"{BASE}/audit-logs/",
            json={"data": [], "has_more": False},
        )
        AuditLogs(http).list(
            action="create",
            resource_type="run",
            method="post",
            status_code=201,
            limit=10,
            starting_after=5,
        )
        url = responses.calls[0].request.url
        assert "action=create" in url
        assert "resource_type=run" in url
        assert "method=POST" in url
        assert "status_code=201" in url
        assert "limit=10" in url
        assert "starting_after=5" in url


class TestRuns:
    @responses.activate
    def test_create_streaming(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/runs/",
            body="data: {}\n\n",
            status=200,
            content_type="text/event-stream",
        )
        result = Runs(http).create(message="Do X")
        assert isinstance(result, RunStream)
        result._response.close()

    @responses.activate
    def test_stream_join(self, http):
        """runs.stream(run_id) GETs the join endpoint and returns a RunStream (M4)."""
        responses.add(
            responses.GET,
            f"{BASE}/runs/42/stream",
            body="data: {}\n\n",
            status=200,
            content_type="text/event-stream",
        )
        result = Runs(http).stream(42)
        assert isinstance(result, RunStream)
        assert responses.calls[0].request.url == f"{BASE}/runs/42/stream"
        result._response.close()

    @responses.activate
    def test_create_non_streaming(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/runs/",
            json={"id": 1, "status": "running"},
        )
        result = Runs(http).create(message="Do X", stream=False)
        assert isinstance(result, Run)
        assert result.id == 1

    @responses.activate
    def test_create_with_all_fields(self, http):
        responses.add(responses.POST, f"{BASE}/runs/", json={"id": 1})
        Runs(http).create(
            message="Do",
            teammate_id=1,
            tools=["slack"],
            stream=False,
            name="Bot",
            instructions="Help",
            user_id="u_1",
            metadata={"k": "v"},
        )
        body = json.loads(responses.calls[0].request.body)
        assert body["teammate_id"] == 1
        assert body["stream"] is False

    @responses.activate
    def test_create_can_disable_task_setup_tools(self, http):
        responses.add(responses.POST, f"{BASE}/runs/", json={"id": 1, "status": "running"})
        Runs(http).create(message="Do X", stream=False, task_setup_tools=False)
        body = json.loads(responses.calls[0].request.body)
        assert body["task_setup_tools"] is False

    @responses.activate
    def test_create_can_disable_feedback(self, http):
        responses.add(responses.POST, f"{BASE}/runs/", json={"id": 1, "status": "running"})
        Runs(http).create(message="Do X", stream=False, feedback=False)
        body = json.loads(responses.calls[0].request.body)
        assert body["feedback"] is False

    @responses.activate
    def test_create_with_model(self, http):
        responses.add(responses.POST, f"{BASE}/runs/", json={"id": 1, "status": "running"})
        responses.add(responses.POST, f"{BASE}/runs/", json={"id": 2, "status": "running"})
        Runs(http).create(message="Do X", stream=False, model="opus")
        assert json.loads(responses.calls[0].request.body)["model"] == "opus"
        Runs(http).create(message="Do X", stream=False)
        assert "model" not in json.loads(responses.calls[1].request.body)

    @responses.activate
    def test_create_accepts_permission_mode_enum(self, http):
        responses.add(responses.POST, f"{BASE}/runs/", json={"id": 1, "status": "running"})
        Runs(http).create(
            message="Do X",
            stream=False,
            human_in_the_loop=True,
            permission_mode=PermissionMode.APPROVAL,
        )
        body = json.loads(responses.calls[0].request.body)
        assert body["permission_mode"] == "approval"

    @responses.activate
    def test_list(self, http):
        responses.add(
            responses.GET,
            f"{BASE}/runs/",
            json={"data": [{"id": 1}, {"id": 2}], "has_more": False},
        )
        result = Runs(http).list()
        assert len(result.data) == 2

    @responses.activate
    def test_get(self, http):
        responses.add(
            responses.GET,
            f"{BASE}/runs/42",
            json={"id": 42, "status": "completed", "output": "Done"},
        )
        r = Runs(http).get(42)
        assert r.output == "Done"

    @responses.activate
    def test_reply_streaming(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/runs/1/reply",
            body="data: {}\n\n",
            content_type="text/event-stream",
        )
        result = Runs(http).reply(1, message="More")
        assert isinstance(result, RunStream)
        result._response.close()

    @responses.activate
    def test_reply_non_streaming(self, http):
        responses.add(responses.POST, f"{BASE}/runs/1/reply", json={"id": 1})
        result = Runs(http).reply(1, message="More", stream=False)
        assert isinstance(result, Run)

    @responses.activate
    def test_reply_can_override_task_setup_tools(self, http):
        responses.add(responses.POST, f"{BASE}/runs/1/reply", json={"id": 1})
        Runs(http).reply(1, message="More", stream=False, task_setup_tools=False)
        body = json.loads(responses.calls[0].request.body)
        assert body["task_setup_tools"] is False

    @responses.activate
    def test_reply_can_override_feedback(self, http):
        responses.add(responses.POST, f"{BASE}/runs/1/reply", json={"id": 1})
        Runs(http).reply(1, message="More", stream=False, feedback=False)
        body = json.loads(responses.calls[0].request.body)
        assert body["feedback"] is False

    @responses.activate
    def test_retry_returns_new_run(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/runs/42/retry",
            json={"id": 99, "status": "running", "retry_of_run_id": 42, "retry_count": 1},
            status=201,
        )
        run = Runs(http).retry(42)
        assert isinstance(run, Run)
        assert run.id == 99 and run.retry_of_run_id == 42 and run.retry_count == 1

    @responses.activate
    def test_retry_passes_confirm(self, http):
        responses.add(responses.POST, f"{BASE}/runs/42/retry", json={"id": 99})
        Runs(http).retry(42, confirm=True)
        assert "confirm=true" in responses.calls[0].request.url

    @responses.activate
    def test_retry_needs_confirmation_surfaces_code(self, http):
        from m8tes._exceptions import ConflictError

        responses.add(
            responses.POST,
            f"{BASE}/runs/42/retry",
            json={"error": {"code": "retry_needs_confirmation", "message": "may repeat"}},
            status=409,
        )
        with pytest.raises(ConflictError) as exc:
            Runs(http).retry(42)
        assert exc.value.code == "retry_needs_confirmation"

    @responses.activate
    def test_cancel(self, http):
        responses.add(
            responses.POST, f"{BASE}/runs/1/cancel", json={"id": 1, "status": "cancelled"}
        )
        r = Runs(http).cancel(1)
        assert r.status == "cancelled"

    @responses.activate
    def test_update_permission_mode(self, http):
        responses.add(
            responses.PATCH,
            f"{BASE}/runs/1/permission-mode",
            json={"permission_mode": "approval"},
            status=200,
        )
        result = Runs(http).update_permission_mode(1, permission_mode="approval")
        assert result.permission_mode == "approval"
        body = json.loads(responses.calls[0].request.body)
        assert body == {"permission_mode": "approval"}

    @responses.activate
    def test_update_permission_mode_accepts_enum(self, http):
        responses.add(
            responses.PATCH,
            f"{BASE}/runs/1/permission-mode",
            json={"permission_mode": "plan"},
            status=200,
        )
        result = Runs(http).update_permission_mode(1, permission_mode=PermissionMode.PLAN)
        assert result.permission_mode == "plan"
        body = json.loads(responses.calls[0].request.body)
        assert body == {"permission_mode": "plan"}

    @responses.activate
    def test_permissions(self, http):
        responses.add(
            responses.GET,
            f"{BASE}/runs/1/permissions",
            json=[
                {"request_id": "req_1", "tool_name": "gmail", "status": "pending"},
                {"request_id": "req_2", "tool_name": "slack", "status": "resolved"},
            ],
        )
        result = Runs(http).permissions(1)
        assert len(result) == 2
        assert all(isinstance(r, PermissionRequest) for r in result)
        assert result[0].tool_name == "gmail"
        assert result[1].status == "resolved"

    @responses.activate
    def test_approve_allow(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/runs/1/approve",
            json={
                "request_id": "req_1",
                "tool_name": "gmail",
                "status": "allowed",
            },
        )
        result = Runs(http).approve(1, request_id="req_1", decision="allow")
        assert isinstance(result, PermissionRequest)
        assert result.status == "allowed"
        body = json.loads(responses.calls[0].request.body)
        assert body == {"request_id": "req_1", "decision": "allow", "remember": False}

    @responses.activate
    def test_approve_deny_with_remember(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/runs/1/approve",
            json={
                "request_id": "req_1",
                "tool_name": "gmail",
                "status": "denied",
            },
        )
        Runs(http).approve(1, request_id="req_1", decision="deny", remember=True)
        body = json.loads(responses.calls[0].request.body)
        assert body == {"request_id": "req_1", "decision": "deny", "remember": True}

    @responses.activate
    def test_answer_question(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/runs/1/answer",
            json={"status": "ok", "resumed": True},
        )
        result = Runs(http).answer(1, answers={"What priority?": "High"})
        assert result == {"status": "ok", "resumed": True}
        body = json.loads(responses.calls[0].request.body)
        assert body == {"answers": {"What priority?": "High"}}

    @responses.activate
    def test_create_with_hitl_true(self, http):
        """human_in_the_loop=True is non-default, so it IS sent in body."""
        responses.add(responses.POST, f"{BASE}/runs/", json={"id": 1, "status": "running"})
        Runs(http).create(message="Do X", stream=False, human_in_the_loop=True)
        body = json.loads(responses.calls[0].request.body)
        assert body["human_in_the_loop"] is True

    @responses.activate
    def test_create_default_hitl_not_sent(self, http):
        """human_in_the_loop omitted stays omitted in the body."""
        responses.add(responses.POST, f"{BASE}/runs/", json={"id": 1, "status": "running"})
        Runs(http).create(message="Do X", stream=False)
        body = json.loads(responses.calls[0].request.body)
        assert "human_in_the_loop" not in body

    @responses.activate
    def test_create_explicit_false_hitl_is_sent(self, http):
        """Explicit human_in_the_loop=False is serialized for override behavior."""
        responses.add(responses.POST, f"{BASE}/runs/", json={"id": 1, "status": "running"})
        Runs(http).create(message="Do X", stream=False, human_in_the_loop=False)
        body = json.loads(responses.calls[0].request.body)
        assert body["human_in_the_loop"] is False

    @responses.activate
    def test_create_explicit_autonomous_permission_mode_is_sent(self, http):
        """Explicit autonomous override is serialized."""
        responses.add(responses.POST, f"{BASE}/runs/", json={"id": 1, "status": "running"})
        Runs(http).create(message="Do X", stream=False, permission_mode="autonomous")
        body = json.loads(responses.calls[0].request.body)
        assert body["permission_mode"] == "autonomous"

    @responses.activate
    def test_list_files(self, http):
        responses.add(
            responses.GET,
            f"{BASE}/runs/1/files",
            json=[{"name": "report.csv", "size": 1024}, {"name": "chart.png", "size": 2048}],
        )
        files = Runs(http).list_files(1)
        assert len(files) == 2
        assert all(isinstance(f, RunFile) for f in files)
        assert files[0].name == "report.csv"
        assert files[1].size == 2048

    @responses.activate
    def test_list_files_empty(self, http):
        responses.add(responses.GET, f"{BASE}/runs/1/files", json=[])
        assert Runs(http).list_files(1) == []

    @responses.activate
    def test_download_file(self, http):
        responses.add(
            responses.GET,
            f"{BASE}/runs/1/files/report.csv/download",
            body=b"col1,col2\na,b\n",
            content_type="text/csv",
        )
        content = Runs(http).download_file(1, "report.csv")
        assert content == b"col1,col2\na,b\n"

    @responses.activate
    def test_list_files_not_found(self, http):
        responses.add(
            responses.GET,
            f"{BASE}/runs/999/files",
            json={"error": {"message": "Run not found"}},
            status=404,
        )
        with pytest.raises(NotFoundError):
            Runs(http).list_files(999)

    @responses.activate
    def test_download_file_not_found(self, http):
        responses.add(
            responses.GET,
            f"{BASE}/runs/1/files/missing.csv/download",
            json={"error": {"message": "File not found"}},
            status=404,
        )
        with pytest.raises(NotFoundError):
            Runs(http).download_file(1, "missing.csv")


# ── Convenience helpers ──────────────────────────────────────────────


class TestRunConvenienceHelpers:
    @responses.activate
    def test_create_and_wait(self, http):
        """create_and_wait calls create(stream=False) then polls until completed."""
        # Mock create (returns running)
        responses.add(responses.POST, f"{BASE}/runs/", json={"id": 1, "status": "running"})
        # Mock poll (returns completed)
        responses.add(
            responses.GET, f"{BASE}/runs/1", json={"id": 1, "status": "completed", "output": "done"}
        )
        run = Runs(http).create_and_wait(message="Do X")
        assert isinstance(run, Run)
        assert run.status == "completed"
        # Verify create was called with stream=False
        body = json.loads(responses.calls[0].request.body)
        assert body["stream"] is False

    @responses.activate
    def test_reply_and_wait(self, http):
        """reply_and_wait calls reply(stream=False) then polls until completed."""
        responses.add(responses.POST, f"{BASE}/runs/1/reply", json={"id": 2, "status": "running"})
        responses.add(
            responses.GET, f"{BASE}/runs/2", json={"id": 2, "status": "completed", "output": "ok"}
        )
        run = Runs(http).reply_and_wait(1, message="More")
        assert isinstance(run, Run)
        assert run.status == "completed"

    @responses.activate
    def test_stream_text(self, http):
        """stream_text yields only text delta strings."""
        sse = (
            'data: {"type": "text-delta", "delta": "Hello"}\n\n'
            'data: {"type": "tool-call-begin", "toolName": "gmail"}\n\n'
            'data: {"type": "text-delta", "delta": " world"}\n\n'
            'data: {"type": "finish", "finishReason": "end_turn"}\n\n'
        )
        responses.add(
            responses.POST,
            f"{BASE}/runs/",
            body=sse,
            content_type="text/event-stream",
        )
        chunks = list(Runs(http).stream_text(message="Do X"))
        assert chunks == ["Hello", " world"]


# ── Tasks (advanced) ─────────────────────────────────────────────────


class TestTasks:
    @responses.activate
    def test_get_update_delete_forward_user_id(self, http):
        task_json = {"id": 5, "teammate_id": 2, "instructions": "x"}
        responses.add(responses.GET, f"{BASE}/tasks/5", json=task_json)
        responses.add(responses.PATCH, f"{BASE}/tasks/5", json=task_json)
        responses.add(responses.DELETE, f"{BASE}/tasks/5", status=204)
        Tasks(http).get(5, user_id="alice")
        assert responses.calls[0].request.params.get("user_id") == "alice"
        Tasks(http).update(5, user_id="alice", name="N")
        assert responses.calls[1].request.params.get("user_id") == "alice"
        Tasks(http).delete(5, user_id="alice")
        assert responses.calls[2].request.params.get("user_id") == "alice"

    @responses.activate
    def test_enable_webhook(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/tasks/1/webhook",
            json={"enabled": True, "url": "https://api.m8tes.ai/api/v1/webhooks/tasks/1/whk_abc"},
            status=201,
        )
        result = Tasks(http).enable_webhook(1)
        assert isinstance(result, TeammateWebhook)
        assert result.enabled is True
        assert "whk_abc" in result.url

    @responses.activate
    def test_disable_webhook(self, http):
        responses.add(responses.DELETE, f"{BASE}/tasks/1/webhook", status=204)
        Tasks(http).disable_webhook(1)
        assert responses.calls[0].request.method == "DELETE"

    @responses.activate
    def test_create(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/tasks/",
            json={"id": 1, "teammate_id": 2, "instructions": "Do X"},
            status=201,
        )
        t = Tasks(http).create(teammate_id=2, instructions="Do X")
        assert isinstance(t, Task)
        assert t.teammate_id == 2

    @responses.activate
    def test_create_with_user_id(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/tasks/",
            json={"id": 1, "teammate_id": 2, "instructions": "Do", "user_id": "cust_1"},
            status=201,
        )
        t = Tasks(http).create(teammate_id=2, instructions="Do", user_id="cust_1")
        assert t.user_id == "cust_1"
        body = json.loads(responses.calls[0].request.body)
        assert body["user_id"] == "cust_1"

    @responses.activate
    def test_list(self, http):
        responses.add(
            responses.GET,
            f"{BASE}/tasks/",
            json={"data": [{"id": 1, "teammate_id": 2, "instructions": "Do"}], "has_more": False},
        )
        result = Tasks(http).list()
        assert len(result.data) == 1

    @responses.activate
    def test_get(self, http):
        responses.add(
            responses.GET, f"{BASE}/tasks/1", json={"id": 1, "teammate_id": 2, "instructions": "Do"}
        )
        t = Tasks(http).get(1)
        assert t.id == 1

    @responses.activate
    def test_update(self, http):
        responses.add(
            responses.PATCH,
            f"{BASE}/tasks/1",
            json={"id": 1, "teammate_id": 2, "instructions": "New"},
        )
        t = Tasks(http).update(1, instructions="New")
        assert t.instructions == "New"

    @responses.activate
    def test_update_sends_only_provided_fields(self, http):
        responses.add(
            responses.PATCH,
            f"{BASE}/tasks/1",
            json={"id": 1, "teammate_id": 2, "instructions": "X"},
        )
        Tasks(http).update(1, instructions="X", expected_output="Y")
        body = json.loads(responses.calls[0].request.body)
        assert body == {"instructions": "X", "expected_output": "Y"}

    @responses.activate
    def test_run_non_streaming(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/tasks/10/runs",
            json={
                "id": 42,
                "teammate_id": 1,
                "status": "running",
                "created_at": "2026-01-01T00:00:00Z",
            },
        )
        run = Tasks(http).run(10, stream=False)
        assert isinstance(run, Run)
        assert run.id == 42
        body = json.loads(responses.calls[0].request.body)
        assert body["stream"] is False

    @responses.activate
    def test_run_streaming(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/tasks/10/runs",
            body="data: {}\n\n",
            content_type="text/event-stream",
        )
        result = Tasks(http).run(10, stream=True)
        assert isinstance(result, RunStream)
        result._response.close()

    @responses.activate
    def test_run_passes_optional_fields(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/tasks/5/runs",
            json={"id": 1, "status": "running", "created_at": "2026-01-01T00:00:00Z"},
        )
        Tasks(http).run(
            5, stream=False, user_id="u_1", metadata={"k": "v"}, permission_mode="approval"
        )
        body = json.loads(responses.calls[0].request.body)
        assert body["user_id"] == "u_1"
        assert body["metadata"] == {"k": "v"}
        assert body["permission_mode"] == "approval"

    @responses.activate
    def test_run_can_disable_task_setup_tools(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/tasks/10/runs",
            json={"id": 1, "status": "running", "created_at": "2026-01-01T00:00:00Z"},
        )
        Tasks(http).run(10, stream=False, task_setup_tools=False)
        body = json.loads(responses.calls[0].request.body)
        assert body["task_setup_tools"] is False

    @responses.activate
    def test_run_can_disable_feedback(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/tasks/10/runs",
            json={"id": 1, "status": "running", "created_at": "2026-01-01T00:00:00Z"},
        )
        Tasks(http).run(10, stream=False, feedback=False)
        body = json.loads(responses.calls[0].request.body)
        assert body["feedback"] is False

    @responses.activate
    def test_run_accepts_permission_mode_enum(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/tasks/10/runs",
            json={"id": 1, "status": "running", "created_at": "2026-01-01T00:00:00Z"},
        )
        Tasks(http).run(
            10,
            stream=False,
            human_in_the_loop=True,
            permission_mode=PermissionMode.APPROVAL,
        )
        body = json.loads(responses.calls[0].request.body)
        assert body["permission_mode"] == "approval"

    @responses.activate
    def test_run_with_hitl_true(self, http):
        """human_in_the_loop=True is non-default, so it IS sent in body."""
        responses.add(
            responses.POST,
            f"{BASE}/tasks/10/runs",
            json={"id": 1, "status": "running", "created_at": "2026-01-01T00:00:00Z"},
        )
        Tasks(http).run(10, stream=False, human_in_the_loop=True)
        body = json.loads(responses.calls[0].request.body)
        assert body["human_in_the_loop"] is True

    @responses.activate
    def test_run_default_hitl_not_sent(self, http):
        """human_in_the_loop omitted stays omitted in the body."""
        responses.add(
            responses.POST,
            f"{BASE}/tasks/10/runs",
            json={"id": 1, "status": "running", "created_at": "2026-01-01T00:00:00Z"},
        )
        Tasks(http).run(10, stream=False)
        body = json.loads(responses.calls[0].request.body)
        assert "human_in_the_loop" not in body

    @responses.activate
    def test_run_explicit_false_hitl_is_sent(self, http):
        """Explicit human_in_the_loop=False is serialized for task-run overrides."""
        responses.add(
            responses.POST,
            f"{BASE}/tasks/10/runs",
            json={"id": 1, "status": "running", "created_at": "2026-01-01T00:00:00Z"},
        )
        Tasks(http).run(10, stream=False, human_in_the_loop=False)
        body = json.loads(responses.calls[0].request.body)
        assert body["human_in_the_loop"] is False

    @responses.activate
    def test_run_explicit_autonomous_permission_mode_is_sent(self, http):
        """Explicit autonomous override is serialized for task runs."""
        responses.add(
            responses.POST,
            f"{BASE}/tasks/10/runs",
            json={"id": 1, "status": "running", "created_at": "2026-01-01T00:00:00Z"},
        )
        Tasks(http).run(10, stream=False, permission_mode="autonomous")
        body = json.loads(responses.calls[0].request.body)
        assert body["permission_mode"] == "autonomous"

    @responses.activate
    def test_run_with_model(self, http):
        """model is a per-run override: sent when provided, omitted otherwise."""
        responses.add(
            responses.POST,
            f"{BASE}/tasks/10/runs",
            json={"id": 1, "status": "running", "created_at": "2026-01-01T00:00:00Z"},
        )
        responses.add(
            responses.POST,
            f"{BASE}/tasks/10/runs",
            json={"id": 2, "status": "running", "created_at": "2026-01-01T00:00:00Z"},
        )
        Tasks(http).run(10, stream=False, model="opus")
        assert json.loads(responses.calls[0].request.body)["model"] == "opus"
        Tasks(http).run(10, stream=False)
        assert "model" not in json.loads(responses.calls[1].request.body)

    @responses.activate
    def test_delete(self, http):
        responses.add(responses.DELETE, f"{BASE}/tasks/1", status=204)
        Tasks(http).delete(1)


class TestTaskTriggers:
    @responses.activate
    def test_create_schedule(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/tasks/1/triggers/",
            json={"id": 10, "type": "schedule", "enabled": True, "cron": "0 9 * * 1"},
            status=201,
        )
        t = TaskTriggers(http).create(1, type="schedule", cron="0 9 * * 1")
        assert isinstance(t, Trigger)
        assert t.cron == "0 9 * * 1"

    @responses.activate
    def test_list(self, http):
        responses.add(
            responses.GET, f"{BASE}/tasks/1/triggers/", json=[{"id": 10, "type": "schedule"}]
        )
        result = TaskTriggers(http).list(1)
        assert len(result) == 1

    @responses.activate
    def test_delete(self, http):
        responses.add(responses.DELETE, f"{BASE}/tasks/1/triggers/10", status=204)
        TaskTriggers(http).delete(1, 10)


# ── Apps ─────────────────────────────────────────────────────────────


class TestApps:
    @responses.activate
    def test_list(self, http):
        responses.add(
            responses.GET,
            f"{BASE}/apps/",
            json={
                "data": [
                    {
                        "name": "gmail",
                        "display_name": "Gmail",
                        "category": "email",
                        "connected": False,
                    }
                ],
                "has_more": False,
            },
        )
        result = Apps(http).list(limit=2)
        assert len(result.data) == 1
        assert isinstance(result.data[0], App)
        assert result.data[0].name == "gmail"
        assert "limit=2" in responses.calls[0].request.url

    @responses.activate
    def test_list_auto_paging(self, http):
        responses.add(
            responses.GET,
            f"{BASE}/apps/",
            json={
                "data": [
                    {
                        "name": "gmail",
                        "display_name": "Gmail",
                        "category": "email",
                        "connected": True,
                    }
                ],
                "has_more": True,
            },
        )
        responses.add(
            responses.GET,
            f"{BASE}/apps/",
            json={
                "data": [
                    {
                        "name": "slack",
                        "display_name": "Slack",
                        "category": "chat",
                        "connected": False,
                    }
                ],
                "has_more": False,
            },
        )

        page = Apps(http).list(limit=1, user_id="cust_1")
        apps = list(page.auto_paging_iter())

        assert [app.name for app in apps] == ["gmail", "slack"]
        assert "starting_after=gmail" in responses.calls[1].request.url
        assert "user_id=cust_1" in responses.calls[1].request.url

    @responses.activate
    def test_connect(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/apps/gmail/connect",
            json={
                "authorization_url": "https://accounts.google.com/o/oauth2",
                "connection_id": "conn_1",
            },
            status=200,
        )
        result = Apps(http).connect("gmail", "https://myapp.com/callback", user_id="cust_1")
        assert isinstance(result, AppConnectionInitiation)
        assert result.authorization_url == "https://accounts.google.com/o/oauth2"
        assert result.connection_id == "conn_1"
        body = json.loads(responses.calls[0].request.body)
        assert body == {"redirect_uri": "https://myapp.com/callback", "user_id": "cust_1"}

    @responses.activate
    def test_connect_oauth(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/apps/gmail/connect",
            json={
                "authorization_url": "https://accounts.google.com/o/oauth2",
                "connection_id": "conn_oauth",
            },
            status=200,
        )
        result = Apps(http).connect_oauth("gmail", "https://myapp.com/callback", user_id="cust_1")
        assert isinstance(result, AppConnectionInitiation)
        assert result.connection_id == "conn_oauth"
        body = json.loads(responses.calls[0].request.body)
        assert body == {"redirect_uri": "https://myapp.com/callback", "user_id": "cust_1"}

    @responses.activate
    def test_connect_api_key(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/apps/gemini/connect/api-key",
            json={"status": "connected", "app": "gemini"},
            status=200,
        )
        result = Apps(http).connect_api_key("gemini", "sk_test_123", user_id="cust_1")
        assert isinstance(result, AppConnectionResult)
        assert result.status == "connected"
        body = json.loads(responses.calls[0].request.body)
        assert body == {"api_key": "sk_test_123", "user_id": "cust_1"}

    @responses.activate
    def test_connect_complete(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/apps/gmail/connect/complete",
            json={"status": "connected", "app": "gmail"},
            status=200,
        )
        result = Apps(http).connect_complete("gmail", "conn_1", user_id="cust_1")
        assert isinstance(result, AppConnectionResult)
        assert result.status == "connected"
        assert result.app == "gmail"
        body = json.loads(responses.calls[0].request.body)
        assert body == {"connection_id": "conn_1", "user_id": "cust_1"}

    @responses.activate
    def test_disconnect(self, http):
        responses.add(responses.DELETE, f"{BASE}/apps/gmail/connections", status=204)
        Apps(http).disconnect("gmail", user_id="cust_1")
        assert "user_id=cust_1" in responses.calls[0].request.url


# ── Memories ────────────────────────────────────────────────────────


class TestMemories:
    @responses.activate
    def test_auto_paging_iter(self, http):
        """Memories.list() must support auto_paging_iter across pages."""
        page1 = {
            "data": [{"id": 1, "content": "a", "user_id": "u1", "source": "api", "created_at": ""}],
            "has_more": True,
        }
        page2 = {
            "data": [{"id": 2, "content": "b", "user_id": "u1", "source": "api", "created_at": ""}],
            "has_more": False,
        }
        responses.add(responses.GET, f"{BASE}/memories/", json=page1, status=200)
        responses.add(responses.GET, f"{BASE}/memories/", json=page2, status=200)

        page = Memories(http).list(user_id="u1")
        items = list(page.auto_paging_iter())
        assert len(items) == 2
        assert items[0].content == "a"
        assert items[1].content == "b"
        # Second request should have starting_after=1
        assert "starting_after=1" in responses.calls[1].request.url


# ── Permissions ─────────────────────────────────────────────────────


class TestPermissions:
    @responses.activate
    def test_auto_paging_iter(self, http):
        """Permissions.list() must support auto_paging_iter across pages."""
        page1 = {
            "data": [{"id": 10, "user_id": "u1", "tool_name": "bash", "created_at": ""}],
            "has_more": True,
        }
        page2 = {
            "data": [{"id": 11, "user_id": "u1", "tool_name": "gmail", "created_at": ""}],
            "has_more": False,
        }
        responses.add(responses.GET, f"{BASE}/permissions/", json=page1, status=200)
        responses.add(responses.GET, f"{BASE}/permissions/", json=page2, status=200)

        page = Permissions(http).list(user_id="u1")
        items = list(page.auto_paging_iter())
        assert len(items) == 2
        assert items[0].tool_name == "bash"
        assert items[1].tool_name == "gmail"
        assert "starting_after=10" in responses.calls[1].request.url


class TestBridges:
    @responses.activate
    def test_create_returns_secret_once_never_password(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/bridges",
            json={
                "id": 5,
                "name": "my mac",
                "server_url": "https://bb.example.com",
                "status": "active",
                "created_at": "2026-05-29T00:00:00Z",
                "webhook_secret": "whsec_once",
            },
            status=201,
        )
        bridge = Bridges(http).create(
            server_url="https://bb.example.com", password="pw", name="my mac"
        )
        body = json.loads(responses.calls[0].request.body)
        assert body == {"name": "my mac", "server_url": "https://bb.example.com", "password": "pw"}
        assert bridge.id == 5
        assert bridge.webhook_secret == "whsec_once"
        # password is never present on the returned object
        assert not hasattr(bridge, "password")

    @responses.activate
    def test_create_with_owner_handle_and_connection_result(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/bridges",
            json={
                "id": 6,
                "name": "my mac",
                "server_url": "https://bb.example.com",
                "status": "active",
                "created_at": "2026-05-29T00:00:00Z",
                "owner_handle": "+15550001111",
                "webhook_secret": "whsec_once",
                "connection_ok": True,
                "connection_error": None,
            },
            status=201,
        )
        bridge = Bridges(http).create(
            server_url="https://bb.example.com", password="pw", owner_handle="+15550001111"
        )
        body = json.loads(responses.calls[0].request.body)
        assert body["owner_handle"] == "+15550001111"
        assert bridge.owner_handle == "+15550001111"
        assert bridge.connection_ok is True

    @responses.activate
    def test_test_endpoint(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/bridges/5/test",
            json={"ok": False, "detail": "BlueBubbles connection check failed (HTTP 401)"},
            status=200,
        )
        result = Bridges(http).test(5)
        assert result["ok"] is False
        assert "401" in result["detail"]
        assert responses.calls[0].request.method == "POST"

    @responses.activate
    def test_list(self, http):
        responses.add(
            responses.GET,
            f"{BASE}/bridges",
            json={
                "data": [
                    {
                        "id": 1,
                        "name": "a",
                        "server_url": "https://a",
                        "status": "active",
                        "created_at": "2026-05-29T00:00:00Z",
                    }
                ]
            },
            status=200,
        )
        bridges = Bridges(http).list()
        assert len(bridges) == 1
        assert bridges[0].id == 1
        assert bridges[0].webhook_secret is None  # not returned on list

    @responses.activate
    def test_rotate_secret_returns_new_secret(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/bridges/5/rotate-secret",
            json={
                "id": 5,
                "name": "m",
                "server_url": "https://a",
                "status": "active",
                "created_at": "2026-05-29T00:00:00Z",
                "webhook_secret": "whsec_new",
            },
            status=200,
        )
        bridge = Bridges(http).rotate_secret(5)
        assert bridge.webhook_secret == "whsec_new"

    @responses.activate
    def test_update_sends_only_provided(self, http):
        responses.add(
            responses.PATCH,
            f"{BASE}/bridges/5",
            json={
                "id": 5,
                "name": "renamed",
                "server_url": "https://a",
                "status": "disabled",
                "created_at": "2026-05-29T00:00:00Z",
            },
            status=200,
        )
        Bridges(http).update(5, name="renamed", status="disabled")
        body = json.loads(responses.calls[0].request.body)
        assert body == {"name": "renamed", "status": "disabled"}

    @responses.activate
    def test_delete(self, http):
        responses.add(responses.DELETE, f"{BASE}/bridges/5", status=204)
        Bridges(http).delete(5)
        assert responses.calls[0].request.method == "DELETE"

    @responses.activate
    def test_teammate_create_includes_bridge_fields(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/teammates/",
            json={
                "id": 9,
                "name": "bot",
                "inbound_imessage_enabled": True,
                "imessage_chat_guid": "g",
                "bridge_id": 5,
                "allowed_imessage_senders": ["+15551231234"],
            },
            status=201,
        )
        tm = Teammates(http).create(
            name="bot",
            inbound_imessage_enabled=True,
            imessage_chat_guid="g",
            bridge_id=5,
            allowed_imessage_senders=["+15551231234"],
        )
        body = json.loads(responses.calls[0].request.body)
        assert body["bridge_id"] == 5
        assert body["allowed_imessage_senders"] == ["+15551231234"]
        assert tm.bridge_id == 5
        assert tm.allowed_imessage_senders == ["+15551231234"]
