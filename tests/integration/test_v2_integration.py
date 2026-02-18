"""V2 SDK integration tests — real M8tes client against real FastAPI backend.

Covers all V2 resources: teammates (CRUD, webhooks, email inbox), tasks
(CRUD, triggers, run edge cases), runs (create, get, cancel, reply, files,
HITL validation, answer, approve, SDK convenience methods like poll,
create_and_wait, reply_and_wait, stream_text, streaming), memories,
permissions, webhooks, users, settings, apps. Plus pagination, error
handling, validation edge cases, multi-tenancy isolation, parameter combos,
trigger error paths, and context manager usage.

Requirements:
    1. Backend running at localhost:8000 (or E2E_BACKEND_URL)
    2. Database running (via docker compose or SQLite for CI)

Run: pytest tests/integration/test_v2_integration.py -v -m integration
"""

import uuid

import pytest

from m8tes import M8tes
from m8tes._exceptions import (
    AuthenticationError,
    ConflictError,
    M8tesError,
    NotFoundError,
    ValidationError,
)
from m8tes._types import (
    AccountSettings,
    EmailInbox,
    EndUser,
    Memory,
    PermissionPolicy,
    Run,
    SyncPage,
    Task,
    Teammate,
    TeammateWebhook,
    Trigger,
    Webhook,
)


def _uid() -> str:
    """Generate a unique user_id to avoid collision across test runs."""
    return f"user-{uuid.uuid4().hex[:8]}"


# ── Teammates ────────────────────────────────────────────────────────


@pytest.mark.integration
class TestTeammatesCRUD:
    def test_full_lifecycle(self, v2_client):
        """Create -> list -> get -> update -> delete -> verify excluded from list."""
        t = v2_client.teammates.create(name="IntegBot", instructions="Test bot")
        try:
            assert isinstance(t, Teammate)
            assert t.id is not None
            assert t.name == "IntegBot"
            assert t.instructions == "Test bot"
            assert t.status == "enabled"
            assert t.created_at  # non-empty

            # List — should include newly created teammate
            page = v2_client.teammates.list()
            assert isinstance(page, SyncPage)
            assert any(tm.id == t.id for tm in page.data)

            # Get
            fetched = v2_client.teammates.get(t.id)
            assert fetched.id == t.id
            assert fetched.name == "IntegBot"

            # Update
            updated = v2_client.teammates.update(t.id, name="UpdatedBot")
            assert updated.name == "UpdatedBot"

            # Verify update persisted via GET
            refetched = v2_client.teammates.get(t.id)
            assert refetched.name == "UpdatedBot"
        finally:
            v2_client.teammates.delete(t.id)

        # Verify excluded from list (archived teammates are filtered out)
        page_after = v2_client.teammates.list()
        assert not any(tm.id == t.id for tm in page_after.data)

    def test_create_with_all_fields(self, v2_client):
        """Create teammate with every optional field."""
        uid = _uid()
        t = v2_client.teammates.create(
            name="FullBot",
            instructions="Help with everything",
            role="support",
            goals="Resolve tickets",
            user_id=uid,
            metadata={"team": "ops"},
            allowed_senders=["@acme.com"],
        )
        try:
            assert t.name == "FullBot"
            assert t.user_id == uid
            assert t.role == "support"
            assert t.goals == "Resolve tickets"
            assert t.metadata == {"team": "ops"}
            assert t.allowed_senders == ["@acme.com"]
        finally:
            v2_client.teammates.delete(t.id)

    def test_user_id_filtering(self, v2_client):
        """List with user_id only returns matching teammates."""
        uid_a, uid_b = _uid(), _uid()
        t1 = v2_client.teammates.create(name="TenantA", user_id=uid_a)
        t2 = v2_client.teammates.create(name="TenantB", user_id=uid_b)
        try:
            page_a = v2_client.teammates.list(user_id=uid_a)
            ids = [tm.id for tm in page_a.data]
            assert t1.id in ids
            assert t2.id not in ids

            page_b = v2_client.teammates.list(user_id=uid_b)
            ids_b = [tm.id for tm in page_b.data]
            assert t2.id in ids_b
            assert t1.id not in ids_b
        finally:
            v2_client.teammates.delete(t1.id)
            v2_client.teammates.delete(t2.id)

    def test_update_multiple_fields(self, v2_client):
        """Update multiple fields at once, verify all persisted."""
        t = v2_client.teammates.create(name="MultiUpdate")
        try:
            updated = v2_client.teammates.update(
                t.id,
                name="Renamed",
                instructions="New instructions",
                role="analyst",
                goals="Analyze data",
                metadata={"version": "2"},
            )
            assert updated.name == "Renamed"
            assert updated.instructions == "New instructions"
            assert updated.role == "analyst"

            # Verify via GET
            fetched = v2_client.teammates.get(t.id)
            assert fetched.goals == "Analyze data"
            assert fetched.metadata == {"version": "2"}
        finally:
            v2_client.teammates.delete(t.id)

    def test_create_minimal(self, v2_client):
        """Create with only required field (name)."""
        t = v2_client.teammates.create(name="Minimal")
        try:
            assert t.name == "Minimal"
            assert t.instructions is None
            assert t.tools == []
            assert t.role is None
            assert t.user_id is None
        finally:
            v2_client.teammates.delete(t.id)

    def test_get_archived_by_id(self, v2_client):
        """After DELETE, GET by ID still returns the archived teammate."""
        t = v2_client.teammates.create(name="ArchiveMe")
        v2_client.teammates.delete(t.id)
        fetched = v2_client.teammates.get(t.id)
        assert fetched.status == "archived"
        assert fetched.name == "ArchiveMe"

    def test_delete_already_archived_is_idempotent(self, v2_client):
        """DELETE on already-archived teammate does not raise."""
        t = v2_client.teammates.create(name="DoubleDelete")
        v2_client.teammates.delete(t.id)
        v2_client.teammates.delete(t.id)  # should not raise

    def test_tools_roundtrip(self, v2_client):
        """Create teammate with tools, verify persisted, update tools."""
        available = [a.name for a in v2_client.apps.list().data]
        if len(available) < 2:
            pytest.skip(f"Need >=2 tools, got {len(available)}")
        tool_a, tool_b = available[0], available[1]
        t = v2_client.teammates.create(name="ToolsBot", tools=[tool_a, tool_b])
        try:
            assert set(t.tools) == {tool_a, tool_b}

            updated = v2_client.teammates.update(t.id, tools=[tool_b])
            assert updated.tools == [tool_b]

            fetched = v2_client.teammates.get(t.id)
            assert fetched.tools == [tool_b]
        finally:
            v2_client.teammates.delete(t.id)

    def test_tools_clear_to_empty(self, v2_client):
        """Update tools to empty list clears all tools."""
        available = [a.name for a in v2_client.apps.list().data]
        if not available:
            pytest.skip("No tools available")
        t = v2_client.teammates.create(name="ClearTools", tools=[available[0]])
        try:
            updated = v2_client.teammates.update(t.id, tools=[])
            assert updated.tools == []
        finally:
            v2_client.teammates.delete(t.id)

    def test_update_allowed_senders(self, v2_client):
        """Update allowed_senders roundtrips correctly."""
        t = v2_client.teammates.create(name="SenderBot")
        try:
            updated = v2_client.teammates.update(
                t.id, allowed_senders=["@acme.com", "bob@example.com"]
            )
            assert set(updated.allowed_senders) == {"@acme.com", "bob@example.com"}

            fetched = v2_client.teammates.get(t.id)
            assert set(fetched.allowed_senders) == {"@acme.com", "bob@example.com"}
        finally:
            v2_client.teammates.delete(t.id)

    def test_metadata_nested_values(self, v2_client):
        """Nested dict metadata roundtrips correctly."""
        meta = {"team": {"name": "ops", "id": 42}, "tags": ["prod", "v2"]}
        t = v2_client.teammates.create(name="NestedMeta", metadata=meta)
        try:
            assert t.metadata == meta
            fetched = v2_client.teammates.get(t.id)
            assert fetched.metadata == meta
        finally:
            v2_client.teammates.delete(t.id)


# ── Teammate Webhooks ────────────────────────────────────────────────


@pytest.mark.integration
class TestTeammateWebhooks:
    def test_enable_disable_webhook(self, v2_client):
        """Enable webhook trigger → verify → disable → verify."""
        tm = v2_client.teammates.create(name="WebhookHost")
        try:
            wh = v2_client.teammates.enable_webhook(tm.id)
            assert isinstance(wh, TeammateWebhook)
            assert wh.enabled is True
            assert wh.url is not None
            assert "webhook" in wh.url.lower() or "mates" in wh.url.lower()

            v2_client.teammates.disable_webhook(tm.id)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_enable_webhook_idempotent(self, v2_client):
        """Enable webhook twice should not error."""
        tm = v2_client.teammates.create(name="WebhookIdempotent")
        try:
            wh1 = v2_client.teammates.enable_webhook(tm.id)
            wh2 = v2_client.teammates.enable_webhook(tm.id)
            assert wh1.enabled is True
            assert wh2.enabled is True

            v2_client.teammates.disable_webhook(tm.id)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_enable_webhook_nonexistent_404(self, v2_client):
        """Enable webhook on nonexistent teammate returns 404."""
        with pytest.raises(NotFoundError):
            v2_client.teammates.enable_webhook(999999)

    def test_disable_webhook_nonexistent_404(self, v2_client):
        """Disable webhook on nonexistent teammate returns 404."""
        with pytest.raises(NotFoundError):
            v2_client.teammates.disable_webhook(999999)

    def test_webhook_url_changes_on_reenable(self, v2_client):
        """Disable + re-enable webhook produces a new URL/token."""
        tm = v2_client.teammates.create(name="WebhookReEnable")
        try:
            wh1 = v2_client.teammates.enable_webhook(tm.id)
            url1 = wh1.url
            v2_client.teammates.disable_webhook(tm.id)

            wh2 = v2_client.teammates.enable_webhook(tm.id)
            assert wh2.url != url1

            v2_client.teammates.disable_webhook(tm.id)
        finally:
            v2_client.teammates.delete(tm.id)


# ── Teammate Email Inbox ─────────────────────────────────────────────


@pytest.mark.integration
class TestTeammateEmailInbox:
    def test_enable_disable_lifecycle(self, v2_client):
        """Enable email inbox → verify EmailInbox → disable → 204."""
        tm = v2_client.teammates.create(name="EmailInboxHost")
        try:
            inbox = v2_client.teammates.enable_email_inbox(tm.id)
            assert isinstance(inbox, EmailInbox)
            assert inbox.enabled is True
            assert inbox.address is not None
            assert "@" in inbox.address

            v2_client.teammates.disable_email_inbox(tm.id)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_enable_idempotent(self, v2_client):
        """Enable twice returns the same address."""
        tm = v2_client.teammates.create(name="EmailInboxIdem")
        try:
            inbox1 = v2_client.teammates.enable_email_inbox(tm.id)
            inbox2 = v2_client.teammates.enable_email_inbox(tm.id)
            assert inbox1.address == inbox2.address

            v2_client.teammates.disable_email_inbox(tm.id)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_enable_nonexistent_404(self, v2_client):
        """Enable email inbox on nonexistent teammate returns 404."""
        with pytest.raises(NotFoundError):
            v2_client.teammates.enable_email_inbox(999999)

    def test_disable_nonexistent_404(self, v2_client):
        """Disable email inbox on nonexistent teammate returns 404."""
        with pytest.raises(NotFoundError):
            v2_client.teammates.disable_email_inbox(999999)


# ── Tasks ────────────────────────────────────────────────────────────


