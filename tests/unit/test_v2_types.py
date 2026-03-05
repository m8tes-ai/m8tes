"""Tests for v2 SDK dataclass types."""

from m8tes._types import App, AuditLog, PermissionMode, Run, Task, Teammate, Trigger


class TestTeammate:
    def test_from_dict_full(self):
        data = {
            "id": 1,
            "name": "Bot",
            "instructions": "Help",
            "tools": ["gmail"],
            "role": "support",
            "goals": "Resolve tickets",
            "user_id": "u_1",
            "metadata": {"env": "prod"},
            "allowed_senders": ["@acme.com"],
            "default_permission_mode": "approval",
            "status": "enabled",
            "created_at": "2026-01-01",
            "updated_at": "2026-01-02",
        }
        t = Teammate.from_dict(data)
        assert t.id == 1
        assert t.name == "Bot"
        assert t.tools == ["gmail"]
        assert t.allowed_senders == ["@acme.com"]
        assert t.default_permission_mode == "approval"

    def test_from_dict_minimal(self):
        t = Teammate.from_dict({"id": 1, "name": "Bot"})
        assert t.instructions is None
        assert t.tools == []
        assert t.default_permission_mode == "autonomous"
        assert t.status == "enabled"


class TestRun:
    def test_from_dict(self):
        r = Run.from_dict({"id": 42, "teammate_id": 1, "status": "completed", "output": "Done"})
        assert r.id == 42
        assert r.output == "Done"

    def test_from_dict_minimal(self):
        r = Run.from_dict({"id": 1})
        assert r.status == "running"
        assert r.output is None


class TestTask:
    def test_from_dict(self):
        t = Task.from_dict(
            {
                "id": 1,
                "teammate_id": 2,
                "instructions": "Do X",
                "tools": ["slack"],
                "user_id": "cust_1",
            }
        )
        assert t.teammate_id == 2
        assert t.tools == ["slack"]
        assert t.user_id == "cust_1"

    def test_from_dict_no_user_id(self):
        t = Task.from_dict({"id": 1, "teammate_id": 2, "instructions": "Do X"})
        assert t.user_id is None


class TestTrigger:
    def test_schedule_trigger(self):
        t = Trigger.from_dict({"id": 1, "type": "schedule", "cron": "0 9 * * 1"})
        assert t.type == "schedule"
        assert t.cron == "0 9 * * 1"

    def test_webhook_trigger(self):
        t = Trigger.from_dict({"id": 2, "type": "webhook", "url": "https://example.com/hook"})
        assert t.url == "https://example.com/hook"

    def test_email_trigger(self):
        t = Trigger.from_dict({"id": 3, "type": "email", "address": "bot@m8tes.ai"})
        assert t.address == "bot@m8tes.ai"


class TestApp:
    def test_from_dict(self):
        a = App.from_dict(
            {"name": "gmail", "display_name": "Gmail", "category": "email", "connected": True}
        )
        assert a.name == "gmail"
        assert a.connected is True


class TestAuditLog:
    def test_from_dict(self):
        log = AuditLog.from_dict(
            {
                "id": 7,
                "method": "POST",
                "path": "/api/v2/runs/",
                "status_code": 201,
                "duration_ms": 33,
                "action": "create",
                "resource_type": "run",
                "resource_id": None,
                "api_key_prefix": "m8_abc12345",
                "created_at": "2026-03-05T10:00:00Z",
            }
        )
        assert log.id == 7
        assert log.method == "POST"
        assert log.status_code == 201
        assert log.resource_type == "run"


class TestPermissionMode:
    def test_enum_values(self):
        assert PermissionMode.AUTONOMOUS == "autonomous"
        assert PermissionMode.APPROVAL == "approval"
        assert PermissionMode.PLAN == "plan"

    def test_exported_from_package_root(self):
        from m8tes import PermissionMode as ExportedPermissionMode

        assert ExportedPermissionMode is PermissionMode
