"""Tests for v2 SDK resource classes — verify correct HTTP calls and response parsing."""

import json

import pytest
import responses

from m8tes._exceptions import NotFoundError, RunFailedError
from m8tes._http import HTTPClient
from m8tes._resources.apps import Apps
from m8tes._resources.audit_logs import AuditLogs
from m8tes._resources.bridges import Bridges
from m8tes._resources.channels import Channels
from m8tes._resources.memories import Memories
from m8tes._resources.model_connections import ModelConnections
from m8tes._resources.permissions import Permissions
from m8tes._resources.runs import Runs
from m8tes._resources.tasks import Tasks, TaskTriggers
from m8tes._resources.teammates import Teammates
from m8tes._resources.triggers import Triggers
from m8tes._streaming import RunStream
from m8tes._types import (
    App,
    AppConnectionInitiation,
    AppConnectionResult,
    AuditLog,
    PermissionMode,
    PermissionRequest,
    Run,
    RunCheck,
    RunFile,
    RunOutcome,
    RunShare,
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


class TestModelConnections:
    @responses.activate
    def test_list_authorize_poll_cancel_and_disconnect(self, http):
        responses.add(
            responses.GET,
            f"{BASE}/model-connections/",
            json={"data": [], "has_more": False},
        )
        authorization = {
            "provider": "openai",
            "state": "opaque-state",
            "status": "pending",
            "authorization_url": "https://auth.openai.com/codex/device",
            "user_code": "ABCD-EFGH",
            "interval_seconds": 5,
        }
        responses.add(
            responses.POST,
            f"{BASE}/model-connections/openai/authorizations",
            json=authorization,
        )
        responses.add(
            responses.GET,
            f"{BASE}/model-connections/openai/authorizations/opaque-state",
            json={
                "provider": "openai",
                "state": "opaque-state",
                "status": "connected",
            },
        )
        responses.add(
            responses.POST,
            f"{BASE}/model-connections/gemini/authorizations/opaque-state",
            json={
                "provider": "gemini",
                "state": "opaque-state",
                "status": "connected",
            },
        )
        responses.add(
            responses.DELETE,
            f"{BASE}/model-connections/openai/authorizations/opaque-state",
            status=204,
        )
        responses.add(
            responses.DELETE,
            f"{BASE}/model-connections/claude",
            json={
                "provider": "claude",
                "display_name": "Claude",
                "connected": False,
            },
        )
        resource = ModelConnections(http)

        assert resource.list().data == []
        started = resource.authorize("openai")
        completed = resource.authorization_status("openai", started.state)
        pasted = resource.complete_authorization("gemini", started.state, code="pasted-google-code")
        resource.cancel_authorization("openai", started.state)
        disconnected = resource.disconnect("claude")

        assert started.user_code == "ABCD-EFGH"
        assert completed.status == "connected"
        assert pasted.status == "connected"
        assert disconnected.connected is False
        assert responses.calls[1].request.body in (None, b"", "")
        assert b"pasted-google-code" in (responses.calls[3].request.body or b"")

    @responses.activate
    def test_apply_default(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/model-connections/claude/apply-default",
            json={
                "provider": "claude",
                "model": "claude-opus-5",
                "affected_mate_count": 2,
            },
        )
        result = ModelConnections(http).apply_default("claude")
        assert result.provider == "claude"
        assert result.model == "claude-opus-5"
        assert result.affected_mate_count == 2


# ── Teammates ────────────────────────────────────────────────────────


class TestTeammates:
    @responses.activate
    def test_create(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/agents/",
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
        responses.add(responses.POST, f"{BASE}/agents/", json={"id": 2, "name": "Full"}, status=201)
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
        responses.add(responses.POST, f"{BASE}/agents/", json={"id": 4, "name": "M"}, status=201)
        Teammates(http).create(name="M", model="sonnet")
        body = json.loads(responses.calls[0].request.body)
        assert body["model"] == "sonnet"

    @responses.activate
    def test_create_with_imessage_fields(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/agents/",
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
            f"{BASE}/agents/",
            json={"data": [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}], "has_more": False},
        )
        result = Teammates(http).list()
        assert isinstance(result, SyncPage)
        assert len(result.data) == 2
        assert all(isinstance(t, Teammate) for t in result.data)
        assert result.has_more is False

    @responses.activate
    def test_list_with_user_id(self, http):
        responses.add(responses.GET, f"{BASE}/agents/", json={"data": [], "has_more": False})
        Teammates(http).list(user_id="u_1")
        assert "user_id=u_1" in responses.calls[0].request.url

    @responses.activate
    def test_get(self, http):
        responses.add(responses.GET, f"{BASE}/agents/42", json={"id": 42, "name": "Bot"})
        t = Teammates(http).get(42)
        assert t.id == 42

    @responses.activate
    def test_get_forwards_user_id(self, http):
        responses.add(responses.GET, f"{BASE}/agents/42", json={"id": 42, "name": "Bot"})
        Teammates(http).get(42, user_id="alice")
        assert responses.calls[0].request.params.get("user_id") == "alice"

    @responses.activate
    def test_update_and_delete_forward_user_id(self, http):
        responses.add(responses.PATCH, f"{BASE}/agents/1", json={"id": 1, "name": "N"})
        responses.add(responses.DELETE, f"{BASE}/agents/1", status=204)
        Teammates(http).update(1, user_id="alice", name="N")
        assert responses.calls[0].request.params.get("user_id") == "alice"
        Teammates(http).delete(1, user_id="alice")
        assert responses.calls[1].request.params.get("user_id") == "alice"

    @responses.activate
    def test_update(self, http):
        responses.add(responses.PATCH, f"{BASE}/agents/1", json={"id": 1, "name": "New"})
        t = Teammates(http).update(1, name="New")
        assert t.name == "New"

    @responses.activate
    def test_disable_and_enable(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/agents/1/disable",
            json={"id": 1, "name": "Bot", "status": "disabled"},
        )
        responses.add(
            responses.POST,
            f"{BASE}/agents/1/enable",
            json={"id": 1, "name": "Bot", "status": "enabled"},
        )
        assert Teammates(http).disable(1).status == "disabled"
        assert Teammates(http).enable(1).status == "enabled"

    @responses.activate
    def test_unarchive(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/agents/1/unarchive",
            json={"id": 1, "name": "Bot", "status": "disabled"},
        )
        assert Teammates(http).unarchive(1).status == "disabled"

    @responses.activate
    def test_unarchive_forwards_user_id(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/agents/1/unarchive",
            json={"id": 1, "name": "Bot", "status": "disabled"},
        )
        Teammates(http).unarchive(1, user_id="alice")
        assert responses.calls[0].request.params.get("user_id") == "alice"

    @responses.activate
    def test_list_include_archived(self, http):
        responses.add(responses.GET, f"{BASE}/agents/", json={"data": [], "has_more": False})
        Teammates(http).list(include_archived=True)
        assert responses.calls[0].request.params.get("include_archived") == "true"

    @responses.activate
    def test_list_default_omits_include_archived(self, http):
        responses.add(responses.GET, f"{BASE}/agents/", json={"data": [], "has_more": False})
        Teammates(http).list()
        assert "include_archived" not in responses.calls[0].request.params

    @responses.activate
    def test_update_display_order(self, http):
        responses.add(responses.PATCH, f"{BASE}/agents/1", json={"id": 1, "name": "Bot"})
        Teammates(http).update(1, display_order=3)
        body = json.loads(responses.calls[0].request.body)
        assert body == {"display_order": 3}

    @responses.activate
    def test_update_display_order_zero_is_sent(self, http):
        """0 is the top position the scheme actually produces — a truthiness guard
        (`if display_order:`) would silently drop the most common write."""
        responses.add(responses.PATCH, f"{BASE}/agents/1", json={"id": 1, "name": "Bot"})
        Teammates(http).update(1, display_order=0)
        body = json.loads(responses.calls[0].request.body)
        assert body == {"display_order": 0}

    @responses.activate
    def test_update_display_order_explicit_none_clears(self, http):
        """None sends JSON null (clears the position); omitting sends nothing."""
        responses.add(responses.PATCH, f"{BASE}/agents/1", json={"id": 1, "name": "Bot"})
        responses.add(responses.PATCH, f"{BASE}/agents/1", json={"id": 1, "name": "Bot"})
        Teammates(http).update(1, display_order=None)
        assert json.loads(responses.calls[0].request.body) == {"display_order": None}
        Teammates(http).update(1, name="Bot")
        assert "display_order" not in json.loads(responses.calls[1].request.body)

    @responses.activate
    def test_list_include_archived_carries_to_next_page(self, http):
        """Pagination must keep the flag: page 2 losing include_archived silently
        drops archived agents from every roster past 20 rows."""
        responses.add(
            responses.GET,
            f"{BASE}/agents/",
            json={"data": [{"id": 1, "name": "A"}], "has_more": True},
        )
        responses.add(responses.GET, f"{BASE}/agents/", json={"data": [], "has_more": False})
        list(Teammates(http).list(include_archived=True).auto_paging_iter())
        assert responses.calls[1].request.params.get("include_archived") == "true"

    @responses.activate
    def test_display_order_parsed_from_response(self, http):
        responses.add(
            responses.GET, f"{BASE}/agents/42", json={"id": 42, "name": "Bot", "display_order": 7}
        )
        assert Teammates(http).get(42).display_order == 7

    @responses.activate
    def test_update_sends_only_provided_fields(self, http):
        responses.add(responses.PATCH, f"{BASE}/agents/1", json={"id": 1, "name": "X"})
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
        responses.add(responses.PATCH, f"{BASE}/agents/1", json={"id": 1, "name": "X"})
        Teammates(http).update(1, model="sonnet")
        body = json.loads(responses.calls[0].request.body)
        assert body == {"model": "sonnet"}

    @responses.activate
    def test_update_model_explicit_none_sends_null_to_clear(self, http):
        """model=None must send JSON null — the documented clear-to-platform-default.

        Deliberately unlike other optional fields (omit-if-None): the v2 contract
        makes null a meaningful model state (D4).
        """
        responses.add(responses.PATCH, f"{BASE}/agents/1", json={"id": 1, "name": "X"})
        Teammates(http).update(1, model=None)
        body = json.loads(responses.calls[0].request.body)
        assert body == {"model": None}

    @responses.activate
    def test_update_without_model_omits_the_key(self, http):
        responses.add(responses.PATCH, f"{BASE}/agents/1", json={"id": 1, "name": "X"})
        Teammates(http).update(1, name="X")
        body = json.loads(responses.calls[0].request.body)
        assert "model" not in body

    @responses.activate
    def test_update_can_set_imessage_fields(self, http):
        responses.add(
            responses.PATCH,
            f"{BASE}/agents/1",
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
        responses.add(responses.DELETE, f"{BASE}/agents/1", status=204)
        Teammates(http).delete(1)
        assert responses.calls[0].request.method == "DELETE"

    @responses.activate
    def test_enable_webhook(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/agents/1/webhook",
            json={"enabled": True, "url": "https://api.m8tes.ai/api/v1/webhooks/mates/1/tok_abc"},
            status=201,
        )
        result = Teammates(http).enable_webhook(1)
        assert isinstance(result, TeammateWebhook)
        assert result.enabled is True
        assert "tok_abc" in result.url

    @responses.activate
    def test_disable_webhook(self, http):
        responses.add(responses.DELETE, f"{BASE}/agents/1/webhook", status=204)
        Teammates(http).disable_webhook(1)
        assert responses.calls[0].request.method == "DELETE"

    @responses.activate
    def test_set_webhook_enabled(self, http):
        """PATCH pauses/resumes without rotating the token — the URL survives.

        Asserts the VERB as well as the body: routed to POST this would still return an
        enabled=False-shaped object in a mock while minting a new token against the real
        API, which is the failure this method exists to avoid.
        """
        responses.add(
            responses.PATCH,
            f"{BASE}/agents/1/webhook",
            json={
                "enabled": False,
                "url": "https://api.m8tes.ai/api/v1/webhooks/mates/1/whk_ab****",
            },
        )
        result = Teammates(http).set_webhook_enabled(1, enabled=False)
        assert isinstance(result, TeammateWebhook)
        assert result.enabled is False
        assert responses.calls[0].request.method == "PATCH"
        assert json.loads(responses.calls[0].request.body) == {"enabled": False}

    @responses.activate
    def test_enable_webhook_not_found(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/agents/999/webhook",
            json={"error": {"message": "Teammate not found"}},
            status=404,
        )
        with pytest.raises(NotFoundError):
            Teammates(http).enable_webhook(999)

    @responses.activate
    def test_enable_email_inbox(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/agents/1/email-inbox",
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
        responses.add(responses.DELETE, f"{BASE}/agents/1/email-inbox", status=204)
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
            auth="api_key",
            limit=10,
            starting_after=5,
        )
        url = responses.calls[0].request.url
        assert "action=create" in url
        assert "resource_type=run" in url
        assert "method=POST" in url
        assert "status_code=201" in url
        assert "auth=api_key" in url
        assert "limit=10" in url
        assert "starting_after=5" in url

    @responses.activate
    def test_auth_filter_is_omitted_when_not_set(self, http):
        """Default must stay server-side `all` — the SDK must not pin a client default."""
        responses.add(responses.GET, f"{BASE}/audit-logs/", json={"data": [], "has_more": False})
        AuditLogs(http).list()
        assert "auth=" not in responses.calls[0].request.url

    @responses.activate
    def test_auth_filter_survives_pagination(self, http):
        """Page 2 must carry the filter — otherwise it silently widens to every row.

        auto_paging_iter re-issues the request through `_fetch_next`; a filter that is
        threaded into the first call only would leak dashboard rows from page 2 on.
        """
        row = {
            "id": 1,
            "method": "GET",
            "path": "/api/v2/runs",
            "status_code": 200,
            "duration_ms": 5,
            "action": "list",
            "resource_type": "run",
            "resource_id": None,
            "api_key_prefix": "m8_test_pref",
            "created_at": "2026-03-05T10:00:00Z",
        }
        responses.add(responses.GET, f"{BASE}/audit-logs/", json={"data": [row], "has_more": True})
        responses.add(responses.GET, f"{BASE}/audit-logs/", json={"data": [], "has_more": False})
        list(AuditLogs(http).list(auth="api_key", limit=1).auto_paging_iter())
        assert len(responses.calls) == 2
        assert "auth=api_key" in responses.calls[1].request.url


class TestRuns:
    @responses.activate
    def test_check(self, http):
        responses.add(
            responses.GET,
            f"{BASE}/runs/check",
            json={
                "total_count": 7,
                "latest_run_id": 42,
                "awaiting_count": 1,
                "latest_change_at": "2026-08-08T12:00:00Z",
            },
        )
        result = Runs(http).check(user_id="alice")
        assert isinstance(result, RunCheck)
        assert result.total_count == 7
        assert result.latest_run_id == 42
        assert result.awaiting_count == 1
        assert responses.calls[0].request.params.get("user_id") == "alice"

    @responses.activate
    def test_check_empty_account(self, http):
        responses.add(responses.GET, f"{BASE}/runs/check", json={"total_count": 0})
        result = Runs(http).check()
        assert result.latest_run_id is None
        assert result.awaiting_count == 0
        assert result.latest_change_at is None

    @responses.activate
    def test_share_and_unshare(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/runs/42/share",
            json={
                "share_token": "shr_abc",
                "share_url": "https://www.m8tes.ai/shared/runs/shr_abc",
            },
        )
        responses.add(responses.DELETE, f"{BASE}/runs/42/share", status=204)
        share = Runs(http).share(42)
        assert isinstance(share, RunShare)
        assert share.share_token == "shr_abc"
        assert share.share_url.endswith("/shr_abc")
        Runs(http).unshare(42)
        assert responses.calls[1].request.method == "DELETE"

    @responses.activate
    def test_archive(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/runs/42/archive",
            json={"id": 42, "status": "completed", "archived": True},
        )
        result = Runs(http).archive(42)
        assert isinstance(result, Run)
        assert result.id == 42

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
    def test_outcome(self, http):
        responses.add(
            responses.GET,
            f"{BASE}/runs/42/outcome",
            json={
                "run_id": 42,
                "status": "completed",
                "summary": "Paused 3 wasteful keywords.",
                "headline": "wasted spend cut",
                "needs_reply": False,
                "output_data": {"saved": 120},
                "message_count": 14,
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
                "cost_usd": "0.4831",
            },
        )
        outcome = Runs(http).outcome(42)
        assert isinstance(outcome, RunOutcome)
        assert outcome.summary == "Paused 3 wasteful keywords."
        assert outcome.needs_reply is False
        assert outcome.output_data == {"saved": 120}
        assert outcome.cost_usd == "0.4831"

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

    # A failed run must not look like a successful empty one. `stream_text` filters the
    # stream down to text deltas, so an error frame was dropped on the floor: an
    # error-only run yielded ZERO chunks and the caller's `for` loop exited normally, and
    # an error after some text left a truncated answer that read as complete. That is the
    # "no silent fallbacks" rule broken on the very first call the quickstart shows.
    # `RunStream` already knew how to raise; `stream_text` just never passed the flag.
    @responses.activate
    def test_stream_text_can_raise_on_a_failed_run(self, http):
        # `error` is the field the parser reads (streaming.py builds ErrorEvent from
        # `data["error"]`). Naming it `errorText` here would still raise — but on
        # "Unknown error", so the test would pass for the wrong reason and prove nothing
        # about the message reaching the caller.
        sse = (
            'data: {"type": "text-delta", "delta": "Partial"}\n\n'
            'data: {"type": "error", "error": "model exploded"}\n\n'
        )
        responses.add(responses.POST, f"{BASE}/runs/", body=sse, content_type="text/event-stream")
        with pytest.raises(RunFailedError) as exc:
            list(Runs(http).stream_text(message="Do X", raise_on_error=True))
        assert "model exploded" in str(exc.value)

    # `type: "error"` is not the only way a run fails, and for a hosted runtime it is not
    # even the common way. A sandbox that never boots, a runner killed by OOM, or an
    # exhausted quota are TERMINAL failures the backend marks the run failed on, and each
    # arrives as its own frame — none of them is an `error` frame. Before this, they were
    # not recorded as errors at all, so `raise_on_error=True` returned an empty loop and
    # the run looked like a success with nothing to say. That is the same silent-failure
    # bug one layer down from where it was first fixed.
    @pytest.mark.parametrize(
        "frame",
        [
            '{"type": "sdk_error", "error": "model call failed"}',
            '{"type": "AGENT_RUNNER_DIED", "error": "runner died", "suspected_oom": true}',
            '{"type": "SANDBOX_QUOTA_EXHAUSTED", "error": "no capacity"}',
            '{"type": "SANDBOX_BOOT_TIMEOUT", "error": "boot timed out"}',
            '{"type": "SANDBOX_UNAVAILABLE", "error": "unavailable"}',
            '{"type": "SNAPSHOT_VERSION_MISMATCH", "error": "stale snapshot"}',
            '{"type": "RUNNER_LIFECYCLE_ERROR", "error": "lifecycle"}',
        ],
    )
    @responses.activate
    def test_terminal_failure_frames_count_as_errors(self, http, frame):
        responses.add(
            responses.POST,
            f"{BASE}/runs/",
            body=f"data: {frame}\n\n",
            content_type="text/event-stream",
        )
        with pytest.raises(RunFailedError):
            list(Runs(http).stream_text(message="Do X", raise_on_error=True))

    @responses.activate
    def test_stream_text_stays_silent_by_default(self, http):
        """The new flag is opt-in — the old behaviour is unchanged for existing callers."""
        sse = 'data: {"type": "error", "error": "model exploded"}\n\n'
        responses.add(responses.POST, f"{BASE}/runs/", body=sse, content_type="text/event-stream")
        # No raise, no output: exactly the trap the flag exists to let callers avoid.
        assert list(Runs(http).stream_text(message="Do X")) == []


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
    def test_update_status_sends_status_and_omits_when_unset(self, http):
        task_json = {"id": 5, "teammate_id": 2, "instructions": "x", "status": "disabled"}
        responses.add(responses.PATCH, f"{BASE}/tasks/5", json=task_json)
        responses.add(responses.PATCH, f"{BASE}/tasks/5", json=task_json)
        task = Tasks(http).update(5, status="disabled")
        assert task.status == "disabled"
        assert json.loads(responses.calls[0].request.body) == {"status": "disabled"}
        Tasks(http).update(5, name="N")
        assert "status" not in json.loads(responses.calls[1].request.body)

    @responses.activate
    def test_list_include_archived_param(self, http):
        responses.add(
            responses.GET, f"{BASE}/tasks/", json={"data": [], "has_more": False}, status=200
        )
        responses.add(
            responses.GET, f"{BASE}/tasks/", json={"data": [], "has_more": False}, status=200
        )
        Tasks(http).list(include_archived=True)
        assert responses.calls[0].request.params.get("include_archived") == "true"
        Tasks(http).list()
        assert "include_archived" not in responses.calls[1].request.params

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
    def test_set_webhook_enabled(self, http):
        """PATCH pauses/resumes without rotating the token — the URL survives."""
        responses.add(
            responses.PATCH,
            f"{BASE}/tasks/1/webhook",
            json={"enabled": False, "url": "https://api.m8tes.ai/api/v1/webhooks/tasks/1/whk_ab…"},
        )
        result = Tasks(http).set_webhook_enabled(1, enabled=False)
        assert isinstance(result, TeammateWebhook)
        assert result.enabled is False
        assert json.loads(responses.calls[0].request.body) == {"enabled": False}

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


class TestTriggers:
    @responses.activate
    def test_list_forwards_filters_and_uses_composite_cursor(self, http):
        responses.add(
            responses.GET,
            f"{BASE}/triggers/",
            json={
                "data": [
                    {
                        "id": "schedule_10",
                        "task_id": 7,
                        "task_name": "daily report",
                        "type": "schedule",
                        "enabled": False,
                        "cron": "0 9 * * *",
                    }
                ],
                "has_more": True,
            },
        )
        responses.add(
            responses.GET,
            f"{BASE}/triggers/",
            json={"data": [], "has_more": False},
        )

        page = Triggers(http).list(user_id="customer_1", type="schedule", task_id=7, limit=1)
        items = list(page.auto_paging_iter())

        assert isinstance(page.data[0], Trigger)
        assert page.data[0].task_id == 7
        assert page.data[0].task_name == "daily report"
        assert page.data[0].enabled is False
        assert responses.calls[0].request.params == {
            "user_id": "customer_1",
            "type": "schedule",
            "task_id": "7",
            "limit": "1",
        }
        assert responses.calls[1].request.params["starting_after"] == "7:schedule_10"
        assert len(items) == 1


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
        result = Apps(http).list()
        assert len(result.data) == 1
        assert isinstance(result.data[0], App)
        assert result.data[0].name == "gmail"
        # GET /apps/ accepts ONLY user_id. This test used to call list(limit=2)
        # and assert "limit=2" was on the wire — against a mock, so it passed
        # while a real server answered 422 `Unknown query parameter`. Assert the
        # opposite now: nothing but user_id may ever be sent.
        url = responses.calls[0].request.url
        assert "limit" not in url
        assert "starting_after" not in url

    @responses.activate
    def test_list_scoped_to_end_user(self, http):
        responses.add(responses.GET, f"{BASE}/apps/", json={"data": [], "has_more": False})
        Apps(http).list(user_id="cust_1")
        assert "user_id=cust_1" in responses.calls[0].request.url

    @responses.activate
    def test_every_2_7_1_call_shape_still_works(self, http):
        """Backwards-compatibility matrix for the 2.7.2 apps.list() change.

        Removing `limit`/`starting_after` looked safe because the API rejects
        them, but `_build_params` drops `limit` at its old default of 20 — so
        `apps.list()` and `apps.list(limit=20)` were SUCCEEDING, and deleting the
        parameters would have turned working code into a TypeError in a PATCH
        release. Every shape a 2.7.1 user could have written is pinned here.
        """
        import warnings

        cases = [
            ({}, False),
            ({"user_id": "u"}, False),
            ({"limit": 20}, False),  # the old default: worked, so must stay silent
            ({"limit": 50}, True),  # would have 422'd: warn
            ({"starting_after": None}, False),
            ({"starting_after": "x"}, True),
        ]
        for kwargs, should_warn in cases:
            responses.add(responses.GET, f"{BASE}/apps/", json={"data": [], "has_more": False})
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                Apps(http).list(**kwargs)  # must never raise
                warned = any(issubclass(c.category, DeprecationWarning) for c in caught)
            url = responses.calls[-1].request.url
            assert warned is should_warn, f"{kwargs}: warned={warned}, expected {should_warn}"
            # Neither param may ever reach the API — it 422s on both.
            assert "limit" not in url and "starting_after" not in url, f"{kwargs} leaked a param"

    @responses.activate
    def test_list_keeps_pagination_params_accepted_but_ignored(self, http):
        """Removing them outright would break calls that were SUCCEEDING.

        `_build_params` drops `limit` at its old default of 20, so
        `apps.list(limit=20)` and `apps.list(starting_after=None)` both worked;
        only a non-default value reached the API and 422'd. So the params stay,
        warn, and are never sent.
        """
        responses.add(responses.GET, f"{BASE}/apps/", json={"data": [], "has_more": False})
        responses.add(responses.GET, f"{BASE}/apps/", json={"data": [], "has_more": False})

        # The previously-working call must neither raise NOR warn: limit=20 was
        # the old default and never reached the API, so that code was correct.
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("error")
            Apps(http).list(limit=20)
        assert "limit" not in responses.calls[0].request.url

        with pytest.warns(DeprecationWarning, match="not paginated"):
            Apps(http).list(limit=50, starting_after="gmail")
        assert "limit" not in responses.calls[1].request.url
        assert "starting_after" not in responses.calls[1].request.url

    @responses.activate
    def test_list_does_not_page(self, http):
        """The catalog is unpaginated, so iterating must finish on page one.

        This replaced a test that mocked a SECOND /apps/ page and asserted the
        client sent `starting_after=gmail`. The real API answers that with a 422,
        and never sets has_more=True on this route, so the old test was pinning
        behaviour that could only exist against the mock.
        """
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
                "has_more": False,
            },
        )

        page = Apps(http).list(user_id="cust_1")
        assert [app.name for app in page.auto_paging_iter()] == ["gmail"]
        assert len(responses.calls) == 1
        assert "user_id=cust_1" in responses.calls[0].request.url

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
        # End-user scope is unchanged: the developer names the connection, no ticket.
        assert body == {"connection_id": "conn_1", "user_id": "cust_1"}

    @responses.activate
    def test_connect_complete_account_scope_sends_the_claim_ticket(self, http):
        """Account-level completion carries the ticket, and nothing else needs to.

        The ticket is what proves the caller is the account that started the flow; the
        backend 400s without it. A payload that dropped it would break every first-party
        connect at the last step.
        """
        responses.add(
            responses.POST,
            f"{BASE}/apps/gmail/connect/complete",
            json={"status": "connected", "app": "gmail"},
            status=200,
        )
        Apps(http).connect_complete("gmail", claim_ticket="tk_abc")
        assert json.loads(responses.calls[0].request.body) == {"claim_ticket": "tk_abc"}

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
            f"{BASE}/agents/",
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