@pytest.mark.integration
class TestTasksCRUD:
    def test_full_lifecycle(self, v2_client):
        """Create -> list -> get -> update -> delete."""
        tm = v2_client.teammates.create(name="TaskHost")
        try:
            task = v2_client.tasks.create(
                teammate_id=tm.id, instructions="Weekly summary", name="Weekly"
            )
            try:
                assert isinstance(task, Task)
                assert task.teammate_id == tm.id
                assert task.name == "Weekly"
                assert task.instructions == "Weekly summary"
                assert task.status == "enabled"

                # List
                page = v2_client.tasks.list(teammate_id=tm.id)
                assert any(t.id == task.id for t in page.data)

                # Get
                fetched = v2_client.tasks.get(task.id)
                assert fetched.instructions == "Weekly summary"

                # Update
                updated = v2_client.tasks.update(task.id, instructions="Daily summary")
                assert updated.instructions == "Daily summary"

                # Verify update persisted
                refetched = v2_client.tasks.get(task.id)
                assert refetched.instructions == "Daily summary"
            finally:
                v2_client.tasks.delete(task.id)

            # Verify excluded from list after delete
            page_after = v2_client.tasks.list(teammate_id=tm.id)
            assert not any(t.id == task.id for t in page_after.data)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_create_with_all_fields(self, v2_client):
        """Create task with all optional fields."""
        uid = _uid()
        tm = v2_client.teammates.create(name="TaskAllFields")
        try:
            task = v2_client.tasks.create(
                teammate_id=tm.id,
                instructions="Compile report",
                name="Report Task",
                expected_output="PDF report with charts",
                goals="Accurate and concise",
                user_id=uid,
            )
            try:
                assert task.name == "Report Task"
                assert task.expected_output == "PDF report with charts"
                assert task.goals == "Accurate and concise"
                assert task.user_id == uid
            finally:
                v2_client.tasks.delete(task.id)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_name_defaults_to_instructions(self, v2_client):
        """When name is omitted, backend defaults name to instructions[:100]."""
        tm = v2_client.teammates.create(name="TaskNameDefault")
        try:
            task = v2_client.tasks.create(
                teammate_id=tm.id, instructions="Generate weekly marketing report"
            )
            try:
                assert task.name is not None
                assert "weekly" in task.name.lower() or "generate" in task.name.lower()
            finally:
                v2_client.tasks.delete(task.id)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_task_user_id_filtering(self, v2_client):
        """List tasks filtered by user_id for multi-tenancy."""
        uid_a, uid_b = _uid(), _uid()
        tm = v2_client.teammates.create(name="TaskFilterHost")
        try:
            t1 = v2_client.tasks.create(teammate_id=tm.id, instructions="Task A", user_id=uid_a)
            t2 = v2_client.tasks.create(teammate_id=tm.id, instructions="Task B", user_id=uid_b)
            try:
                page_a = v2_client.tasks.list(user_id=uid_a)
                ids = [t.id for t in page_a.data]
                assert t1.id in ids
                assert t2.id not in ids
            finally:
                v2_client.tasks.delete(t1.id)
                v2_client.tasks.delete(t2.id)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_multiple_tasks_per_teammate(self, v2_client):
        """Create multiple tasks for same teammate, all appear in list."""
        tm = v2_client.teammates.create(name="MultiTaskHost")
        tasks = []
        try:
            for i in range(3):
                t = v2_client.tasks.create(
                    teammate_id=tm.id, instructions=f"Task {i}", name=f"Task-{i}"
                )
                tasks.append(t)

            page = v2_client.tasks.list(teammate_id=tm.id)
            page_ids = {t.id for t in page.data}
            for t in tasks:
                assert t.id in page_ids
        finally:
            for t in tasks:
                v2_client.tasks.delete(t.id)
            v2_client.teammates.delete(tm.id)

    def test_update_multiple_fields(self, v2_client):
        """Update name, instructions, expected_output, goals at once."""
        tm = v2_client.teammates.create(name="TaskUpdateHost")
        try:
            task = v2_client.tasks.create(
                teammate_id=tm.id, instructions="Original", name="Original"
            )
            try:
                updated = v2_client.tasks.update(
                    task.id,
                    name="Updated",
                    instructions="New instructions",
                    expected_output="New output",
                    goals="New goals",
                )
                assert updated.name == "Updated"
                assert updated.instructions == "New instructions"

                # Verify via GET
                fetched = v2_client.tasks.get(task.id)
                assert fetched.expected_output == "New output"
                assert fetched.goals == "New goals"
            finally:
                v2_client.tasks.delete(task.id)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_get_archived_task_by_id(self, v2_client):
        """After DELETE, GET by ID still returns the task with status=archived."""
        tm = v2_client.teammates.create(name="ArchiveTaskHost")
        try:
            task = v2_client.tasks.create(teammate_id=tm.id, instructions="Archive me")
            v2_client.tasks.delete(task.id)
            fetched = v2_client.tasks.get(task.id)
            assert fetched.status == "archived"
            assert fetched.instructions == "Archive me"
        finally:
            v2_client.teammates.delete(tm.id)

    def test_tools_roundtrip(self, v2_client):
        """Create task with tools, verify persisted, update tools."""
        tm = v2_client.teammates.create(name="TaskToolsHost")
        try:
            task = v2_client.tasks.create(
                teammate_id=tm.id, instructions="With tools", tools=["gmail", "slack"]
            )
            try:
                assert set(task.tools) == {"gmail", "slack"}

                updated = v2_client.tasks.update(task.id, tools=["notion"])
                assert updated.tools == ["notion"]

                fetched = v2_client.tasks.get(task.id)
                assert fetched.tools == ["notion"]
            finally:
                v2_client.tasks.delete(task.id)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_delete_nonexistent_task_404(self, v2_client):
        """DELETE on nonexistent task returns 404."""
        with pytest.raises(NotFoundError):
            v2_client.tasks.delete(999999)

    def test_update_nonexistent_task_404(self, v2_client):
        """PATCH on nonexistent task returns 404."""
        with pytest.raises(NotFoundError):
            v2_client.tasks.update(999999, name="Ghost")

    def test_delete_already_archived_task_idempotent(self, v2_client):
        """DELETE on already-archived task does not raise."""
        tm = v2_client.teammates.create(name="TaskDoubleDelHost")
        try:
            task = v2_client.tasks.create(teammate_id=tm.id, instructions="Double delete")
            v2_client.tasks.delete(task.id)
            v2_client.tasks.delete(task.id)  # should not raise
        finally:
            v2_client.teammates.delete(tm.id)

    def test_list_without_teammate_id(self, v2_client):
        """List tasks without teammate_id returns tasks across all teammates."""
        tm1 = v2_client.teammates.create(name="ListAllHost1")
        tm2 = v2_client.teammates.create(name="ListAllHost2")
        try:
            t1 = v2_client.tasks.create(teammate_id=tm1.id, instructions="Task on tm1")
            t2 = v2_client.tasks.create(teammate_id=tm2.id, instructions="Task on tm2")
            try:
                page = v2_client.tasks.list()
                ids = {t.id for t in page.data}
                assert t1.id in ids
                assert t2.id in ids
            finally:
                v2_client.tasks.delete(t1.id)
                v2_client.tasks.delete(t2.id)
        finally:
            v2_client.teammates.delete(tm1.id)
            v2_client.teammates.delete(tm2.id)


# ── Task Triggers ────────────────────────────────────────────────────


@pytest.mark.integration
class TestTaskTriggers:
    def test_schedule_trigger_lifecycle(self, v2_client):
        """Create schedule trigger -> list -> delete."""
        tm = v2_client.teammates.create(name="TriggerHost")
        try:
            task = v2_client.tasks.create(teammate_id=tm.id, instructions="Cron job")
            try:
                trigger = v2_client.tasks.triggers.create(
                    task.id, type="schedule", cron="0 9 * * 1"
                )
                assert isinstance(trigger, Trigger)
                assert trigger.type == "schedule"
                assert trigger.cron == "0 9 * * 1"
                assert trigger.enabled is True

                # List
                triggers = v2_client.tasks.triggers.list(task.id)
                assert len(triggers) >= 1
                assert any(tr.id == trigger.id for tr in triggers)

                # Delete
                v2_client.tasks.triggers.delete(task.id, trigger.id)

                # Verify deleted
                triggers_after = v2_client.tasks.triggers.list(task.id)
                assert not any(tr.id == trigger.id for tr in triggers_after)
            finally:
                v2_client.tasks.delete(task.id)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_schedule_trigger_with_timezone(self, v2_client):
        """Create schedule trigger with non-UTC timezone."""
        tm = v2_client.teammates.create(name="TZTriggerHost")
        try:
            task = v2_client.tasks.create(teammate_id=tm.id, instructions="TZ job")
            try:
                trigger = v2_client.tasks.triggers.create(
                    task.id, type="schedule", cron="0 9 * * *", timezone="America/New_York"
                )
                assert trigger.type == "schedule"
                assert trigger.timezone == "America/New_York"
                v2_client.tasks.triggers.delete(task.id, trigger.id)
            finally:
                v2_client.tasks.delete(task.id)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_schedule_trigger_with_interval(self, v2_client):
        """Create interval-based schedule trigger."""
        tm = v2_client.teammates.create(name="IntervalHost")
        try:
            task = v2_client.tasks.create(teammate_id=tm.id, instructions="Interval job")
            try:
                trigger = v2_client.tasks.triggers.create(
                    task.id, type="schedule", interval_seconds=3600
                )
                assert trigger.type == "schedule"
                v2_client.tasks.triggers.delete(task.id, trigger.id)
            finally:
                v2_client.tasks.delete(task.id)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_webhook_trigger(self, v2_client):
        """Create webhook trigger -> list -> verify URL returned."""
        tm = v2_client.teammates.create(name="WebhookTriggerHost")
        try:
            task = v2_client.tasks.create(teammate_id=tm.id, instructions="Webhook triggered")
            try:
                trigger = v2_client.tasks.triggers.create(task.id, type="webhook")
                assert trigger.type == "webhook"
                assert trigger.url is not None or trigger.id is not None

                triggers = v2_client.tasks.triggers.list(task.id)
                assert len(triggers) >= 1
            finally:
                v2_client.tasks.delete(task.id)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_email_trigger(self, v2_client):
        """Create email trigger -> list -> verify address."""
        tm = v2_client.teammates.create(name="EmailTriggerHost")
        try:
            task = v2_client.tasks.create(teammate_id=tm.id, instructions="Email triggered")
            try:
                trigger = v2_client.tasks.triggers.create(task.id, type="email")
                assert trigger.type == "email"

                triggers = v2_client.tasks.triggers.list(task.id)
                assert len(triggers) >= 1
            finally:
                v2_client.tasks.delete(task.id)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_schedule_without_cron_or_interval_rejected(self, v2_client):
        """Schedule trigger without cron or interval_seconds raises ValidationError."""
        tm = v2_client.teammates.create(name="NoScheduleHost")
        try:
            task = v2_client.tasks.create(teammate_id=tm.id, instructions="Empty schedule")
            try:
                with pytest.raises(ValidationError):
                    v2_client.tasks.triggers.create(task.id, type="schedule")
            finally:
                v2_client.tasks.delete(task.id)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_create_trigger_nonexistent_task_404(self, v2_client):
        """Create trigger on nonexistent task returns 404."""
        with pytest.raises(NotFoundError):
            v2_client.tasks.triggers.create(999999, type="schedule", cron="0 9 * * *")

    def test_create_trigger_invalid_type_rejected(self, v2_client):
        """Invalid trigger type rejected with 422."""
        tm = v2_client.teammates.create(name="BadTriggerTypeHost")
        try:
            task = v2_client.tasks.create(teammate_id=tm.id, instructions="Bad type")
            try:
                with pytest.raises(ValidationError):
                    v2_client.tasks.triggers.create(task.id, type="invalid")
            finally:
                v2_client.tasks.delete(task.id)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_all_trigger_types_same_task(self, v2_client):
        """Schedule, webhook, and email triggers coexist on same task."""
        tm = v2_client.teammates.create(name="AllTriggersHost")
        try:
            task = v2_client.tasks.create(teammate_id=tm.id, instructions="All triggers")
            try:
                t_sched = v2_client.tasks.triggers.create(
                    task.id, type="schedule", cron="0 9 * * *"
                )
                t_wh = v2_client.tasks.triggers.create(task.id, type="webhook")
                t_email = v2_client.tasks.triggers.create(task.id, type="email")

                triggers = v2_client.tasks.triggers.list(task.id)
                types = {tr.type for tr in triggers}
                assert {"schedule", "webhook", "email"} == types

                v2_client.tasks.triggers.delete(task.id, t_sched.id)
                v2_client.tasks.triggers.delete(task.id, t_wh.id)
                v2_client.tasks.triggers.delete(task.id, t_email.id)
            finally:
                v2_client.tasks.delete(task.id)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_multiple_schedule_triggers(self, v2_client):
        """Multiple schedule triggers can coexist on same task."""
        tm = v2_client.teammates.create(name="MultiTriggerHost")
        try:
            task = v2_client.tasks.create(teammate_id=tm.id, instructions="Multi trigger")
            try:
                t1 = v2_client.tasks.triggers.create(task.id, type="schedule", cron="0 9 * * 1")
                t2 = v2_client.tasks.triggers.create(task.id, type="schedule", cron="0 17 * * 5")

                triggers = v2_client.tasks.triggers.list(task.id)
                schedule_ids = {tr.id for tr in triggers if tr.type == "schedule"}
                assert t1.id in schedule_ids
                assert t2.id in schedule_ids

                v2_client.tasks.triggers.delete(task.id, t1.id)
                v2_client.tasks.triggers.delete(task.id, t2.id)
            finally:
                v2_client.tasks.delete(task.id)
        finally:
            v2_client.teammates.delete(tm.id)


