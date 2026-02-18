"""Tests for v2 SDK resource classes — verify correct HTTP calls and response parsing."""

import json

import pytest
import responses

from m8tes._exceptions import NotFoundError
from m8tes._http import HTTPClient
from m8tes._resources.apps import Apps
from m8tes._resources.memories import Memories
from m8tes._resources.permissions import Permissions
from m8tes._resources.runs import Runs
from m8tes._resources.tasks import Tasks, TaskTriggers
from m8tes._resources.teammates import Teammates
from m8tes._streaming import RunStream
from m8tes._types import (
    App,
    AppConnection,
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
            f"{BASE}/teammates",
            json={
                "id": 1,
                "name": "Bot",
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
            responses.POST, f"{BASE}/teammates", json={"id": 2, "name": "Full"}, status=201
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
        )
        body = json.loads(responses.calls[0].request.body)
        assert body["tools"] == ["gmail"]
        assert body["allowed_senders"] == ["@acme.com"]

    @responses.activate
    def test_list(self, http):
        responses.add(
            responses.GET,
            f"{BASE}/teammates",
            json={"data": [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}], "has_more": False},
        )
        result = Teammates(http).list()
        assert isinstance(result, SyncPage)
        assert len(result.data) == 2
        assert all(isinstance(t, Teammate) for t in result.data)
        assert result.has_more is False

    @responses.activate
    def test_list_with_user_id(self, http):
        responses.add(responses.GET, f"{BASE}/teammates", json={"data": [], "has_more": False})
        Teammates(http).list(user_id="u_1")
        assert "user_id=u_1" in responses.calls[0].request.url

    @responses.activate
    def test_get(self, http):
        responses.add(responses.GET, f"{BASE}/teammates/42", json={"id": 42, "name": "Bot"})
        t = Teammates(http).get(42)
        assert t.id == 42

    @responses.activate
    def test_update(self, http):
        responses.add(responses.PATCH, f"{BASE}/teammates/1", json={"id": 1, "name": "New"})
        t = Teammates(http).update(1, name="New")
        assert t.name == "New"

    @responses.activate
    def test_update_sends_only_provided_fields(self, http):
        responses.add(responses.PATCH, f"{BASE}/teammates/1", json={"id": 1, "name": "X"})
        Teammates(http).update(1, name="X", tools=["gmail"], allowed_senders=["@a.com"])
        body = json.loads(responses.calls[0].request.body)
        assert body == {"name": "X", "tools": ["gmail"], "allowed_senders": ["@a.com"]}

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


# ── Runs ─────────────────────────────────────────────────────────────


class TestRuns:
    @responses.activate
    def test_create_streaming(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/runs",
            body="data: {}\n\n",
            status=200,
            content_type="text/event-stream",
        )
        result = Runs(http).create(message="Do X")
        assert isinstance(result, RunStream)
        result._response.close()

    @responses.activate
    def test_create_non_streaming(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/runs",
            json={"id": 1, "status": "running"},
        )
        result = Runs(http).create(message="Do X", stream=False)
        assert isinstance(result, Run)
        assert result.id == 1

    @responses.activate
    def test_create_with_all_fields(self, http):
        responses.add(responses.POST, f"{BASE}/runs", json={"id": 1})
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
    def test_list(self, http):
        responses.add(
            responses.GET,
            f"{BASE}/runs",
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
    def test_cancel(self, http):
        responses.add(
            responses.POST, f"{BASE}/runs/1/cancel", json={"id": 1, "status": "cancelled"}
        )
        r = Runs(http).cancel(1)
        assert r.status == "cancelled"

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


# ── Tasks (advanced) ─────────────────────────────────────────────────


class TestTasks:
    @responses.activate
    def test_create(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/tasks",
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
            f"{BASE}/tasks",
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
            f"{BASE}/tasks",
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
    def test_delete(self, http):
        responses.add(responses.DELETE, f"{BASE}/tasks/1", status=204)
        Tasks(http).delete(1)


class TestTaskTriggers:
    @responses.activate
    def test_create_schedule(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/tasks/1/triggers",
            json={"id": 10, "type": "schedule", "enabled": True, "cron": "0 9 * * 1"},
            status=201,
        )
        t = TaskTriggers(http).create(1, type="schedule", cron="0 9 * * 1")
        assert isinstance(t, Trigger)
        assert t.cron == "0 9 * * 1"

    @responses.activate
    def test_list(self, http):
        responses.add(
            responses.GET, f"{BASE}/tasks/1/triggers", json=[{"id": 10, "type": "schedule"}]
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
            f"{BASE}/apps",
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
        assert isinstance(result, AppConnection)
        assert result.authorization_url == "https://accounts.google.com/o/oauth2"
        assert result.connection_id == "conn_1"
        body = json.loads(responses.calls[0].request.body)
        assert body == {"redirect_uri": "https://myapp.com/callback", "user_id": "cust_1"}

    @responses.activate
    def test_connect_complete(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/apps/gmail/connect/complete",
            json={"status": "connected", "app": "gmail"},
            status=200,
        )
        result = Apps(http).connect_complete("gmail", "conn_1", user_id="cust_1")
        assert isinstance(result, AppConnection)
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
        responses.add(responses.GET, f"{BASE}/memories", json=page1, status=200)
        responses.add(responses.GET, f"{BASE}/memories", json=page2, status=200)

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
        responses.add(responses.GET, f"{BASE}/permissions", json=page1, status=200)
        responses.add(responses.GET, f"{BASE}/permissions", json=page2, status=200)

        page = Permissions(http).list(user_id="u1")
        items = list(page.auto_paging_iter())
        assert len(items) == 2
        assert items[0].tool_name == "bash"
        assert items[1].tool_name == "gmail"
        assert "starting_after=10" in responses.calls[1].request.url
