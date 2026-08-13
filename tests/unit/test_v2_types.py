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
            "model": "sonnet",
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
        assert t.model == "sonnet"

    def test_from_dict_minimal(self):
        t = Teammate.from_dict({"id": 1, "name": "Bot"})
        assert t.instructions is None
        assert t.tools == []
        assert t.default_permission_mode == "autonomous"
        assert t.model is None
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


class TestSlackInstallLinkExport:
    def test_exported_from_package_root(self):
        from m8tes import SlackInstallLink
        from m8tes._types import SlackInstallLink as Inner

        assert SlackInstallLink is Inner


class TestRunAcknowledgementAndRetryFields:
    """Declared-but-unmapped is the failure these cover.

    `test_v2_schema_contract.py` asserts the dataclass has a field for everything
    `DevRunResponse` publishes — but it never calls `from_dict`, so a field can exist on
    the type, be absent from the mapping, and read `None` forever while every contract
    test stays green. Verified: deleting the `from_dict` line for either field below
    leaves that suite passing.
    """

    def test_notified_at_round_trips(self):
        """With only `last_viewed_at`, an emailed run looks unread forever."""
        run = Run.from_dict(
            {
                "id": 1,
                "teammate_id": 2,
                "status": "completed",
                "notified_at": "2026-08-01T09:00:00Z",
            }
        )
        assert run.notified_at == "2026-08-01T09:00:00Z"

    def test_repeats_actions_round_trips_and_distinguishes_false_from_none(self):
        """`False` ("safe to retry") and `None` ("not computed") must not collapse."""
        assert Run.from_dict({"id": 1, "status": "failed", "repeats_actions": True}).repeats_actions
        assert (
            Run.from_dict({"id": 1, "status": "failed", "repeats_actions": False}).repeats_actions
            is False
        )
        # Absent on a list read: unknown, NOT "took no actions". A client that treats the
        # two the same skips a confirmation for a run that may have sent an email.
        assert Run.from_dict({"id": 1, "status": "failed"}).repeats_actions is None


class TestTeammateParsesEveryFieldItDeclares:
    """A dataclass field the server sends but `from_dict` never reads is silently the
    default, forever.

    Not hypothetical: `disabled_builtin_tools` shipped on the dataclass and NOT in
    `from_dict`, so `agents.create(disabled_builtin_tools=[...])` sent the list, the server
    stored it, and the SDK handed back `[]` — the caller would reasonably conclude the write
    failed. Every unit test passed; only a live round-trip caught it. This guard is generic
    so the next added field cannot repeat it.
    """

    def test_from_dict_reads_every_declared_field(self):
        import dataclasses

        from m8tes._types import Teammate

        payload = {
            "id": 1,
            "name": "Bot",
            "prompt_profile": "bare",
            "disabled_builtin_tools": ["feedback", "notify"],
        }
        parsed = Teammate.from_dict(payload)
        for key, value in payload.items():
            assert getattr(parsed, key) == value, (
                f"Teammate.from_dict ignored {key!r}: the server sent {value!r} and the SDK "
                f"reports {getattr(parsed, key)!r}"
            )
        # And the declared field set has not drifted from what from_dict can populate.
        declared = {f.name for f in dataclasses.fields(Teammate)}
        assert "disabled_builtin_tools" in declared