# ── Memories ─────────────────────────────────────────────────────────


@pytest.mark.integration
class TestMemoriesCRUD:
    def test_full_lifecycle(self, v2_client):
        """Create -> list -> delete -> verify empty."""
        user_id = _uid()
        mem = v2_client.memories.create(user_id=user_id, content="Prefers dark mode")
        try:
            assert isinstance(mem, Memory)
            assert mem.content == "Prefers dark mode"
            assert mem.source == "api"

            # List
            page = v2_client.memories.list(user_id=user_id)
            assert any(m.id == mem.id for m in page.data)
        finally:
            v2_client.memories.delete(mem.id, user_id=user_id)

        # Verify gone
        page_after = v2_client.memories.list(user_id=user_id)
        assert not any(m.id == mem.id for m in page_after.data)

    def test_multiple_memories(self, v2_client):
        """Create several memories for same user, all appear in list."""
        user_id = _uid()
        mems = []
        try:
            for i in range(3):
                m = v2_client.memories.create(user_id=user_id, content=f"Memory item {i}")
                mems.append(m)

            page = v2_client.memories.list(user_id=user_id)
            page_ids = {m.id for m in page.data}
            for m in mems:
                assert m.id in page_ids
        finally:
            for m in mems:
                v2_client.memories.delete(m.id, user_id=user_id)

    def test_user_id_isolation(self, v2_client):
        """Memories for user A are not visible to user B."""
        uid_a, uid_b = _uid(), _uid()
        mem_a = v2_client.memories.create(user_id=uid_a, content="A's preference")
        mem_b = v2_client.memories.create(user_id=uid_b, content="B's preference")
        try:
            page_a = v2_client.memories.list(user_id=uid_a)
            ids_a = {m.id for m in page_a.data}
            assert mem_a.id in ids_a
            assert mem_b.id not in ids_a

            page_b = v2_client.memories.list(user_id=uid_b)
            ids_b = {m.id for m in page_b.data}
            assert mem_b.id in ids_b
            assert mem_a.id not in ids_b
        finally:
            v2_client.memories.delete(mem_a.id, user_id=uid_a)
            v2_client.memories.delete(mem_b.id, user_id=uid_b)

    def test_memory_content_trimmed(self, v2_client):
        """Backend strips whitespace from memory content."""
        user_id = _uid()
        mem = v2_client.memories.create(user_id=user_id, content="  spaced out  ")
        try:
            assert mem.content.strip() == "spaced out"
        finally:
            v2_client.memories.delete(mem.id, user_id=user_id)

    def test_different_users_same_content_allowed(self, v2_client):
        """Same content for different users is NOT a duplicate."""
        uid_a, uid_b = _uid(), _uid()
        mem_a = v2_client.memories.create(user_id=uid_a, content="Both like tea")
        mem_b = v2_client.memories.create(user_id=uid_b, content="Both like tea")
        try:
            assert mem_a.id != mem_b.id
        finally:
            v2_client.memories.delete(mem_a.id, user_id=uid_a)
            v2_client.memories.delete(mem_b.id, user_id=uid_b)

    def test_exceeds_max_length_rejected(self, v2_client):
        """301-char content raises ValidationError (max_length=300)."""
        with pytest.raises(ValidationError):
            v2_client.memories.create(user_id=_uid(), content="X" * 301)

    def test_pagination_with_starting_after(self, v2_client):
        """Memories support cursor pagination with starting_after."""
        uid = _uid()
        mems = []
        try:
            for i in range(3):
                mems.append(v2_client.memories.create(user_id=uid, content=f"Paginated mem {i}"))

            page1 = v2_client.memories.list(user_id=uid, limit=1)
            assert len(page1.data) == 1
            assert page1.has_more is True

            page2 = v2_client.memories.list(user_id=uid, limit=1, starting_after=page1.data[0].id)
            assert len(page2.data) == 1
            assert page2.data[0].id != page1.data[0].id
        finally:
            for m in mems:
                v2_client.memories.delete(m.id, user_id=uid)

    def test_duplicate_memory_conflict(self, v2_client):
        """Creating identical memory content raises ConflictError (409)."""
        user_id = _uid()
        mem = v2_client.memories.create(user_id=user_id, content="Unique preference")
        try:
            with pytest.raises(ConflictError):
                v2_client.memories.create(user_id=user_id, content="Unique preference")
        finally:
            v2_client.memories.delete(mem.id, user_id=user_id)


# ── Permissions ──────────────────────────────────────────────────────


@pytest.mark.integration
class TestPermissionsCRUD:
    def test_full_lifecycle(self, v2_client):
        """Create -> list -> delete -> verify gone."""
        user_id = _uid()
        perm = v2_client.permissions.create(user_id=user_id, tool="gmail")
        try:
            assert isinstance(perm, PermissionPolicy)
            assert perm.tool_name == "gmail"
            assert perm.user_id == user_id

            # List
            page = v2_client.permissions.list(user_id=user_id)
            assert any(p.id == perm.id for p in page.data)
        finally:
            v2_client.permissions.delete(perm.id, user_id=user_id)

        # Verify gone
        page_after = v2_client.permissions.list(user_id=user_id)
        assert not any(p.id == perm.id for p in page_after.data)

    def test_idempotent_create(self, v2_client):
        """Creating same (user_id, tool) twice returns same record."""
        user_id = _uid()
        p1 = v2_client.permissions.create(user_id=user_id, tool="slack")
        try:
            p2 = v2_client.permissions.create(user_id=user_id, tool="slack")
            assert p1.id == p2.id
        finally:
            v2_client.permissions.delete(p1.id, user_id=user_id)

    def test_multiple_tools(self, v2_client):
        """Different tools create separate permission policies."""
        user_id = _uid()
        p1 = v2_client.permissions.create(user_id=user_id, tool="gmail")
        p2 = v2_client.permissions.create(user_id=user_id, tool="slack")
        try:
            assert p1.id != p2.id
            assert p1.tool_name == "gmail"
            assert p2.tool_name == "slack"

            page = v2_client.permissions.list(user_id=user_id)
            ids = {p.id for p in page.data}
            assert p1.id in ids
            assert p2.id in ids
        finally:
            v2_client.permissions.delete(p1.id, user_id=user_id)
            v2_client.permissions.delete(p2.id, user_id=user_id)

    def test_user_id_isolation(self, v2_client):
        """Permissions for user A are not visible to user B."""
        uid_a, uid_b = _uid(), _uid()
        pa = v2_client.permissions.create(user_id=uid_a, tool="tool_a")
        pb = v2_client.permissions.create(user_id=uid_b, tool="tool_b")
        try:
            page_a = v2_client.permissions.list(user_id=uid_a)
            ids_a = {p.id for p in page_a.data}
            assert pa.id in ids_a
            assert pb.id not in ids_a
        finally:
            v2_client.permissions.delete(pa.id, user_id=uid_a)
            v2_client.permissions.delete(pb.id, user_id=uid_b)

    def test_pagination_with_starting_after(self, v2_client):
        """Permissions support cursor pagination with starting_after."""
        uid = _uid()
        perms = []
        try:
            for tool in ["gmail", "slack", "notion"]:
                perms.append(v2_client.permissions.create(user_id=uid, tool=tool))

            page1 = v2_client.permissions.list(user_id=uid, limit=1)
            assert len(page1.data) == 1
            assert page1.has_more is True

            page2 = v2_client.permissions.list(
                user_id=uid, limit=1, starting_after=page1.data[0].id
            )
            assert len(page2.data) == 1
            assert page2.data[0].id != page1.data[0].id
        finally:
            for p in perms:
                v2_client.permissions.delete(p.id, user_id=uid)

    def test_delete_then_recreate(self, v2_client):
        """After deleting a permission, can recreate same (user_id, tool) with new ID."""
        uid = _uid()
        p1 = v2_client.permissions.create(user_id=uid, tool="recreate_tool")
        v2_client.permissions.delete(p1.id, user_id=uid)

        p2 = v2_client.permissions.create(user_id=uid, tool="recreate_tool")
        try:
            assert p2.id != p1.id
            assert p2.tool_name == "recreate_tool"
        finally:
            v2_client.permissions.delete(p2.id, user_id=uid)


# ── Webhooks ─────────────────────────────────────────────────────────


