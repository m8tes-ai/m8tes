"""Tests for from_dict() edge cases — None handling, defaults, minimal payloads."""

from m8tes._types import (
    App,
    AppConnection,
    Memory,
    PermissionPolicy,
    PermissionRequest,
    Run,
    RunFile,
    Task,
    Teammate,
    TeammateWebhook,
    Trigger,
    Webhook,
    WebhookDelivery,
)


class TestTeammateFromDict:
    def test_minimal(self):
        """Minimal dict with only required fields."""
        t = Teammate.from_dict({"id": 1, "name": "Bot"})
        assert t.id == 1
        assert t.name == "Bot"
        assert t.instructions is None
        assert t.tools == []
        assert t.role is None
        assert t.user_id is None
        assert t.metadata is None
        assert t.status == "enabled"
        assert t.created_at == ""

    def test_full(self):
        """All fields populated."""
        t = Teammate.from_dict(
            {
                "id": 1,
                "name": "Bot",
                "instructions": "Help",
                "tools": ["gmail"],
                "role": "support",
                "goals": "Resolve",
                "user_id": "u1",
                "metadata": {"k": "v"},
                "allowed_senders": ["@a.com"],
                "status": "disabled",
                "created_at": "2024-01-01",
                "updated_at": "2024-01-02",
            }
        )
        assert t.tools == ["gmail"]
        assert t.allowed_senders == ["@a.com"]
        assert t.updated_at == "2024-01-02"


class TestRunFromDict:
    def test_minimal(self):
        r = Run.from_dict({"id": 1})
        assert r.id == 1
        assert r.status == "running"
        assert r.output is None
        assert r.error is None

    def test_completed(self):
        r = Run.from_dict({"id": 1, "status": "completed", "output": "Done"})
        assert r.output == "Done"

    def test_failed(self):
        r = Run.from_dict({"id": 1, "status": "failed", "error": "Boom"})
        assert r.error == "Boom"


class TestTaskFromDict:
    def test_minimal(self):
        t = Task.from_dict({"id": 1, "teammate_id": 2, "instructions": "Do"})
        assert t.name is None
        assert t.tools == []
        assert t.expected_output is None
        assert t.status == "enabled"

    def test_full(self):
        t = Task.from_dict(
            {
                "id": 1,
                "teammate_id": 2,
                "instructions": "Do",
                "name": "T",
                "tools": ["slack"],
                "expected_output": "PDF",
                "goals": "G",
                "user_id": "u",
                "status": "archived",
            }
        )
        assert t.name == "T"
        assert t.tools == ["slack"]


class TestTriggerFromDict:
    def test_schedule(self):
        t = Trigger.from_dict({"id": 1, "type": "schedule", "cron": "0 9 * * *"})
        assert t.cron == "0 9 * * *"
        assert t.timezone == "UTC"
        assert t.enabled is True

    def test_webhook(self):
        t = Trigger.from_dict({"id": 0, "type": "webhook", "url": "https://example.com"})
        assert t.url == "https://example.com"

    def test_email(self):
        t = Trigger.from_dict({"id": 0, "type": "email", "address": "task@in.m8tes.ai"})
        assert t.address == "task@in.m8tes.ai"


class TestAppFromDict:
    def test_minimal(self):
        a = App.from_dict({"name": "gmail"})
        assert a.display_name == "gmail"
        assert a.category == "general"
        assert a.connected is False

    def test_full(self):
        a = App.from_dict(
            {"name": "gmail", "display_name": "Gmail", "category": "email", "connected": True}
        )
        assert a.connected is True


class TestAppConnectionFromDict:
    def test_all_none(self):
        c = AppConnection.from_dict({})
        assert c.authorization_url is None
        assert c.connection_id is None

    def test_full(self):
        c = AppConnection.from_dict(
            {
                "authorization_url": "https://auth.com",
                "connection_id": "c1",
                "status": "connected",
                "app": "gmail",
            }
        )
        assert c.status == "connected"


class TestMemoryFromDict:
    def test_minimal(self):
        m = Memory.from_dict({"id": 1, "content": "Pref"})
        assert m.source == "api"
        assert m.user_id is None


class TestPermissionRequestFromDict:
    def test_minimal(self):
        p = PermissionRequest.from_dict(
            {"request_id": "r1", "tool_name": "gmail", "status": "pending"}
        )
        assert p.tool_input is None
        assert p.resolved_at is None


class TestPermissionPolicyFromDict:
    def test_full(self):
        p = PermissionPolicy.from_dict(
            {"id": 1, "user_id": "u1", "tool_name": "gmail", "created_at": "2024-01-01"}
        )
        assert p.user_id == "u1"


class TestWebhookFromDict:
    def test_minimal(self):
        w = Webhook.from_dict({"id": 1, "url": "https://x.com"})
        assert w.events == []
        assert w.secret is None
        assert w.active is True
        assert w.delivery_status == "active"

    def test_full(self):
        w = Webhook.from_dict(
            {
                "id": 1,
                "url": "https://x.com",
                "events": ["run.completed"],
                "secret": "s",
                "active": False,
                "delivery_status": "failing",
                "created_at": "2024-01-01",
            }
        )
        assert w.active is False
        assert w.delivery_status == "failing"


class TestWebhookDeliveryFromDict:
    def test_full(self):
        d = WebhookDelivery.from_dict(
            {
                "id": 1,
                "webhook_endpoint_id": 10,
                "event_type": "run.completed",
                "event_id": "evt_1",
                "run_id": 42,
                "status": "success",
                "response_status_code": 200,
                "response_body": "OK",
                "attempts": 1,
                "next_retry_at": None,
                "created_at": "2024-01-01",
            }
        )
        assert d.response_status_code == 200

    def test_minimal(self):
        d = WebhookDelivery.from_dict(
            {
                "id": 1,
                "webhook_endpoint_id": 10,
                "event_type": "run.completed",
                "event_id": "evt_1",
                "run_id": 42,
                "status": "pending",
            }
        )
        assert d.attempts == 0
        assert d.response_status_code is None


class TestRunFileFromDict:
    def test_basic(self):
        f = RunFile.from_dict({"name": "report.csv", "size": 1024})
        assert f.name == "report.csv"
        assert f.size == 1024


class TestTeammateWebhookFromDict:
    def test_enabled(self):
        w = TeammateWebhook.from_dict({"enabled": True, "url": "https://hook.com"})
        assert w.enabled is True
        assert w.url == "https://hook.com"

    def test_disabled(self):
        w = TeammateWebhook.from_dict({"enabled": False})
        assert w.url is None