class TestTeammateDocuments:
    @responses.activate
    def test_list_documents(self, http):
        responses.add(
            responses.GET,
            f"{BASE}/agents/1/documents",
            json={
                "data": [
                    {
                        "id": 3,
                        "name": "latest-report",
                        "summary": "Weekly PPC report",
                        "mime_type": "text/markdown",
                        "size_bytes": 2048,
                        "source": "agent",
                    }
                ],
                "has_more": False,
            },
        )
        docs = Teammates(http).list_documents(1)
        assert len(docs) == 1
        assert docs[0].name == "latest-report"
        assert docs[0].content is None

    @responses.activate
    def test_get_document(self, http):
        responses.add(
            responses.GET,
            f"{BASE}/agents/1/documents/latest-report",
            json={
                "id": 3,
                "name": "latest-report",
                "summary": "Weekly PPC report",
                "mime_type": "text/markdown",
                "size_bytes": 2048,
                "source": "agent",
                "content": "# Report",
            },
        )
        doc = Teammates(http).get_document(1, "latest-report")
        assert doc.content == "# Report"


class TestTaskTriggerUpdate:
    @responses.activate
    def test_pause_schedule_trigger(self, http):
        responses.add(
            responses.PATCH,
            f"{BASE}/tasks/10/triggers/5",
            json={"id": 5, "type": "schedule", "enabled": False, "cron": "0 9 * * *"},
        )
        t = TaskTriggers(http).update(10, 5, enabled=False)
        assert isinstance(t, Trigger)
        assert t.enabled is False
        assert json.loads(responses.calls[0].request.body) == {"enabled": False}

    @responses.activate
    def test_reshape_schedule_trigger(self, http):
        responses.add(
            responses.PATCH,
            f"{BASE}/tasks/10/triggers/5",
            json={"id": 5, "type": "schedule", "enabled": True, "cron": "0 18 * * 5"},
        )
        TaskTriggers(http).update(10, 5, cron="0 18 * * 5", timezone="Europe/Copenhagen")
        body = json.loads(responses.calls[0].request.body)
        assert body == {"cron": "0 18 * * 5", "timezone": "Europe/Copenhagen"}