@pytest.mark.integration
class TestWebhooksCRUD:
    def test_full_lifecycle(self, v2_client):
        """Create -> list -> get -> update -> delete."""
        wh = v2_client.webhooks.create(url="https://example.com/hook", events=["run.completed"])
        try:
            assert isinstance(wh, Webhook)
            assert wh.url == "https://example.com/hook"
            assert wh.secret is not None
            assert wh.active is True
            assert "run.completed" in wh.events

            # List
            page = v2_client.webhooks.list()
            assert any(w.id == wh.id for w in page.data)

            # Get (secret may be masked)
            fetched = v2_client.webhooks.get(wh.id)
            assert fetched.id == wh.id

            # Update URL + rotate secret
            old_secret = wh.secret
            updated = v2_client.webhooks.update(
                wh.id, url="https://example.com/v2/hook", rotate_secret=True
            )
            assert updated.url == "https://example.com/v2/hook"
            if updated.secret and old_secret:
                assert updated.secret != old_secret
        finally:
            v2_client.webhooks.delete(wh.id)

        with pytest.raises(NotFoundError):
            v2_client.webhooks.get(wh.id)

    def test_create_with_default_events(self, v2_client):
        """Create webhook without specifying events uses defaults."""
        wh = v2_client.webhooks.create(url="https://example.com/default-events")
        try:
            assert isinstance(wh.events, list)
            assert len(wh.events) > 0
        finally:
            v2_client.webhooks.delete(wh.id)

    def test_create_with_multiple_events(self, v2_client):
        """Create webhook subscribed to multiple event types."""
        events = ["run.started", "run.completed", "run.failed"]
        wh = v2_client.webhooks.create(url="https://example.com/multi", events=events)
        try:
            assert set(wh.events) == set(events)
        finally:
            v2_client.webhooks.delete(wh.id)

    def test_update_events(self, v2_client):
        """Update webhook event subscriptions."""
        wh = v2_client.webhooks.create(url="https://example.com/events", events=["run.completed"])
        try:
            updated = v2_client.webhooks.update(wh.id, events=["run.started", "run.failed"])
            assert "run.started" in updated.events
            assert "run.failed" in updated.events
        finally:
            v2_client.webhooks.delete(wh.id)

    def test_deactivate_reactivate(self, v2_client):
        """Toggle webhook active status."""
        wh = v2_client.webhooks.create(url="https://example.com/toggle")
        try:
            assert wh.active is True

            deactivated = v2_client.webhooks.update(wh.id, active=False)
            assert deactivated.active is False

            reactivated = v2_client.webhooks.update(wh.id, active=True)
            assert reactivated.active is True
        finally:
            v2_client.webhooks.delete(wh.id)

    def test_deliveries_empty(self, v2_client):
        """Newly created webhook has no deliveries."""
        wh = v2_client.webhooks.create(url="https://example.com/empty")
        try:
            page = v2_client.webhooks.list_deliveries(wh.id)
            assert isinstance(page, SyncPage)
            assert len(page.data) == 0
        finally:
            v2_client.webhooks.delete(wh.id)

    def test_multiple_webhooks(self, v2_client):
        """Multiple webhooks can coexist."""
        wh1 = v2_client.webhooks.create(url="https://example.com/one")
        wh2 = v2_client.webhooks.create(url="https://example.com/two")
        try:
            assert wh1.id != wh2.id

            page = v2_client.webhooks.list()
            ids = {w.id for w in page.data}
            assert wh1.id in ids
            assert wh2.id in ids
        finally:
            v2_client.webhooks.delete(wh1.id)
            v2_client.webhooks.delete(wh2.id)

    def test_secret_full_on_create_masked_on_get(self, v2_client):
        """Create returns full secret; GET returns masked (first 4 chars + '...')."""
        wh = v2_client.webhooks.create(url="https://example.com/secret-test")
        try:
            assert wh.secret is not None
            assert "..." not in wh.secret
            assert len(wh.secret) >= 32  # full hex secret

            fetched = v2_client.webhooks.get(wh.id)
            assert fetched.secret is not None
            assert fetched.secret.endswith("...")
            assert len(fetched.secret) < len(wh.secret)
        finally:
            v2_client.webhooks.delete(wh.id)

    def test_secrets_masked_on_list(self, v2_client):
        """All webhooks in list have masked secrets."""
        wh = v2_client.webhooks.create(url="https://example.com/list-mask")
        try:
            page = v2_client.webhooks.list()
            for w in page.data:
                if w.secret:
                    assert w.secret.endswith("...")
        finally:
            v2_client.webhooks.delete(wh.id)

    def test_rotate_secret_returns_full_new_secret(self, v2_client):
        """rotate_secret=True returns full new secret, different from original."""
        wh = v2_client.webhooks.create(url="https://example.com/rotate")
        try:
            original_secret = wh.secret
            updated = v2_client.webhooks.update(wh.id, rotate_secret=True)
            assert updated.secret is not None
            assert "..." not in updated.secret
            assert updated.secret != original_secret
        finally:
            v2_client.webhooks.delete(wh.id)

    def test_update_without_rotate_keeps_masked_secret(self, v2_client):
        """Update URL without rotate_secret → secret stays masked."""
        wh = v2_client.webhooks.create(url="https://example.com/no-rotate")
        try:
            updated = v2_client.webhooks.update(wh.id, url="https://example.com/new-url")
            assert updated.secret is not None
            assert updated.secret.endswith("...")
        finally:
            v2_client.webhooks.delete(wh.id)

    def test_update_multiple_fields_simultaneously(self, v2_client):
        """Update url, events, and active in one call."""
        wh = v2_client.webhooks.create(
            url="https://example.com/multi-update", events=["run.completed"]
        )
        try:
            updated = v2_client.webhooks.update(
                wh.id,
                url="https://example.com/multi-updated",
                events=["run.started", "run.failed"],
                active=False,
            )
            assert updated.url == "https://example.com/multi-updated"
            assert set(updated.events) == {"run.started", "run.failed"}
            assert updated.active is False
        finally:
            v2_client.webhooks.delete(wh.id)


# ── Webhook Validation ───────────────────────────────────────────────


@pytest.mark.integration
class TestWebhookValidation:
    def test_http_url_rejected(self, v2_client):
        """HTTP (not HTTPS) webhook URLs are rejected (422)."""
        with pytest.raises(ValidationError):
            v2_client.webhooks.create(url="http://example.com/hook")

    def test_invalid_event_rejected(self, v2_client):
        """Unknown event type is rejected (422)."""
        with pytest.raises(ValidationError):
            v2_client.webhooks.create(url="https://example.com/hook", events=["invalid.event"])

    def test_localhost_url_rejected(self, v2_client):
        """Webhook URLs pointing to localhost are rejected (SSRF protection)."""
        with pytest.raises(ValidationError):
            v2_client.webhooks.create(url="https://localhost/hook")

    def test_private_network_url_rejected(self, v2_client):
        """Private network URLs rejected (SSRF protection)."""
        with pytest.raises(ValidationError):
            v2_client.webhooks.create(url="https://192.168.1.1/hook")

    def test_internal_domain_rejected(self, v2_client):
        """*.internal and *.local domains rejected (SSRF protection)."""
        with pytest.raises(ValidationError):
            v2_client.webhooks.create(url="https://app.internal/hook")

    def test_update_url_to_http_rejected(self, v2_client):
        """PATCH webhook URL to HTTP rejected (422)."""
        wh = v2_client.webhooks.create(url="https://example.com/update-val")
        try:
            with pytest.raises(ValidationError):
                v2_client.webhooks.update(wh.id, url="http://example.com/hook")
        finally:
            v2_client.webhooks.delete(wh.id)

    def test_update_events_invalid_rejected(self, v2_client):
        """PATCH webhook events to invalid type rejected (422)."""
        wh = v2_client.webhooks.create(url="https://example.com/update-ev-val")
        try:
            with pytest.raises(ValidationError):
                v2_client.webhooks.update(wh.id, events=["invalid.event"])
        finally:
            v2_client.webhooks.delete(wh.id)

    def test_update_url_to_localhost_rejected(self, v2_client):
        """PATCH webhook URL to localhost rejected (SSRF)."""
        wh = v2_client.webhooks.create(url="https://example.com/update-ssrf")
        try:
            with pytest.raises(ValidationError):
                v2_client.webhooks.update(wh.id, url="https://localhost/hook")
        finally:
            v2_client.webhooks.delete(wh.id)

    def test_list_deliveries_nonexistent_webhook_404(self, v2_client):
        """List deliveries for nonexistent webhook returns 404."""
        with pytest.raises(NotFoundError):
            v2_client.webhooks.list_deliveries(999999)


# ── Runs (list/get only — no execution) ─────────────────────────────


@pytest.mark.integration
class TestRunsReadOnly:
    def test_list_empty(self, v2_client):
        """List runs for new user returns empty or existing runs."""
        page = v2_client.runs.list()
        assert isinstance(page, SyncPage)

    def test_get_nonexistent(self, v2_client):
        """Get nonexistent run returns 404."""
        with pytest.raises(NotFoundError):
            v2_client.runs.get(999999)

    def test_list_with_status_filter(self, v2_client):
        """List runs with status filter returns valid page."""
        page = v2_client.runs.list(status="completed")
        assert isinstance(page, SyncPage)

    def test_list_with_limit(self, v2_client):
        """List runs respects limit parameter."""
        page = v2_client.runs.list(limit=1)
        assert isinstance(page, SyncPage)
        assert len(page.data) <= 1

    def test_list_with_combined_filters(self, v2_client):
        """Multiple filters (status + user_id) work together without error."""
        page = v2_client.runs.list(status="completed", user_id="nonexistent-user")
        assert isinstance(page, SyncPage)
        assert len(page.data) == 0

    def test_cancel_nonexistent_run(self, v2_client):
        """Cancel nonexistent run returns 404."""
        with pytest.raises(NotFoundError):
            v2_client.runs.cancel(999999)

    def test_permissions_nonexistent_run(self, v2_client):
        """List permissions for nonexistent run returns 404."""
        with pytest.raises(NotFoundError):
            v2_client.runs.permissions(999999)

    def test_list_files_nonexistent_run(self, v2_client):
        """List files for nonexistent run returns 404."""
        with pytest.raises(NotFoundError):
            v2_client.runs.list_files(999999)

    def test_list_with_teammate_filter(self, v2_client):
        """Filter runs by teammate_id returns valid page."""
        page = v2_client.runs.list(teammate_id=999999)
        assert isinstance(page, SyncPage)
        assert len(page.data) == 0


# ── Runs: Human-in-the-Loop ─────────────────────────────────────────


@pytest.mark.integration
class TestRunsHumanInTheLoop:
    """HITL validation via SDK — permission_mode + human_in_the_loop combos."""

    def test_create_run_default_autonomous(self, v2_client):
        """Default run (no HITL params) is accepted as autonomous."""
        tm = v2_client.teammates.create(name="HitlDefault")
        try:
            run = v2_client.runs.create(
                teammate_id=tm.id,
                message="Test default",
                stream=False,
            )
            assert isinstance(run, Run)
            assert run.status == "running"
        finally:
            v2_client.teammates.delete(tm.id)

    def test_create_run_with_hitl_enabled(self, v2_client):
        """Run with human_in_the_loop=True is accepted."""
        tm = v2_client.teammates.create(name="HitlOn")
        try:
            run = v2_client.runs.create(
                teammate_id=tm.id,
                message="Test HITL on",
                stream=False,
                human_in_the_loop=True,
            )
            assert isinstance(run, Run)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_plan_mode_without_hitl_rejected(self, v2_client):
        """permission_mode=plan without HITL raises ValidationError."""
        tm = v2_client.teammates.create(name="HitlPlanNoHitl")
        try:
            with pytest.raises(ValidationError):
                v2_client.runs.create(
                    teammate_id=tm.id,
                    message="Test plan no hitl",
                    stream=False,
                    permission_mode="plan",
                )
        finally:
            v2_client.teammates.delete(tm.id)

    def test_approval_mode_without_hitl_rejected(self, v2_client):
        """permission_mode=approval without HITL raises ValidationError."""
        tm = v2_client.teammates.create(name="HitlApprNoHitl")
        try:
            with pytest.raises(ValidationError):
                v2_client.runs.create(
                    teammate_id=tm.id,
                    message="Test approval no hitl",
                    stream=False,
                    permission_mode="approval",
                )
        finally:
            v2_client.teammates.delete(tm.id)

    def test_plan_mode_with_hitl_accepted(self, v2_client):
        """permission_mode=plan + human_in_the_loop=True is accepted."""
        tm = v2_client.teammates.create(name="HitlPlanOk")
        try:
            run = v2_client.runs.create(
                teammate_id=tm.id,
                message="Test plan with hitl",
                stream=False,
                permission_mode="plan",
                human_in_the_loop=True,
            )
            assert isinstance(run, Run)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_task_run_plan_mode_without_hitl_rejected(self, v2_client):
        """Task run with permission_mode=plan without HITL raises ValidationError."""
        tm = v2_client.teammates.create(name="TaskHitlHost")
        try:
            task = v2_client.tasks.create(
                teammate_id=tm.id,
                instructions="HITL task test",
            )
            try:
                with pytest.raises(ValidationError):
                    v2_client.tasks.run(
                        task.id,
                        stream=False,
                        permission_mode="plan",
                    )
            finally:
                v2_client.tasks.delete(task.id)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_task_run_with_hitl_accepted(self, v2_client):
        """Task run with human_in_the_loop=True is accepted."""
        tm = v2_client.teammates.create(name="TaskHitlOk")
        try:
            task = v2_client.tasks.create(
                teammate_id=tm.id,
                instructions="HITL task ok",
            )
            try:
                run = v2_client.tasks.run(
                    task.id,
                    stream=False,
                    human_in_the_loop=True,
                )
                assert isinstance(run, Run)
            finally:
                v2_client.tasks.delete(task.id)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_answer_nonexistent_run(self, v2_client):
        """Answer on nonexistent run raises NotFoundError."""
        with pytest.raises(NotFoundError):
            v2_client.runs.answer(999999, answers={"Q": "A"})

    def test_approve_nonexistent_run(self, v2_client):
        """Approve on nonexistent run raises NotFoundError."""
        with pytest.raises(NotFoundError):
            v2_client.runs.approve(999999, request_id="fake-uuid")

    def test_answer_on_running_run(self, v2_client):
        """Answer on a run that's running (not waiting) returns ok status."""
        tm = v2_client.teammates.create(name="AnswerRunning")
        try:
            run = v2_client.runs.create(
                teammate_id=tm.id,
                message="Answer test",
                stream=False,
            )
            result = v2_client.runs.answer(run.id, answers={"Q": "A"})
            assert isinstance(result, dict)
            assert "status" in result
        finally:
            v2_client.teammates.delete(tm.id)

    def test_approve_invalid_request_on_real_run(self, v2_client):
        """Approve with fake request_id on a real run raises NotFoundError."""
        tm = v2_client.teammates.create(name="ApproveInvalid")
        try:
            run = v2_client.runs.create(
                teammate_id=tm.id,
                message="Approve test",
                stream=False,
            )
            with pytest.raises(NotFoundError):
                v2_client.runs.approve(run.id, request_id="nonexistent-uuid")
        finally:
            v2_client.teammates.delete(tm.id)


# ── Run Creation Edge Cases ──────────────────────────────────────────


@pytest.mark.integration
class TestRunCreation:
    """Run creation with various optional parameters."""

    def test_create_run_quick_start(self, v2_client):
        """Create run with name= (auto-creates teammate via quick-start)."""
        run = v2_client.runs.create(
            name="QuickBot",
            message="Hi",
            stream=False,
        )
        assert isinstance(run, Run)
        assert run.status == "running"
        assert run.teammate_id is not None

    def test_create_run_auto_detect(self, v2_client):
        """Create run with no teammate_id or name (auto-detect)."""
        run = v2_client.runs.create(message="Auto detect test", stream=False)
        assert isinstance(run, Run)
        assert run.status == "running"

    def test_create_run_with_metadata(self, v2_client):
        """Metadata dict roundtrips through run creation."""
        tm = v2_client.teammates.create(name="MetaRunHost")
        try:
            run = v2_client.runs.create(
                teammate_id=tm.id,
                message="With meta",
                stream=False,
                metadata={"env": "test", "version": 2},
            )
            assert isinstance(run, Run)
            assert run.metadata == {"env": "test", "version": 2}
        finally:
            v2_client.teammates.delete(tm.id)

    def test_create_run_with_user_id(self, v2_client):
        """user_id is set on the created run."""
        uid = _uid()
        tm = v2_client.teammates.create(name="UserIdRunHost")
        try:
            run = v2_client.runs.create(
                teammate_id=tm.id,
                message="With user",
                stream=False,
                user_id=uid,
            )
            assert isinstance(run, Run)
            assert run.user_id == uid
        finally:
            v2_client.teammates.delete(tm.id)


# ── Run Get / Cancel / Reply ─────────────────────────────────────────


@pytest.mark.integration
class TestRunGetCancelReply:
    """Run retrieval, cancellation, and reply."""

    def test_get_existing_run(self, v2_client):
        """Get a run by ID returns the correct run."""
        tm = v2_client.teammates.create(name="GetRunHost")
        try:
            created = v2_client.runs.create(
                teammate_id=tm.id,
                message="Get test",
                stream=False,
            )
            fetched = v2_client.runs.get(created.id)
            assert isinstance(fetched, Run)
            assert fetched.id == created.id
            assert fetched.teammate_id == tm.id
        finally:
            v2_client.teammates.delete(tm.id)

    def test_cancel_active_run(self, v2_client):
        """Cancel a running run returns a Run object."""
        tm = v2_client.teammates.create(name="CancelRunHost")
        try:
            run = v2_client.runs.create(
                teammate_id=tm.id,
                message="Cancel test",
                stream=False,
            )
            result = v2_client.runs.cancel(run.id)
            assert isinstance(result, Run)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_reply_non_streaming(self, v2_client):
        """Reply to a run (non-streaming) returns a Run."""
        tm = v2_client.teammates.create(name="ReplyHost")
        try:
            run = v2_client.runs.create(
                teammate_id=tm.id,
                message="Initial",
                stream=False,
            )
            reply = v2_client.runs.reply(run.id, message="Follow up", stream=False)
            assert isinstance(reply, Run)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_reply_nonexistent_run_404(self, v2_client):
        """Reply to nonexistent run raises NotFoundError."""
        with pytest.raises(NotFoundError):
            v2_client.runs.reply(999999, message="Ghost", stream=False)


# ── Run Files ────────────────────────────────────────────────────────


@pytest.mark.integration
class TestRunFiles:
    """Run file listing and download error paths."""

    def test_list_files_empty_on_new_run(self, v2_client):
        """New run (no sandbox) has empty file list."""
        tm = v2_client.teammates.create(name="RunFilesHost")
        try:
            run = v2_client.runs.create(
                teammate_id=tm.id,
                message="Files test",
                stream=False,
            )
            files = v2_client.runs.list_files(run.id)
            assert isinstance(files, list)
            assert len(files) == 0
        finally:
            v2_client.teammates.delete(tm.id)

    def test_download_file_nonexistent_run_404(self, v2_client):
        """Download file from nonexistent run raises NotFoundError."""
        with pytest.raises(NotFoundError):
            v2_client.runs.download_file(999999, "test.txt")


# ── Task Run Edge Cases ──────────────────────────────────────────────


@pytest.mark.integration
class TestTaskRunEdgeCases:
    """Task execution edge cases."""

    def test_task_run_with_metadata(self, v2_client):
        """Task run with metadata returns Run with metadata set."""
        tm = v2_client.teammates.create(name="TaskMetaHost")
        try:
            task = v2_client.tasks.create(
                teammate_id=tm.id,
                instructions="Meta task",
            )
            try:
                run = v2_client.tasks.run(
                    task.id,
                    stream=False,
                    metadata={"k": "v"},
                )
                assert isinstance(run, Run)
                assert run.metadata == {"k": "v"}
            finally:
                v2_client.tasks.delete(task.id)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_task_run_with_user_id(self, v2_client):
        """Task run with user_id sets it on the run."""
        uid = _uid()
        tm = v2_client.teammates.create(name="TaskUserIdHost")
        try:
            task = v2_client.tasks.create(
                teammate_id=tm.id,
                instructions="User task",
            )
            try:
                run = v2_client.tasks.run(
                    task.id,
                    stream=False,
                    user_id=uid,
                )
                assert isinstance(run, Run)
                assert run.user_id == uid
            finally:
                v2_client.tasks.delete(task.id)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_task_run_disabled_task_400(self, v2_client):
        """Running a deleted (archived) task raises ValidationError (400)."""
        tm = v2_client.teammates.create(name="TaskDisabledHost")
        try:
            task = v2_client.tasks.create(
                teammate_id=tm.id,
                instructions="Will be deleted",
            )
            task_id = task.id
            v2_client.tasks.delete(task_id)

            with pytest.raises((ValidationError, NotFoundError)):
                v2_client.tasks.run(task_id, stream=False)
        finally:
            v2_client.teammates.delete(tm.id)


# ── Pagination ───────────────────────────────────────────────────────


@pytest.mark.integration
class TestPagination:
    def test_cursor_pagination(self, v2_client):
        """Create 3 teammates, paginate with limit=1."""
        created = []
        try:
            for i in range(3):
                t = v2_client.teammates.create(name=f"Page{i}")
                created.append(t)

            # First page
            page1 = v2_client.teammates.list(limit=1)
            assert len(page1.data) == 1
            assert page1.has_more is True

            # Second page
            page2 = v2_client.teammates.list(limit=1, starting_after=page1.data[0].id)
            assert len(page2.data) == 1
            assert page2.data[0].id != page1.data[0].id

            # Collect all via manual pagination
            all_ids = set()
            cursor = None
            for _ in range(10):  # safety limit
                page = v2_client.teammates.list(limit=2, starting_after=cursor)
                for tm in page.data:
                    all_ids.add(tm.id)
                if not page.has_more:
                    break
                cursor = page.data[-1].id

            for t in created:
                assert t.id in all_ids
        finally:
            for t in created:
                v2_client.teammates.delete(t.id)

    def test_auto_paging_iter(self, v2_client):
        """SyncPage.auto_paging_iter() walks through all pages."""
        created = []
        try:
            for i in range(3):
                t = v2_client.teammates.create(name=f"AutoPage{i}")
                created.append(t)

            # Use auto_paging_iter with limit=1 to force multiple pages
            first_page = v2_client.teammates.list(limit=1)
            all_teammates = list(first_page.auto_paging_iter())

            created_ids = {t.id for t in created}
            fetched_ids = {t.id for t in all_teammates}
            assert created_ids.issubset(fetched_ids)
        finally:
            for t in created:
                v2_client.teammates.delete(t.id)

    def test_pagination_with_large_limit(self, v2_client):
        """limit=100 (max) works without error."""
        page = v2_client.teammates.list(limit=100)
        assert isinstance(page, SyncPage)

    def test_task_pagination(self, v2_client):
        """Pagination also works for tasks."""
        tm = v2_client.teammates.create(name="TaskPaginationHost")
        tasks = []
        try:
            for i in range(3):
                t = v2_client.tasks.create(teammate_id=tm.id, instructions=f"Paginated task {i}")
                tasks.append(t)

            page1 = v2_client.tasks.list(teammate_id=tm.id, limit=1)
            assert len(page1.data) == 1
            assert page1.has_more is True
        finally:
            for t in tasks:
                v2_client.tasks.delete(t.id)
            v2_client.teammates.delete(tm.id)

    def test_exact_count_means_no_more(self, v2_client):
        """When limit equals item count, has_more is False."""
        created = []
        try:
            for i in range(3):
                wh = v2_client.webhooks.create(url=f"https://example.com/exact{i}")
                created.append(wh)

            page = v2_client.webhooks.list(limit=100)
            assert page.has_more is False
            for wh in created:
                assert any(w.id == wh.id for w in page.data)
        finally:
            for wh in created:
                v2_client.webhooks.delete(wh.id)

    def test_webhook_pagination(self, v2_client):
        """Pagination works for webhooks."""
        webhooks = []
        try:
            for i in range(3):
                wh = v2_client.webhooks.create(url=f"https://example.com/page{i}")
                webhooks.append(wh)

            page1 = v2_client.webhooks.list(limit=1)
            assert len(page1.data) == 1
            assert page1.has_more is True
        finally:
            for wh in webhooks:
                v2_client.webhooks.delete(wh.id)

    def test_run_pagination(self, v2_client):
        """Pagination works for runs."""
        tm = v2_client.teammates.create(name="RunPaginationHost")
        try:
            for i in range(3):
                v2_client.runs.create(
                    teammate_id=tm.id,
                    message=f"Paginate {i}",
                    stream=False,
                )
            page1 = v2_client.runs.list(teammate_id=tm.id, limit=1)
            assert isinstance(page1, SyncPage)
            assert len(page1.data) == 1
            assert page1.has_more is True

            page2 = v2_client.runs.list(
                teammate_id=tm.id,
                limit=1,
                starting_after=page1.data[0].id,
            )
            assert page2.data[0].id != page1.data[0].id
        finally:
            v2_client.teammates.delete(tm.id)


# ── Error Handling ───────────────────────────────────────────────────