class TestRunsWithFiles:
    @responses.activate
    def test_create_with_files_uses_multipart(self, http):
        responses.add(
            responses.POST, f"{BASE}/runs/with-files", json={"id": 9, "status": "running"}
        )
        run = Runs(http).create(
            message="Summarize this",
            teammate_id=1,
            stream=False,
            files=[("data.csv", b"a,b\n1,2\n")],
        )
        assert isinstance(run, Run)
        req = responses.calls[0].request
        assert "multipart/form-data" in req.headers["Content-Type"]
        body = req.body if isinstance(req.body, bytes) else req.body.encode()
        assert b'name="payload"' in body
        assert b'"message": "Summarize this"' in body
        assert b"data.csv" in body
        assert b"a,b" in body

    @responses.activate
    def test_create_without_files_stays_json(self, http):
        responses.add(responses.POST, f"{BASE}/runs/", json={"id": 9, "status": "running"})
        Runs(http).create(message="Hi", teammate_id=1, stream=False)
        assert responses.calls[0].request.headers["Content-Type"] == "application/json"


class TestToFilePart:
    def test_path_string_reads_bytes(self, tmp_path):
        from m8tes._resources.runs import _to_file_part

        p = tmp_path / "report.csv"
        p.write_bytes(b"a,b\n1,2\n")
        name, content, ctype = _to_file_part(str(p))
        assert name == "report.csv"
        assert content == b"a,b\n1,2\n"
        assert ctype == "text/csv"  # untyped parts are rejected by the API (2026-08-16)

    def test_file_object_is_materialized(self, tmp_path):
        """File objects are read once so HTTP retries re-send identical bytes."""
        from m8tes._resources.runs import _to_file_part

        p = tmp_path / "note.txt"
        p.write_bytes(b"hello")
        with open(p, "rb") as fh:
            name, content, ctype = _to_file_part(fh)
        assert name == "note.txt"
        assert content == b"hello"
        assert ctype == "text/plain"

    def test_unknown_extension_defaults_to_octet_stream(self):
        from m8tes._resources.runs import _to_file_part

        assert _to_file_part(("blob.unknownext", b"x"))[2] == "application/octet-stream"

    def test_four_tuple_passes_through_untouched(self):
        """requests accepts (name, content, type, headers) 4-tuples; the typing
        shim must not demote them (2026-08-16 review)."""
        from m8tes._resources.runs import _to_file_part

        part = ("a.bin", b"x", "application/x-own", {"X-Part": "1"})
        assert _to_file_part(part) == part

    def test_tuple_gains_a_content_type(self):
        """(name, bytes) pairs are typed on the way through — untyped multipart
        parts are rejected by the API with "Invalid type: None" (2026-08-16
        executable-docs gate). Explicit 3-tuples still pass through untouched."""
        from m8tes._resources.runs import _to_file_part

        assert _to_file_part(("x.bin", b"\x00")) == ("x.bin", b"\x00", "application/octet-stream")
        assert _to_file_part(("x.bin", b"\x00", "application/x-own")) == (
            "x.bin",
            b"\x00",
            "application/x-own",
        )