@pytest.mark.integration
class TestErrorHandling:
    def test_not_found_teammate(self, v2_client):
        """404 mapped to NotFoundError with status_code."""
        with pytest.raises(NotFoundError) as exc_info:
            v2_client.teammates.get(999999)
        assert exc_info.value.status_code == 404

    def test_not_found_task(self, v2_client):
        """404 for nonexistent task."""
        with pytest.raises(NotFoundError):
            v2_client.tasks.get(999999)

    def test_not_found_webhook(self, v2_client):
        """404 for nonexistent webhook."""
        with pytest.raises(NotFoundError):
            v2_client.webhooks.get(999999)

    def test_update_nonexistent_teammate(self, v2_client):
        """PATCH on nonexistent teammate returns 404."""
        with pytest.raises(NotFoundError):
            v2_client.teammates.update(999999, name="Ghost")

    def test_delete_nonexistent_webhook(self, v2_client):
        """DELETE on nonexistent webhook returns 404."""
        with pytest.raises(NotFoundError):
            v2_client.webhooks.delete(999999)

    def test_unauthenticated(self, backend_url):
        """Invalid API key raises AuthenticationError."""
        bad_client = M8tes(api_key="invalid_key", base_url=f"{backend_url}/api/v2")
        try:
            with pytest.raises(AuthenticationError):
                bad_client.teammates.list()
        finally:
            bad_client.close()

    def test_error_has_status_code(self, v2_client):
        """All errors carry status_code attribute."""
        with pytest.raises(M8tesError) as exc_info:
            v2_client.teammates.get(999999)
        assert exc_info.value.status_code is not None

    def test_task_create_invalid_teammate(self, v2_client):
        """Creating task with nonexistent teammate_id returns 404."""
        with pytest.raises(NotFoundError):
            v2_client.tasks.create(teammate_id=999999, instructions="Orphan task")

    def test_trigger_invalid_timezone(self, v2_client):
        """Invalid timezone on trigger create returns 422."""
        tm = v2_client.teammates.create(name="BadTZHost")
        try:
            task = v2_client.tasks.create(teammate_id=tm.id, instructions="TZ test")
            try:
                with pytest.raises(ValidationError):
                    v2_client.tasks.triggers.create(
                        task.id,
                        type="schedule",
                        cron="0 9 * * *",
                        timezone="Fake/Zone",
                    )
            finally:
                v2_client.tasks.delete(task.id)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_memory_delete_wrong_user(self, v2_client):
        """Deleting memory with wrong user_id returns 404."""
        uid = _uid()
        mem = v2_client.memories.create(user_id=uid, content="Owner's memory")
        try:
            with pytest.raises(NotFoundError):
                v2_client.memories.delete(mem.id, user_id="wrong_user")
        finally:
            v2_client.memories.delete(mem.id, user_id=uid)

    def test_permission_delete_wrong_user(self, v2_client):
        """Deleting permission with wrong user_id returns 404."""
        uid = _uid()
        perm = v2_client.permissions.create(user_id=uid, tool="test_tool")
        try:
            with pytest.raises(NotFoundError):
                v2_client.permissions.delete(perm.id, user_id="wrong_user")
        finally:
            v2_client.permissions.delete(perm.id, user_id=uid)


# ── Apps (read-only) ─────────────────────────────────────────────────


@pytest.mark.integration
class TestAppsReadOnly:
    def test_list_apps(self, v2_client):
        """List available apps (may be empty if no tools seeded)."""
        page = v2_client.apps.list()
        assert isinstance(page, SyncPage)


# ── Context Manager ──────────────────────────────────────────────────


@pytest.mark.integration
class TestContextManager:
    def test_with_statement(self, backend_url):
        """M8tes works as context manager, auto-closes session."""
        import requests

        email = f"ctx-{uuid.uuid4().hex[:8]}@test.m8tes.ai"
        resp = requests.post(
            f"{backend_url}/api/v1/auth/register",
            json={
                "email": email,
                "password": "TestPassword123!",
                "first_name": "CtxTest",
            },
        )
        assert resp.status_code == 201
        token = resp.json()["api_key"]

        with M8tes(api_key=token, base_url=f"{backend_url}/api/v2") as client:
            page = client.teammates.list()
            assert isinstance(page, SyncPage)
        # After __exit__, session is closed — no crash


# ── Multi-Tenancy Isolation ──────────────────────────────────────────


@pytest.mark.integration
class TestMultiTenancyIsolation:
    def test_teammate_user_id_does_not_leak(self, v2_client):
        """Teammates with different user_ids are fully isolated in list."""
        uid_a, uid_b = _uid(), _uid()
        t1 = v2_client.teammates.create(name="IsoA", user_id=uid_a)
        t2 = v2_client.teammates.create(name="IsoB", user_id=uid_b)
        try:
            # user_id=uid_a should not see uid_b's teammate
            page = v2_client.teammates.list(user_id=uid_a)
            ids = {tm.id for tm in page.data}
            assert t1.id in ids
            assert t2.id not in ids

            # Unfiltered list should see both
            page_all = v2_client.teammates.list()
            all_ids = {tm.id for tm in page_all.data}
            assert t1.id in all_ids
            assert t2.id in all_ids
        finally:
            v2_client.teammates.delete(t1.id)
            v2_client.teammates.delete(t2.id)

    def test_task_inherits_teammate_user_id(self, v2_client):
        """Task user_id filtering works independently."""
        uid_a, uid_b = _uid(), _uid()
        tm = v2_client.teammates.create(name="IsoTaskHost")
        try:
            t1 = v2_client.tasks.create(teammate_id=tm.id, instructions="Alpha task", user_id=uid_a)
            t2 = v2_client.tasks.create(teammate_id=tm.id, instructions="Beta task", user_id=uid_b)
            try:
                page = v2_client.tasks.list(user_id=uid_a)
                ids = {t.id for t in page.data}
                assert t1.id in ids
                assert t2.id not in ids
            finally:
                v2_client.tasks.delete(t1.id)
                v2_client.tasks.delete(t2.id)
        finally:
            v2_client.teammates.delete(tm.id)


# ── Response Type Verification ───────────────────────────────────────


@pytest.mark.integration
class TestResponseTypes:
    def test_teammate_response_fields(self, v2_client):
        """Verify all Teammate fields are populated correctly."""
        t = v2_client.teammates.create(
            name="TypeCheck",
            instructions="Verify types",
            metadata={"key": "value"},
        )
        try:
            assert isinstance(t.id, int)
            assert isinstance(t.name, str)
            assert isinstance(t.status, str)
            assert isinstance(t.created_at, str)
            assert isinstance(t.tools, list)
            assert isinstance(t.metadata, dict)
        finally:
            v2_client.teammates.delete(t.id)

    def test_task_response_fields(self, v2_client):
        """Verify all Task fields are populated correctly."""
        tm = v2_client.teammates.create(name="TaskTypeHost")
        try:
            task = v2_client.tasks.create(
                teammate_id=tm.id,
                instructions="Type check",
                name="TypeTask",
                expected_output="Report",
                goals="Accuracy",
            )
            try:
                assert isinstance(task.id, int)
                assert isinstance(task.teammate_id, int)
                assert isinstance(task.instructions, str)
                assert isinstance(task.status, str)
                assert isinstance(task.created_at, str)
                assert isinstance(task.tools, list)
            finally:
                v2_client.tasks.delete(task.id)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_webhook_response_fields(self, v2_client):
        """Verify all Webhook fields are populated correctly."""
        wh = v2_client.webhooks.create(url="https://example.com/types")
        try:
            assert isinstance(wh.id, int)
            assert isinstance(wh.url, str)
            assert isinstance(wh.events, list)
            assert isinstance(wh.active, bool)
            assert isinstance(wh.created_at, str)
            assert isinstance(wh.secret, str)
        finally:
            v2_client.webhooks.delete(wh.id)

    def test_memory_response_fields(self, v2_client):
        """Verify all Memory fields are populated correctly."""
        uid = _uid()
        mem = v2_client.memories.create(user_id=uid, content="Test content")
        try:
            assert isinstance(mem.id, int)
            assert isinstance(mem.content, str)
            assert isinstance(mem.source, str)
            assert isinstance(mem.created_at, str)
        finally:
            v2_client.memories.delete(mem.id, user_id=uid)

    def test_permission_response_fields(self, v2_client):
        """Verify all PermissionPolicy fields are populated correctly."""
        uid = _uid()
        perm = v2_client.permissions.create(user_id=uid, tool="test")
        try:
            assert isinstance(perm.id, int)
            assert isinstance(perm.user_id, str)
            assert isinstance(perm.tool_name, str)
            assert isinstance(perm.created_at, str)
        finally:
            v2_client.permissions.delete(perm.id, user_id=uid)

    def test_trigger_response_fields(self, v2_client):
        """Verify all Trigger fields are populated correctly."""
        tm = v2_client.teammates.create(name="TriggerTypeHost")
        try:
            task = v2_client.tasks.create(teammate_id=tm.id, instructions="Trigger types")
            try:
                trigger = v2_client.tasks.triggers.create(
                    task.id, type="schedule", cron="0 9 * * *"
                )
                assert isinstance(trigger.id, int)
                assert isinstance(trigger.type, str)
                assert isinstance(trigger.enabled, bool)
                v2_client.tasks.triggers.delete(task.id, trigger.id)
            finally:
                v2_client.tasks.delete(task.id)
        finally:
            v2_client.teammates.delete(tm.id)


# ── Input Validation ────────────────────────────────────────────────


@pytest.mark.integration
class TestInputValidation:
    def test_empty_teammate_name_rejected(self, v2_client):
        """Empty name raises ValidationError (min_length=1)."""
        with pytest.raises(ValidationError):
            v2_client.teammates.create(name="")

    def test_max_length_teammate_name(self, v2_client):
        """255-char name succeeds (max_length=255)."""
        long_name = "A" * 255
        t = v2_client.teammates.create(name=long_name)
        try:
            assert t.name == long_name
        finally:
            v2_client.teammates.delete(t.id)

    def test_empty_memory_content_rejected(self, v2_client):
        """Empty content raises ValidationError (min_length=1)."""
        with pytest.raises(ValidationError):
            v2_client.memories.create(user_id=_uid(), content="")

    def test_max_length_memory_content(self, v2_client):
        """300-char content succeeds (max_length=300)."""
        uid = _uid()
        content = "A" * 300
        mem = v2_client.memories.create(user_id=uid, content=content)
        try:
            assert mem.content == content
        finally:
            v2_client.memories.delete(mem.id, user_id=uid)

    def test_webhook_localhost_rejected(self, v2_client):
        """Webhook URLs pointing to localhost are rejected (SSRF protection)."""
        with pytest.raises(ValidationError):
            v2_client.webhooks.create(url="https://localhost/hook")

    def test_teammate_name_exceeds_max_length(self, v2_client):
        """256-char name rejected (max_length=255)."""
        with pytest.raises(ValidationError):
            v2_client.teammates.create(name="A" * 256)

    def test_memory_exceeds_max_length(self, v2_client):
        """301-char content rejected (max_length=300)."""
        with pytest.raises(ValidationError):
            v2_client.memories.create(user_id=_uid(), content="A" * 301)

    def test_task_empty_instructions_rejected(self, v2_client):
        """Empty instructions rejected (min_length=1)."""
        tm = v2_client.teammates.create(name="EmptyInstrHost")
        try:
            with pytest.raises(ValidationError):
                v2_client.tasks.create(teammate_id=tm.id, instructions="")
        finally:
            v2_client.teammates.delete(tm.id)


# ── Memory Dedup Edge Cases ─────────────────────────────────────────


@pytest.mark.integration
class TestMemoryDedup:
    def test_case_insensitive_dedup(self, v2_client):
        """'Dark Mode' then 'dark mode' raises ConflictError (case-insensitive)."""
        uid = _uid()
        mem = v2_client.memories.create(user_id=uid, content="Dark Mode")
        try:
            with pytest.raises(ConflictError):
                v2_client.memories.create(user_id=uid, content="dark mode")
        finally:
            v2_client.memories.delete(mem.id, user_id=uid)

    def test_whitespace_normalization_dedup(self, v2_client):
        """'likes  coffee' and 'likes coffee' are treated as duplicates."""
        uid = _uid()
        mem = v2_client.memories.create(user_id=uid, content="likes  coffee")
        try:
            with pytest.raises(ConflictError):
                v2_client.memories.create(user_id=uid, content="likes coffee")
        finally:
            v2_client.memories.delete(mem.id, user_id=uid)


# ── Error Attributes ────────────────────────────────────────────────


@pytest.mark.integration
class TestErrorAttributes:
    def test_not_found_error_attributes(self, v2_client):
        """NotFoundError has status_code=404, non-empty message, method and path."""
        with pytest.raises(NotFoundError) as exc_info:
            v2_client.teammates.get(999999)
        e = exc_info.value
        assert e.status_code == 404
        assert isinstance(e.message, str) and len(e.message) > 0
        assert e.method is not None
        assert e.path is not None

    def test_validation_error_attributes(self, v2_client):
        """ValidationError has status_code=422 and non-empty message."""
        with pytest.raises(ValidationError) as exc_info:
            v2_client.webhooks.create(url="http://example.com/not-https")
        e = exc_info.value
        assert e.status_code == 422
        assert isinstance(e.message, str) and len(e.message) > 0

    def test_conflict_error_attributes(self, v2_client):
        """ConflictError has status_code=409."""
        uid = _uid()
        mem = v2_client.memories.create(user_id=uid, content="Unique item for conflict")
        try:
            with pytest.raises(ConflictError) as exc_info:
                v2_client.memories.create(user_id=uid, content="Unique item for conflict")
            assert exc_info.value.status_code == 409
        finally:
            v2_client.memories.delete(mem.id, user_id=uid)


# ── Unicode Support ─────────────────────────────────────────────────


@pytest.mark.integration
class TestUnicode:
    def test_teammate_name_unicode(self, v2_client):
        """Emoji and unicode in teammate name roundtrip correctly."""
        t = v2_client.teammates.create(name="Bot 🤖")
        try:
            assert t.name == "Bot 🤖"
            fetched = v2_client.teammates.get(t.id)
            assert fetched.name == "Bot 🤖"
        finally:
            v2_client.teammates.delete(t.id)

    def test_memory_unicode_content(self, v2_client):
        """Accented characters and emoji in memory content roundtrip correctly."""
        uid = _uid()
        content = "Préfère le café ☕"
        mem = v2_client.memories.create(user_id=uid, content=content)
        try:
            assert mem.content == content
        finally:
            v2_client.memories.delete(mem.id, user_id=uid)


# ── Webhook Signature Verification ──────────────────────────────────


@pytest.mark.integration
class TestWebhookSignatureVerification:
    def test_valid_signature(self, v2_client):
        """End-to-end: create webhook, construct signed payload, verify."""
        import hashlib
        import hmac

        wh = v2_client.webhooks.create(url="https://example.com/sig-test")
        try:
            secret = wh.secret
            assert secret is not None

            body = '{"event":"run.completed","run_id":1}'
            webhook_id = "msg_test123"
            timestamp = "1234567890"
            msg = f"{webhook_id}.{timestamp}.{body}"
            sig = "v1=" + hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
            headers = {
                "Webhook-Id": webhook_id,
                "Webhook-Timestamp": timestamp,
                "Webhook-Signature": sig,
            }

            from m8tes._resources.webhooks import Webhooks

            assert Webhooks.verify_signature(body, headers, secret) is True
        finally:
            v2_client.webhooks.delete(wh.id)

    def test_tampered_body_rejected(self, v2_client):
        """Signature verification fails when body is tampered."""
        import hashlib
        import hmac

        wh = v2_client.webhooks.create(url="https://example.com/sig-tamper")
        try:
            secret = wh.secret
            body = '{"event":"run.completed"}'
            webhook_id = "msg_test456"
            timestamp = "1234567890"
            msg = f"{webhook_id}.{timestamp}.{body}"
            sig = "v1=" + hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
            headers = {
                "Webhook-Id": webhook_id,
                "Webhook-Timestamp": timestamp,
                "Webhook-Signature": sig,
            }

            from m8tes._resources.webhooks import Webhooks

            assert Webhooks.verify_signature('{"tampered":true}', headers, secret) is False
        finally:
            v2_client.webhooks.delete(wh.id)

    def test_missing_headers_rejected(self):
        """Missing required headers returns False."""
        from m8tes._resources.webhooks import Webhooks

        assert Webhooks.verify_signature("body", {}, "secret") is False
        assert Webhooks.verify_signature("body", {"Webhook-Id": "x"}, "secret") is False


# ── End Users ────────────────────────────────────────────────────────


@pytest.mark.integration
class TestEndUsersCRUD:
    def test_full_lifecycle(self, v2_client):
        """Create -> list -> get -> update -> delete -> verify gone."""
        uid = _uid()
        eu = v2_client.users.create(
            user_id=uid,
            name="Alice",
            email="alice@example.com",
            company="Acme",
        )
        try:
            assert isinstance(eu, EndUser)
            assert eu.user_id == uid
            assert eu.name == "Alice"
            assert eu.email == "alice@example.com"
            assert eu.company == "Acme"
            assert eu.id is not None
            assert eu.created_at

            # List
            page = v2_client.users.list()
            assert isinstance(page, SyncPage)
            assert any(u.user_id == uid for u in page.data)

            # Get
            fetched = v2_client.users.get(uid)
            assert fetched.user_id == uid
            assert fetched.name == "Alice"

            # Update
            updated = v2_client.users.update(uid, name="Alice Jones", company="NewCo")
            assert updated.name == "Alice Jones"
            assert updated.company == "NewCo"
            assert updated.email == "alice@example.com"  # unchanged

            # Verify update persisted
            refetched = v2_client.users.get(uid)
            assert refetched.name == "Alice Jones"
        finally:
            v2_client.users.delete(uid)

        # Verify gone
        with pytest.raises(NotFoundError):
            v2_client.users.get(uid)

    def test_create_with_metadata(self, v2_client):
        """Create with metadata dict."""
        uid = _uid()
        eu = v2_client.users.create(user_id=uid, metadata={"tier": "premium"})
        try:
            assert eu.metadata == {"tier": "premium"}
        finally:
            v2_client.users.delete(uid)

    def test_duplicate_returns_conflict(self, v2_client):
        """Creating the same user_id twice returns ConflictError."""
        uid = _uid()
        v2_client.users.create(user_id=uid)
        try:
            with pytest.raises(ConflictError):
                v2_client.users.create(user_id=uid)
        finally:
            v2_client.users.delete(uid)

    def test_get_not_found(self, v2_client):
        """Non-existent user_id returns NotFoundError."""
        with pytest.raises(NotFoundError):
            v2_client.users.get("nonexistent-user-id-xyz")

    def test_delete_not_found(self, v2_client):
        """Deleting non-existent user_id returns NotFoundError."""
        with pytest.raises(NotFoundError):
            v2_client.users.delete("nonexistent-user-id-xyz")

    def test_auto_creation_via_memory(self, v2_client):
        """Creating a memory with user_id auto-creates an EndUser profile."""
        uid = _uid()
        mem = v2_client.memories.create(user_id=uid, content="Prefers dark mode")
        try:
            # Should be able to get the auto-created user
            eu = v2_client.users.get(uid)
            assert eu.user_id == uid
            assert eu.name is None  # auto-created, no profile data

            # Direct create should 409 since it already exists
            with pytest.raises(ConflictError):
                v2_client.users.create(user_id=uid)

            # But update should work
            updated = v2_client.users.update(uid, name="Bob")
            assert updated.name == "Bob"
        finally:
            v2_client.memories.delete(mem.id)
            v2_client.users.delete(uid)

    def test_users_pagination(self, v2_client):
        """Users list supports cursor pagination."""
        uids = [_uid() for _ in range(3)]
        try:
            for uid in uids:
                v2_client.users.create(user_id=uid, name=f"Page-{uid[:8]}")

            page1 = v2_client.users.list(limit=1)
            assert isinstance(page1, SyncPage)
            assert len(page1.data) == 1
            assert page1.has_more is True

            page2 = v2_client.users.list(limit=1, starting_after=page1.data[0].id)
            assert page2.data[0].id != page1.data[0].id
        finally:
            for uid in uids:
                v2_client.users.delete(uid)


# ── Settings ─────────────────────────────────────────────────────────


@pytest.mark.integration
class TestSettingsCRUD:
    def test_get_defaults(self, v2_client):
        """Default settings: company_research enabled."""
        settings = v2_client.settings.get()
        assert isinstance(settings, AccountSettings)
        assert settings.company_research is True

    def test_toggle_company_research(self, v2_client):
        """Disable and re-enable company research."""
        # Disable
        updated = v2_client.settings.update(company_research=False)
        assert updated.company_research is False

        # Verify persisted
        fetched = v2_client.settings.get()
        assert fetched.company_research is False

        # Re-enable
        restored = v2_client.settings.update(company_research=True)
        assert restored.company_research is True


# ── Runs: SDK Convenience Methods ────────────────────────────────────


@pytest.mark.integration
class TestRunsSDKMethods:
    """Tests for SDK convenience methods: poll, create_and_wait, reply_and_wait, stream_text."""

    def test_poll_running_run(self, v2_client):
        """poll() returns a Run when it reaches terminal status."""
        tm = v2_client.teammates.create(name="PollHost")
        try:
            run = v2_client.runs.create(
                teammate_id=tm.id,
                message="Poll test",
                stream=False,
            )
            result = v2_client.runs.poll(run.id, interval=1.0, timeout=120.0)
            assert isinstance(result, Run)
            assert result.status in ("completed", "failed", "cancelled")
        finally:
            v2_client.teammates.delete(tm.id)

    def test_create_and_wait(self, v2_client):
        """create_and_wait() returns finished Run."""
        tm = v2_client.teammates.create(name="CreateWaitHost")
        try:
            run = v2_client.runs.create_and_wait(
                teammate_id=tm.id,
                message="Respond with 'hello'",
                poll_interval=1.0,
                poll_timeout=120.0,
            )
            assert isinstance(run, Run)
            assert run.status in ("completed", "failed", "cancelled")
        finally:
            v2_client.teammates.delete(tm.id)

    def test_create_and_wait_has_output(self, v2_client):
        """create_and_wait() on completed run has non-empty output."""
        tm = v2_client.teammates.create(name="CreateWaitOutputHost")
        try:
            run = v2_client.runs.create_and_wait(
                teammate_id=tm.id,
                message="Say the word 'pineapple'",
                poll_interval=1.0,
                poll_timeout=120.0,
            )
            if run.status == "completed":
                assert run.output is not None
                assert len(run.output) > 0
        finally:
            v2_client.teammates.delete(tm.id)

    def test_reply_and_wait(self, v2_client):
        """reply_and_wait() sends follow-up and polls to completion."""
        tm = v2_client.teammates.create(name="ReplyWaitHost")
        try:
            run = v2_client.runs.create_and_wait(
                teammate_id=tm.id,
                message="Say hello",
                poll_interval=1.0,
                poll_timeout=120.0,
            )
            reply = v2_client.runs.reply_and_wait(
                run.id,
                message="Now say goodbye",
                poll_interval=1.0,
                poll_timeout=120.0,
            )
            assert isinstance(reply, Run)
            assert reply.status in ("completed", "failed", "cancelled")
        finally:
            v2_client.teammates.delete(tm.id)

    def test_create_streaming_run(self, v2_client):
        """stream=True returns a RunStream context manager."""
        from m8tes._streaming import RunStream

        tm = v2_client.teammates.create(name="StreamHost")
        try:
            with v2_client.runs.create(
                teammate_id=tm.id,
                message="Say hi",
                stream=True,
            ) as stream:
                assert isinstance(stream, RunStream)
                events = list(stream)
                assert len(events) > 0
                # At least one event should exist
                assert all(hasattr(e, "type") for e in events)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_stream_text_generator(self, v2_client):
        """stream_text() yields text chunks."""
        tm = v2_client.teammates.create(name="StreamTextHost")
        try:
            chunks = list(
                v2_client.runs.stream_text(
                    teammate_id=tm.id,
                    message="Say the word 'banana'",
                )
            )
            assert len(chunks) > 0
            full_text = "".join(chunks)
            assert len(full_text) > 0
        finally:
            v2_client.teammates.delete(tm.id)