class TestAppTools:
    """apps.list_tools — the tools half of app discovery."""

    @responses.activate
    def test_list_tools_keeps_side_effect_and_approval_as_separate_verdicts(self, http):
        responses.add(
            responses.GET,
            f"{BASE}/apps/github/tools",
            json={
                "data": [
                    {
                        "slug": "GITHUB_LIST_REPOSITORIES",
                        "name": "List repos",
                        "description": "Lists repos",
                        "read_only": True,
                        "approval_mode": "never",
                    },
                    {
                        "slug": "GITHUB_CREATE_AN_ISSUE_COMMENT",
                        "name": "Comment",
                        "read_only": False,
                        "approval_mode": "always",
                    },
                    {
                        "slug": "GITHUB_DELETE_REPO",
                        "name": "Delete repo",
                        "read_only": False,
                        "approval_mode": "always",
                    },
                ],
                "has_more": False,
            },
        )
        page = Apps(http).list_tools("github")
        assert isinstance(page, SyncPage)
        assert page.has_more is False
        assert [t.read_only for t in page.data] == [True, False, False]
        assert [t.approval_mode for t in page.data] == ["never", "always", "always"]
        assert page.data[2].description is None
        assert responses.calls[0].request.url.endswith("/apps/github/tools")


class TestChannels:
    @responses.activate
    def test_list_install_links_and_upsert(self, http):
        responses.add(
            responses.GET,
            f"{BASE}/channels",
            json={
                "data": [
                    {
                        "channel": "slack",
                        "branded": False,
                        "identity_id": None,
                        "client_id": "cid-global",
                        "events_url": "https://www.m8tes.ai/api/v1/webhooks/inbound/slack",
                        "actions_url": "https://www.m8tes.ai/api/v1/webhooks/slack/actions",
                    }
                ],
                "has_more": False,
            },
        )
        responses.add(
            responses.GET,
            f"{BASE}/channels/install-links",
            json={"slack": {"authorization_url": "https://slack.com/oauth/v2/authorize?x=1"}},
        )
        responses.add(
            responses.PUT,
            f"{BASE}/channels/identities",
            json={
                "channel": "slack",
                "branded": True,
                "identity_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "client_id": "cid-custom",
                "events_url": (
                    "https://www.m8tes.ai/api/v1/webhooks/inbound/slack/"
                    "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
                ),
                "actions_url": (
                    "https://www.m8tes.ai/api/v1/webhooks/slack/actions/"
                    "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
                ),
            },
        )
        ch = Channels(http)
        page = ch.list()
        assert page.data[0].branded is False
        links = ch.install_links(user_id="cust_123")
        assert "slack.com" in links.slack.authorization_url
        assert "user_id=cust_123" in responses.calls[1].request.url
        branded = ch.upsert_identity(
            channel="slack",
            client_id="cid-custom",
            client_secret="csec",
            signing_secret="sign",
        )
        assert branded.branded is True
        body = json.loads(responses.calls[2].request.body)
        assert body["signing_secret"] == "sign"

        responses.add(
            responses.PUT,
            f"{BASE}/channels/identities",
            json={
                "channel": "github",
                "branded": True,
                "identity_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "client_id": "Iv1.acme",
                "webhook_url": (
                    "https://www.m8tes.ai/api/v1/webhooks/github-app/"
                    "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
                ),
                "github_app_id": "555",
                "github_app_slug": "acme-code",
            },
        )
        gh = ch.upsert_identity(
            channel="github",
            client_id="Iv1.acme",
            client_secret="oauth",
            signing_secret="hook",
            github_app_id="555",
            github_app_slug="acme-code",
            github_private_key="test-github-app-pem-placeholder",
        )
        assert gh.channel == "github"
        assert gh.webhook_url.endswith("/github-app/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        gh_body = json.loads(responses.calls[3].request.body)
        assert gh_body["github_app_slug"] == "acme-code"
        assert gh_body["github_private_key"] == "test-github-app-pem-placeholder"

        responses.add(
            responses.GET,
            f"{BASE}/channels/install-links",
            json={
                "slack": {"authorization_url": "https://slack.com/oauth/v2/authorize?x=1"},
                "github": {"install_url": "https://github.com/apps/acme-code/installations/new"},
            },
        )
        both = ch.install_links()
        assert both.github is not None
        assert "acme-code" in both.github.install_url


class TestSubresourceScopeForwarding:
    """Every sub-resource method that gained `user_id` (2026-08-16 scope fix) must
    put it on the WIRE as a query param — the endpoint enforces it there, so a
    dropped `params=` silently strips the tenant boundary from the call while
    every test that omits user_id stays green. One test per resource family,
    asserting the recorded request's params, same shape as the by-id family."""

    @responses.activate
    def test_agent_subresources_forward_user_id(self, http):
        t = Teammates(http)
        responses.add(responses.POST, f"{BASE}/agents/1/reset", json={"reset_fields": []})
        responses.add(
            responses.POST, f"{BASE}/agents/1/webhook", json={"enabled": True, "url": "u"}
        )
        responses.add(
            responses.PATCH, f"{BASE}/agents/1/webhook", json={"enabled": False, "url": "u"}
        )
        responses.add(responses.DELETE, f"{BASE}/agents/1/webhook", status=204)
        responses.add(
            responses.POST, f"{BASE}/agents/1/email-inbox", json={"enabled": True, "address": "a@b"}
        )
        responses.add(responses.DELETE, f"{BASE}/agents/1/email-inbox", status=204)
        responses.add(
            responses.POST, f"{BASE}/agents/1/fetchmail", json={"enabled": True, "address": "a@b"}
        )
        responses.add(responses.DELETE, f"{BASE}/agents/1/fetchmail", status=204)

        t.reset(1, user_id="alice")
        t.enable_webhook(1, user_id="alice")
        t.set_webhook_enabled(1, enabled=False, user_id="alice")
        t.disable_webhook(1, user_id="alice")
        t.enable_email_inbox(1, user_id="alice")
        t.disable_email_inbox(1, user_id="alice")
        t.enable_fetchmail(1, user_id="alice")
        t.disable_fetchmail(1, user_id="alice")
        for call in responses.calls:
            assert call.request.params.get("user_id") == "alice", call.request.url

    @responses.activate
    def test_task_subresources_forward_user_id(self, http):
        tasks = Tasks(http)
        responses.add(responses.POST, f"{BASE}/tasks/1/webhook", json={"enabled": True, "url": "u"})
        responses.add(
            responses.PATCH, f"{BASE}/tasks/1/webhook", json={"enabled": False, "url": "u"}
        )
        responses.add(responses.DELETE, f"{BASE}/tasks/1/webhook", status=204)
        trig = {"id": "schedule_1", "type": "schedule", "enabled": True}
        responses.add(responses.POST, f"{BASE}/tasks/1/triggers/", json=trig)
        responses.add(responses.GET, f"{BASE}/tasks/1/triggers/", json={"data": [trig]})
        responses.add(responses.PATCH, f"{BASE}/tasks/1/triggers/schedule_1", json=trig)
        responses.add(responses.DELETE, f"{BASE}/tasks/1/triggers/schedule_1", status=204)

        tasks.enable_webhook(1, user_id="alice")
        tasks.set_webhook_enabled(1, enabled=False, user_id="alice")
        tasks.disable_webhook(1, user_id="alice")
        tasks.triggers.create(1, type="schedule", cron="0 9 * * 1", user_id="alice")
        tasks.triggers.list(1, user_id="alice")
        tasks.triggers.update(1, "schedule_1", enabled=False, user_id="alice")
        tasks.triggers.delete(1, "schedule_1", user_id="alice")
        for call in responses.calls:
            assert call.request.params.get("user_id") == "alice", call.request.url

    @responses.activate
    def test_omitted_user_id_sends_no_param(self, http):
        # The operator view must stay the default: no user_id kwarg → no query param.
        responses.add(
            responses.POST, f"{BASE}/agents/1/webhook", json={"enabled": True, "url": "u"}
        )
        Teammates(http).enable_webhook(1)
        assert "user_id" not in responses.calls[0].request.params