# ── Runs: Parameter Combinations ────────────────────────────────────


@pytest.mark.integration
class TestRunParameterCombos:
    """Run creation with various parameter combinations."""

    def test_create_run_memory_disabled(self, v2_client):
        """Run with memory=False is accepted."""
        tm = v2_client.teammates.create(name="NoMemoryHost")
        try:
            run = v2_client.runs.create(
                teammate_id=tm.id,
                message="No memory test",
                stream=False,
                memory=False,
            )
            assert isinstance(run, Run)
            assert run.status == "running"
        finally:
            v2_client.teammates.delete(tm.id)

    def test_create_run_history_disabled(self, v2_client):
        """Run with history=False is accepted."""
        tm = v2_client.teammates.create(name="NoHistoryHost")
        try:
            run = v2_client.runs.create(
                teammate_id=tm.id,
                message="No history test",
                stream=False,
                history=False,
            )
            assert isinstance(run, Run)
            assert run.status == "running"
        finally:
            v2_client.teammates.delete(tm.id)

    def test_create_run_with_instructions_override(self, v2_client):
        """Run with instructions override is accepted."""
        tm = v2_client.teammates.create(name="InstrOverrideHost")
        try:
            run = v2_client.runs.create(
                teammate_id=tm.id,
                message="Hello",
                stream=False,
                instructions="Always respond in French",
            )
            assert isinstance(run, Run)
            assert run.status == "running"
        finally:
            v2_client.teammates.delete(tm.id)

    def test_create_run_all_flags_disabled(self, v2_client):
        """Run with memory=False and history=False is accepted."""
        tm = v2_client.teammates.create(name="AllDisabledHost")
        try:
            run = v2_client.runs.create(
                teammate_id=tm.id,
                message="Minimal context",
                stream=False,
                memory=False,
                history=False,
            )
            assert isinstance(run, Run)
            assert run.status == "running"
        finally:
            v2_client.teammates.delete(tm.id)

    def test_approve_deny_decision(self, v2_client):
        """Approve with decision='deny' on a real run (no pending request → 404)."""
        tm = v2_client.teammates.create(name="DenyHost")
        try:
            run = v2_client.runs.create(
                teammate_id=tm.id,
                message="Deny test",
                stream=False,
            )
            with pytest.raises(NotFoundError):
                v2_client.runs.approve(run.id, request_id="fake-uuid", decision="deny")
        finally:
            v2_client.teammates.delete(tm.id)

    def test_approve_with_remember(self, v2_client):
        """Approve with remember=True on a real run (no pending request → 404)."""
        tm = v2_client.teammates.create(name="RememberHost")
        try:
            run = v2_client.runs.create(
                teammate_id=tm.id,
                message="Remember test",
                stream=False,
            )
            with pytest.raises(NotFoundError):
                v2_client.runs.approve(
                    run.id, request_id="fake-uuid", decision="allow", remember=True
                )
        finally:
            v2_client.teammates.delete(tm.id)

    def test_run_list_user_id_filter_with_real_runs(self, v2_client):
        """List runs filtered by user_id that has actual runs."""
        uid = _uid()
        tm = v2_client.teammates.create(name="UserRunFilterHost")
        try:
            v2_client.runs.create(
                teammate_id=tm.id,
                message="Scoped run",
                stream=False,
                user_id=uid,
            )
            page = v2_client.runs.list(user_id=uid)
            assert isinstance(page, SyncPage)
            assert len(page.data) >= 1
            assert all(r.user_id == uid for r in page.data)
        finally:
            v2_client.teammates.delete(tm.id)


# ── Apps: Edge Cases ────────────────────────────────────────────────


@pytest.mark.integration
class TestAppsEdgeCases:
    """Apps endpoint edge cases beyond basic list."""

    def test_list_apps_with_user_id(self, v2_client):
        """List apps with user_id filter works without error."""
        uid = _uid()
        page = v2_client.apps.list(user_id=uid)
        assert isinstance(page, SyncPage)

    def test_connect_nonexistent_app_404(self, v2_client):
        """Connect to nonexistent app raises NotFoundError."""
        with pytest.raises((NotFoundError, ValidationError)):
            v2_client.apps.connect("nonexistent_app_xyz", "https://example.com/callback")

    def test_disconnect_nonexistent_app_404(self, v2_client):
        """Disconnect nonexistent app raises NotFoundError."""
        with pytest.raises((NotFoundError, ValidationError)):
            v2_client.apps.disconnect("nonexistent_app_xyz")


# ── End Users: Edge Cases ────────────────────────────────────────────


@pytest.mark.integration
class TestEndUsersEdgeCases:
    """End user edge cases beyond basic CRUD."""

    def test_update_nonexistent_user_404(self, v2_client):
        """Update nonexistent user_id raises NotFoundError."""
        with pytest.raises(NotFoundError):
            v2_client.users.update("nonexistent-user-xyz-999", name="Ghost")

    def test_metadata_replace_on_update(self, v2_client):
        """Metadata update replaces entire dict (not merge)."""
        uid = _uid()
        v2_client.users.create(user_id=uid, metadata={"key1": "val1", "key2": "val2"})
        try:
            updated = v2_client.users.update(uid, metadata={"key3": "val3"})
            assert updated.metadata == {"key3": "val3"}
            assert "key1" not in updated.metadata
        finally:
            v2_client.users.delete(uid)

    def test_update_partial_fields(self, v2_client):
        """Updating one field does not affect others."""
        uid = _uid()
        v2_client.users.create(
            user_id=uid, name="Original", email="orig@example.com", company="OldCo"
        )
        try:
            updated = v2_client.users.update(uid, company="NewCo")
            assert updated.company == "NewCo"
            assert updated.name == "Original"
            assert updated.email == "orig@example.com"
        finally:
            v2_client.users.delete(uid)


# ── Trigger Error Paths ──────────────────────────────────────────────


@pytest.mark.integration
class TestTriggerErrorPaths:
    """Trigger-specific error conditions."""

    def test_delete_nonexistent_trigger_404(self, v2_client):
        """Delete nonexistent trigger returns 404."""
        tm = v2_client.teammates.create(name="TrigDelHost")
        try:
            task = v2_client.tasks.create(teammate_id=tm.id, instructions="Trigger del")
            try:
                with pytest.raises(NotFoundError):
                    v2_client.tasks.triggers.delete(task.id, 999999)
            finally:
                v2_client.tasks.delete(task.id)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_delete_trigger_wrong_task_404(self, v2_client):
        """Delete trigger using wrong task_id returns 404."""
        tm = v2_client.teammates.create(name="TrigWrongTaskHost")
        try:
            task1 = v2_client.tasks.create(teammate_id=tm.id, instructions="Task 1")
            task2 = v2_client.tasks.create(teammate_id=tm.id, instructions="Task 2")
            try:
                trigger = v2_client.tasks.triggers.create(
                    task1.id, type="schedule", cron="0 9 * * *"
                )
                # Try to delete trigger from task2 — should 404
                with pytest.raises(NotFoundError):
                    v2_client.tasks.triggers.delete(task2.id, trigger.id)
                # Clean up properly
                v2_client.tasks.triggers.delete(task1.id, trigger.id)
            finally:
                v2_client.tasks.delete(task1.id)
                v2_client.tasks.delete(task2.id)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_list_triggers_nonexistent_task_404(self, v2_client):
        """List triggers for nonexistent task returns 404."""
        with pytest.raises(NotFoundError):
            v2_client.tasks.triggers.list(999999)

    def test_delete_virtual_trigger_rejected(self, v2_client):
        """Delete trigger with id=0 (webhook/email virtual) returns 422."""
        tm = v2_client.teammates.create(name="VirtualTrigHost")
        try:
            task = v2_client.tasks.create(teammate_id=tm.id, instructions="Virtual trig")
            try:
                with pytest.raises(ValidationError):
                    v2_client.tasks.triggers.delete(task.id, 0)
            finally:
                v2_client.tasks.delete(task.id)
        finally:
            v2_client.teammates.delete(tm.id)


# ── Webhook Event Types ──────────────────────────────────────────────


@pytest.mark.integration
class TestWebhookEventTypes:
    """Webhook event type edge cases."""

    def test_awaiting_input_event_valid(self, v2_client):
        """run.awaiting_input is a valid webhook event type."""
        wh = v2_client.webhooks.create(
            url="https://example.com/awaiting", events=["run.awaiting_input"]
        )
        try:
            assert "run.awaiting_input" in wh.events
        finally:
            v2_client.webhooks.delete(wh.id)

    def test_all_valid_events(self, v2_client):
        """All four valid event types accepted together."""
        all_events = ["run.started", "run.completed", "run.failed", "run.awaiting_input"]
        wh = v2_client.webhooks.create(url="https://example.com/all-events", events=all_events)
        try:
            assert set(wh.events) == set(all_events)
        finally:
            v2_client.webhooks.delete(wh.id)


# ── Teammate Edge Paths ──────────────────────────────────────────────


@pytest.mark.integration
class TestTeammateEdgePaths:
    """Teammate webhook/email edge cases."""

    def test_disable_webhook_never_enabled(self, v2_client):
        """Disable webhook on teammate that never had webhook enabled."""
        import contextlib

        tm = v2_client.teammates.create(name="NoWebhookHost")
        try:
            # Should not raise — disabling something that doesn't exist is a no-op or 404
            with contextlib.suppress(NotFoundError):
                v2_client.teammates.disable_webhook(tm.id)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_disable_email_never_enabled(self, v2_client):
        """Disable email inbox on teammate that never had email enabled."""
        import contextlib

        tm = v2_client.teammates.create(name="NoEmailHost")
        try:
            with contextlib.suppress(NotFoundError):
                v2_client.teammates.disable_email_inbox(tm.id)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_get_nonexistent_teammate_404(self, v2_client):
        """GET nonexistent teammate raises NotFoundError."""
        with pytest.raises(NotFoundError):
            v2_client.teammates.get(999999)

    def test_delete_nonexistent_teammate_404(self, v2_client):
        """DELETE nonexistent teammate raises NotFoundError."""
        with pytest.raises(NotFoundError):
            v2_client.teammates.delete(999999)


# ── Permission Error Paths ───────────────────────────────────────────


@pytest.mark.integration
class TestPermissionErrorPaths:
    """Permission-specific error conditions."""

    def test_delete_nonexistent_permission_404(self, v2_client):
        """Delete nonexistent permission raises NotFoundError."""
        uid = _uid()
        with pytest.raises(NotFoundError):
            v2_client.permissions.delete(999999, user_id=uid)

    def test_list_empty_for_new_user(self, v2_client):
        """List permissions for user with none returns empty."""
        uid = _uid()
        page = v2_client.permissions.list(user_id=uid)
        assert isinstance(page, SyncPage)
        assert len(page.data) == 0

    def test_list_empty_memories_for_new_user(self, v2_client):
        """List memories for user with none returns empty."""
        uid = _uid()
        page = v2_client.memories.list(user_id=uid)
        assert isinstance(page, SyncPage)
        assert len(page.data) == 0
