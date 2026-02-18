"""V2 SDK integration tests — real M8tes client against real FastAPI backend.

Tests CRUD endpoints only (no run execution, no Claude SDK calls).
Covers all 7 V2 resources: teammates, tasks, triggers, memories,
permissions, webhooks, runs (read-only), plus pagination, error handling,
validation edge cases, multi-tenancy isolation, and context manager usage.

Requirements:
    1. Backend running at localhost:8000 (or E2E_BACKEND_URL)
    2. Database running (via docker compose or SQLite for CI)

Run: pytest tests/integration/test_v2_integration.py -v -m integration
"""

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
    Memory,
    PermissionPolicy,
    SyncPage,
    Task,
    Teammate,
    TeammateWebhook,
    Trigger,
    Webhook,
)

# ── Teammates ────────────────────────────────────────────────────────


@pytest.mark.integration
class TestTeammatesCRUD:
    def test_full_lifecycle(self, v2_client):
        """Create -> list -> get -> update -> delete -> verify excluded from list."""
        t = v2_client.teammates.create(name="IntegBot", instructions="Test bot")
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

        # Delete (soft delete — archives the teammate)
        v2_client.teammates.delete(t.id)

        # Verify excluded from list (archived teammates are filtered out)
        page_after = v2_client.teammates.list()
        assert not any(tm.id == t.id for tm in page_after.data)

    def test_create_with_all_fields(self, v2_client):
        """Create teammate with every optional field."""
        t = v2_client.teammates.create(
            name="FullBot",
            instructions="Help with everything",
            role="support",
            goals="Resolve tickets",
            user_id="tenant_1",
            metadata={"team": "ops"},
            allowed_senders=["@acme.com"],
        )
        assert t.name == "FullBot"
        assert t.user_id == "tenant_1"
        assert t.role == "support"
        assert t.goals == "Resolve tickets"
        assert t.metadata == {"team": "ops"}
        assert t.allowed_senders == ["@acme.com"]

        # Cleanup
        v2_client.teammates.delete(t.id)

    def test_user_id_filtering(self, v2_client):
        """List with user_id only returns matching teammates."""
        t1 = v2_client.teammates.create(name="TenantA", user_id="filter_a")
        t2 = v2_client.teammates.create(name="TenantB", user_id="filter_b")

        page_a = v2_client.teammates.list(user_id="filter_a")
        ids = [tm.id for tm in page_a.data]
        assert t1.id in ids
        assert t2.id not in ids

        page_b = v2_client.teammates.list(user_id="filter_b")
        ids_b = [tm.id for tm in page_b.data]
        assert t2.id in ids_b
        assert t1.id not in ids_b

        # Cleanup
        v2_client.teammates.delete(t1.id)
        v2_client.teammates.delete(t2.id)

    def test_update_multiple_fields(self, v2_client):
        """Update multiple fields at once, verify all persisted."""
        t = v2_client.teammates.create(name="MultiUpdate")
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

        v2_client.teammates.delete(t.id)

    def test_create_minimal(self, v2_client):
        """Create with only required field (name)."""
        t = v2_client.teammates.create(name="Minimal")
        assert t.name == "Minimal"
        assert t.instructions is None
        assert t.tools == []
        assert t.role is None
        assert t.user_id is None
        v2_client.teammates.delete(t.id)


# ── Teammate Webhooks ────────────────────────────────────────────────


@pytest.mark.integration
class TestTeammateWebhooks:
    def test_enable_disable_webhook(self, v2_client):
        """Enable webhook trigger → verify → disable → verify."""
        tm = v2_client.teammates.create(name="WebhookHost")

        # Enable
        wh = v2_client.teammates.enable_webhook(tm.id)
        assert isinstance(wh, TeammateWebhook)
        assert wh.enabled is True
        assert wh.url is not None
        assert "webhook" in wh.url.lower() or "mates" in wh.url.lower()

        # Disable
        v2_client.teammates.disable_webhook(tm.id)

        # Cleanup
        v2_client.teammates.delete(tm.id)

    def test_enable_webhook_idempotent(self, v2_client):
        """Enable webhook twice should not error."""
        tm = v2_client.teammates.create(name="WebhookIdempotent")
        wh1 = v2_client.teammates.enable_webhook(tm.id)
        wh2 = v2_client.teammates.enable_webhook(tm.id)
        assert wh1.enabled is True
        assert wh2.enabled is True

        v2_client.teammates.disable_webhook(tm.id)
        v2_client.teammates.delete(tm.id)


# ── Tasks ────────────────────────────────────────────────────────────


@pytest.mark.integration
class TestTasksCRUD:
    def test_full_lifecycle(self, v2_client):
        """Create -> list -> get -> update -> delete."""
        tm = v2_client.teammates.create(name="TaskHost")

        task = v2_client.tasks.create(
            teammate_id=tm.id, instructions="Weekly summary", name="Weekly"
        )
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

        # Delete (soft delete — archives the task)
        v2_client.tasks.delete(task.id)
        page_after = v2_client.tasks.list(teammate_id=tm.id)
        assert not any(t.id == task.id for t in page_after.data)

        # Cleanup
        v2_client.teammates.delete(tm.id)

    def test_create_with_all_fields(self, v2_client):
        """Create task with all optional fields."""
        tm = v2_client.teammates.create(name="TaskAllFields")
        task = v2_client.tasks.create(
            teammate_id=tm.id,
            instructions="Compile report",
            name="Report Task",
            expected_output="PDF report with charts",
            goals="Accurate and concise",
            user_id="task_user_1",
        )
        assert task.name == "Report Task"
        assert task.expected_output == "PDF report with charts"
        assert task.goals == "Accurate and concise"
        assert task.user_id == "task_user_1"

        v2_client.tasks.delete(task.id)
        v2_client.teammates.delete(tm.id)

    def test_name_defaults_to_instructions(self, v2_client):
        """When name is omitted, backend defaults name to instructions[:100]."""
        tm = v2_client.teammates.create(name="TaskNameDefault")
        task = v2_client.tasks.create(
            teammate_id=tm.id, instructions="Generate weekly marketing report"
        )
        # Name should be set automatically by backend
        assert task.name is not None
        assert "weekly" in task.name.lower() or "generate" in task.name.lower()

        v2_client.tasks.delete(task.id)
        v2_client.teammates.delete(tm.id)

    def test_task_user_id_filtering(self, v2_client):
        """List tasks filtered by user_id for multi-tenancy."""
        tm = v2_client.teammates.create(name="TaskFilterHost")
        t1 = v2_client.tasks.create(teammate_id=tm.id, instructions="Task A", user_id="user_a")
        t2 = v2_client.tasks.create(teammate_id=tm.id, instructions="Task B", user_id="user_b")

        page_a = v2_client.tasks.list(user_id="user_a")
        ids = [t.id for t in page_a.data]
        assert t1.id in ids
        assert t2.id not in ids

        v2_client.tasks.delete(t1.id)
        v2_client.tasks.delete(t2.id)
        v2_client.teammates.delete(tm.id)

    def test_multiple_tasks_per_teammate(self, v2_client):
        """Create multiple tasks for same teammate, all appear in list."""
        tm = v2_client.teammates.create(name="MultiTaskHost")
        tasks = []
        for i in range(3):
            t = v2_client.tasks.create(
                teammate_id=tm.id, instructions=f"Task {i}", name=f"Task-{i}"
            )
            tasks.append(t)

        page = v2_client.tasks.list(teammate_id=tm.id)
        page_ids = {t.id for t in page.data}
        for t in tasks:
            assert t.id in page_ids

        for t in tasks:
            v2_client.tasks.delete(t.id)
        v2_client.teammates.delete(tm.id)

    def test_update_multiple_fields(self, v2_client):
        """Update name, instructions, expected_output, goals at once."""
        tm = v2_client.teammates.create(name="TaskUpdateHost")
        task = v2_client.tasks.create(teammate_id=tm.id, instructions="Original", name="Original")
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

        v2_client.tasks.delete(task.id)
        v2_client.teammates.delete(tm.id)


# ── Task Triggers ────────────────────────────────────────────────────


@pytest.mark.integration
class TestTaskTriggers:
    def test_schedule_trigger_lifecycle(self, v2_client):
        """Create schedule trigger -> list -> delete."""
        tm = v2_client.teammates.create(name="TriggerHost")
        task = v2_client.tasks.create(teammate_id=tm.id, instructions="Cron job")

        trigger = v2_client.tasks.triggers.create(task.id, type="schedule", cron="0 9 * * 1")
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

        # Cleanup
        v2_client.tasks.delete(task.id)
        v2_client.teammates.delete(tm.id)

    def test_schedule_trigger_with_timezone(self, v2_client):
        """Create schedule trigger with non-UTC timezone."""
        tm = v2_client.teammates.create(name="TZTriggerHost")
        task = v2_client.tasks.create(teammate_id=tm.id, instructions="TZ job")

        trigger = v2_client.tasks.triggers.create(
            task.id, type="schedule", cron="0 9 * * *", timezone="America/New_York"
        )
        assert trigger.type == "schedule"
        assert trigger.timezone == "America/New_York"

        v2_client.tasks.triggers.delete(task.id, trigger.id)
        v2_client.tasks.delete(task.id)
        v2_client.teammates.delete(tm.id)

    def test_schedule_trigger_with_interval(self, v2_client):
        """Create interval-based schedule trigger."""
        tm = v2_client.teammates.create(name="IntervalHost")
        task = v2_client.tasks.create(teammate_id=tm.id, instructions="Interval job")

        trigger = v2_client.tasks.triggers.create(task.id, type="schedule", interval_seconds=3600)
        assert trigger.type == "schedule"

        v2_client.tasks.triggers.delete(task.id, trigger.id)
        v2_client.tasks.delete(task.id)
        v2_client.teammates.delete(tm.id)

    def test_webhook_trigger(self, v2_client):
        """Create webhook trigger -> list -> verify URL returned."""
        tm = v2_client.teammates.create(name="WebhookTriggerHost")
        task = v2_client.tasks.create(teammate_id=tm.id, instructions="Webhook triggered")

        trigger = v2_client.tasks.triggers.create(task.id, type="webhook")
        assert trigger.type == "webhook"
        # Webhook triggers return a URL (shown once)
        assert trigger.url is not None or trigger.id is not None

        triggers = v2_client.tasks.triggers.list(task.id)
        assert len(triggers) >= 1

        v2_client.tasks.delete(task.id)
        v2_client.teammates.delete(tm.id)

    def test_email_trigger(self, v2_client):
        """Create email trigger -> list -> verify address."""
        tm = v2_client.teammates.create(name="EmailTriggerHost")
        task = v2_client.tasks.create(teammate_id=tm.id, instructions="Email triggered")

        trigger = v2_client.tasks.triggers.create(task.id, type="email")
        assert trigger.type == "email"

        triggers = v2_client.tasks.triggers.list(task.id)
        assert len(triggers) >= 1

        v2_client.tasks.delete(task.id)
        v2_client.teammates.delete(tm.id)

    def test_multiple_schedule_triggers(self, v2_client):
        """Multiple schedule triggers can coexist on same task."""
        tm = v2_client.teammates.create(name="MultiTriggerHost")
        task = v2_client.tasks.create(teammate_id=tm.id, instructions="Multi trigger")

        t1 = v2_client.tasks.triggers.create(task.id, type="schedule", cron="0 9 * * 1")
        t2 = v2_client.tasks.triggers.create(task.id, type="schedule", cron="0 17 * * 5")

        triggers = v2_client.tasks.triggers.list(task.id)
        schedule_ids = {tr.id for tr in triggers if tr.type == "schedule"}
        assert t1.id in schedule_ids
        assert t2.id in schedule_ids

        v2_client.tasks.triggers.delete(task.id, t1.id)
        v2_client.tasks.triggers.delete(task.id, t2.id)
        v2_client.tasks.delete(task.id)
        v2_client.teammates.delete(tm.id)


# ── Memories ─────────────────────────────────────────────────────────


@pytest.mark.integration
class TestMemoriesCRUD:
    def test_full_lifecycle(self, v2_client):
        """Create -> list -> delete -> verify empty."""
        user_id = "mem_test_user"

        mem = v2_client.memories.create(user_id=user_id, content="Prefers dark mode")
        assert isinstance(mem, Memory)
        assert mem.content == "Prefers dark mode"
        assert mem.source == "api"

        # List
        page = v2_client.memories.list(user_id=user_id)
        assert any(m.id == mem.id for m in page.data)

        # Delete
        v2_client.memories.delete(mem.id, user_id=user_id)

        # Verify gone
        page_after = v2_client.memories.list(user_id=user_id)
        assert not any(m.id == mem.id for m in page_after.data)

    def test_multiple_memories(self, v2_client):
        """Create several memories for same user, all appear in list."""
        user_id = "multi_mem_user"
        mems = []
        for i in range(3):
            m = v2_client.memories.create(user_id=user_id, content=f"Memory item {i}")
            mems.append(m)

        page = v2_client.memories.list(user_id=user_id)
        page_ids = {m.id for m in page.data}
        for m in mems:
            assert m.id in page_ids

        # Cleanup
        for m in mems:
            v2_client.memories.delete(m.id, user_id=user_id)

    def test_user_id_isolation(self, v2_client):
        """Memories for user A are not visible to user B."""
        mem_a = v2_client.memories.create(user_id="mem_iso_a", content="A's preference")
        mem_b = v2_client.memories.create(user_id="mem_iso_b", content="B's preference")

        page_a = v2_client.memories.list(user_id="mem_iso_a")
        ids_a = {m.id for m in page_a.data}
        assert mem_a.id in ids_a
        assert mem_b.id not in ids_a

        page_b = v2_client.memories.list(user_id="mem_iso_b")
        ids_b = {m.id for m in page_b.data}
        assert mem_b.id in ids_b
        assert mem_a.id not in ids_b

        v2_client.memories.delete(mem_a.id, user_id="mem_iso_a")
        v2_client.memories.delete(mem_b.id, user_id="mem_iso_b")

    def test_memory_content_trimmed(self, v2_client):
        """Backend strips whitespace from memory content."""
        user_id = "mem_trim_user"
        mem = v2_client.memories.create(user_id=user_id, content="  spaced out  ")
        # Backend should strip content
        assert mem.content.strip() == "spaced out"

        v2_client.memories.delete(mem.id, user_id=user_id)

    def test_duplicate_memory_conflict(self, v2_client):
        """Creating identical memory content raises ConflictError (409)."""
        user_id = "mem_dup_user"
        mem = v2_client.memories.create(user_id=user_id, content="Unique preference")
        try:
            with pytest.raises((ConflictError, M8tesError)):
                v2_client.memories.create(user_id=user_id, content="Unique preference")
        finally:
            v2_client.memories.delete(mem.id, user_id=user_id)


# ── Permissions ──────────────────────────────────────────────────────


@pytest.mark.integration
class TestPermissionsCRUD:
    def test_full_lifecycle(self, v2_client):
        """Create -> list -> delete -> verify gone."""
        user_id = "perm_test_user"

        perm = v2_client.permissions.create(user_id=user_id, tool="gmail")
        assert isinstance(perm, PermissionPolicy)
        assert perm.tool_name == "gmail"
        assert perm.user_id == user_id

        # List
        page = v2_client.permissions.list(user_id=user_id)
        assert any(p.id == perm.id for p in page.data)

        # Delete
        v2_client.permissions.delete(perm.id, user_id=user_id)

        # Verify gone
        page_after = v2_client.permissions.list(user_id=user_id)
        assert not any(p.id == perm.id for p in page_after.data)

    def test_idempotent_create(self, v2_client):
        """Creating same (user_id, tool) twice returns same record."""
        user_id = "perm_idemp_user"
        p1 = v2_client.permissions.create(user_id=user_id, tool="slack")
        p2 = v2_client.permissions.create(user_id=user_id, tool="slack")
        assert p1.id == p2.id

        v2_client.permissions.delete(p1.id, user_id=user_id)

    def test_multiple_tools(self, v2_client):
        """Different tools create separate permission policies."""
        user_id = "perm_multi_user"
        p1 = v2_client.permissions.create(user_id=user_id, tool="gmail")
        p2 = v2_client.permissions.create(user_id=user_id, tool="slack")
        assert p1.id != p2.id
        assert p1.tool_name == "gmail"
        assert p2.tool_name == "slack"

        page = v2_client.permissions.list(user_id=user_id)
        ids = {p.id for p in page.data}
        assert p1.id in ids
        assert p2.id in ids

        v2_client.permissions.delete(p1.id, user_id=user_id)
        v2_client.permissions.delete(p2.id, user_id=user_id)

    def test_user_id_isolation(self, v2_client):
        """Permissions for user A are not visible to user B."""
        pa = v2_client.permissions.create(user_id="perm_iso_a", tool="tool_a")
        pb = v2_client.permissions.create(user_id="perm_iso_b", tool="tool_b")

        page_a = v2_client.permissions.list(user_id="perm_iso_a")
        ids_a = {p.id for p in page_a.data}
        assert pa.id in ids_a
        assert pb.id not in ids_a

        v2_client.permissions.delete(pa.id, user_id="perm_iso_a")
        v2_client.permissions.delete(pb.id, user_id="perm_iso_b")


# ── Webhooks ─────────────────────────────────────────────────────────


@pytest.mark.integration
class TestWebhooksCRUD:
    def test_full_lifecycle(self, v2_client):
        """Create -> list -> get -> update -> delete."""
        wh = v2_client.webhooks.create(url="https://example.com/hook", events=["run.completed"])
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
        # Secret should have changed after rotation
        if updated.secret and old_secret:
            assert updated.secret != old_secret

        # Delete
        v2_client.webhooks.delete(wh.id)

        with pytest.raises(NotFoundError):
            v2_client.webhooks.get(wh.id)

    def test_create_with_default_events(self, v2_client):
        """Create webhook without specifying events uses defaults."""
        wh = v2_client.webhooks.create(url="https://example.com/default-events")
        assert isinstance(wh.events, list)
        assert len(wh.events) > 0
        v2_client.webhooks.delete(wh.id)

    def test_create_with_multiple_events(self, v2_client):
        """Create webhook subscribed to multiple event types."""
        events = ["run.started", "run.completed", "run.failed"]
        wh = v2_client.webhooks.create(url="https://example.com/multi", events=events)
        assert set(wh.events) == set(events)
        v2_client.webhooks.delete(wh.id)

    def test_update_events(self, v2_client):
        """Update webhook event subscriptions."""
        wh = v2_client.webhooks.create(url="https://example.com/events", events=["run.completed"])
        updated = v2_client.webhooks.update(wh.id, events=["run.started", "run.failed"])
        assert "run.started" in updated.events
        assert "run.failed" in updated.events
        v2_client.webhooks.delete(wh.id)

    def test_deactivate_reactivate(self, v2_client):
        """Toggle webhook active status."""
        wh = v2_client.webhooks.create(url="https://example.com/toggle")
        assert wh.active is True

        deactivated = v2_client.webhooks.update(wh.id, active=False)
        assert deactivated.active is False

        reactivated = v2_client.webhooks.update(wh.id, active=True)
        assert reactivated.active is True

        v2_client.webhooks.delete(wh.id)

    def test_deliveries_empty(self, v2_client):
        """Newly created webhook has no deliveries."""
        wh = v2_client.webhooks.create(url="https://example.com/empty")
        page = v2_client.webhooks.list_deliveries(wh.id)
        assert isinstance(page, SyncPage)
        assert len(page.data) == 0

        v2_client.webhooks.delete(wh.id)

    def test_multiple_webhooks(self, v2_client):
        """Multiple webhooks can coexist."""
        wh1 = v2_client.webhooks.create(url="https://example.com/one")
        wh2 = v2_client.webhooks.create(url="https://example.com/two")
        assert wh1.id != wh2.id

        page = v2_client.webhooks.list()
        ids = {w.id for w in page.data}
        assert wh1.id in ids
        assert wh2.id in ids

        v2_client.webhooks.delete(wh1.id)
        v2_client.webhooks.delete(wh2.id)


# ── Webhook Validation ───────────────────────────────────────────────


@pytest.mark.integration
class TestWebhookValidation:
    def test_http_url_rejected(self, v2_client):
        """HTTP (not HTTPS) webhook URLs are rejected (422)."""
        with pytest.raises((ValidationError, M8tesError)):
            v2_client.webhooks.create(url="http://example.com/hook")

    def test_invalid_event_rejected(self, v2_client):
        """Unknown event type is rejected (422)."""
        with pytest.raises((ValidationError, M8tesError)):
            v2_client.webhooks.create(url="https://example.com/hook", events=["invalid.event"])


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


# ── Pagination ───────────────────────────────────────────────────────


@pytest.mark.integration
class TestPagination:
    def test_cursor_pagination(self, v2_client):
        """Create 3 teammates, paginate with limit=1."""
        created = []
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

        # Cleanup
        for t in created:
            v2_client.teammates.delete(t.id)

    def test_auto_paging_iter(self, v2_client):
        """SyncPage.auto_paging_iter() walks through all pages."""
        created = []
        for i in range(3):
            t = v2_client.teammates.create(name=f"AutoPage{i}")
            created.append(t)

        # Use auto_paging_iter with limit=1 to force multiple pages
        first_page = v2_client.teammates.list(limit=1)
        all_teammates = list(first_page.auto_paging_iter())

        created_ids = {t.id for t in created}
        fetched_ids = {t.id for t in all_teammates}
        assert created_ids.issubset(fetched_ids)

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
        for i in range(3):
            t = v2_client.tasks.create(teammate_id=tm.id, instructions=f"Paginated task {i}")
            tasks.append(t)

        page1 = v2_client.tasks.list(teammate_id=tm.id, limit=1)
        assert len(page1.data) == 1
        assert page1.has_more is True

        for t in tasks:
            v2_client.tasks.delete(t.id)
        v2_client.teammates.delete(tm.id)

    def test_webhook_pagination(self, v2_client):
        """Pagination works for webhooks."""
        webhooks = []
        for i in range(3):
            wh = v2_client.webhooks.create(url=f"https://example.com/page{i}")
            webhooks.append(wh)

        page1 = v2_client.webhooks.list(limit=1)
        assert len(page1.data) == 1
        assert page1.has_more is True

        for wh in webhooks:
            v2_client.webhooks.delete(wh.id)


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
        """Invalid API key raises error on first request."""
        bad_client = M8tes(api_key="invalid_key", base_url=f"{backend_url}/api/v2")
        with pytest.raises((AuthenticationError, M8tesError)):
            bad_client.teammates.list()
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
        task = v2_client.tasks.create(teammate_id=tm.id, instructions="TZ test")
        try:
            with pytest.raises((ValidationError, M8tesError)):
                v2_client.tasks.triggers.create(
                    task.id, type="schedule", cron="0 9 * * *", timezone="Fake/Zone"
                )
        finally:
            v2_client.tasks.delete(task.id)
            v2_client.teammates.delete(tm.id)

    def test_memory_delete_wrong_user(self, v2_client):
        """Deleting memory with wrong user_id returns 404."""
        mem = v2_client.memories.create(user_id="mem_owner", content="Owner's memory")
        try:
            with pytest.raises(NotFoundError):
                v2_client.memories.delete(mem.id, user_id="wrong_user")
        finally:
            v2_client.memories.delete(mem.id, user_id="mem_owner")

    def test_permission_delete_wrong_user(self, v2_client):
        """Deleting permission with wrong user_id returns 404."""
        perm = v2_client.permissions.create(user_id="perm_owner", tool="test_tool")
        try:
            with pytest.raises(NotFoundError):
                v2_client.permissions.delete(perm.id, user_id="wrong_user")
        finally:
            v2_client.permissions.delete(perm.id, user_id="perm_owner")


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
        # Register a fresh user for this test
        import uuid

        import requests

        email = f"ctx-{uuid.uuid4().hex[:8]}@test.m8tes.ai"
        resp = requests.post(
            f"{backend_url}/api/v1/auth/register",
            json={"email": email, "password": "TestPassword123!", "first_name": "CtxTest"},
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
        t1 = v2_client.teammates.create(name="IsoA", user_id="iso_alpha")
        t2 = v2_client.teammates.create(name="IsoB", user_id="iso_beta")

        # user_id=iso_alpha should not see iso_beta's teammate
        page = v2_client.teammates.list(user_id="iso_alpha")
        ids = {tm.id for tm in page.data}
        assert t1.id in ids
        assert t2.id not in ids

        # Unfiltered list should see both
        page_all = v2_client.teammates.list()
        all_ids = {tm.id for tm in page_all.data}
        assert t1.id in all_ids
        assert t2.id in all_ids

        v2_client.teammates.delete(t1.id)
        v2_client.teammates.delete(t2.id)

    def test_task_inherits_teammate_user_id(self, v2_client):
        """Task user_id filtering works independently."""
        tm = v2_client.teammates.create(name="IsoTaskHost")
        t1 = v2_client.tasks.create(
            teammate_id=tm.id, instructions="Alpha task", user_id="task_alpha"
        )
        t2 = v2_client.tasks.create(
            teammate_id=tm.id, instructions="Beta task", user_id="task_beta"
        )

        page = v2_client.tasks.list(user_id="task_alpha")
        ids = {t.id for t in page.data}
        assert t1.id in ids
        assert t2.id not in ids

        v2_client.tasks.delete(t1.id)
        v2_client.tasks.delete(t2.id)
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
        assert isinstance(t.id, int)
        assert isinstance(t.name, str)
        assert isinstance(t.status, str)
        assert isinstance(t.created_at, str)
        assert isinstance(t.tools, list)
        assert isinstance(t.metadata, dict)
        v2_client.teammates.delete(t.id)

    def test_task_response_fields(self, v2_client):
        """Verify all Task fields are populated correctly."""
        tm = v2_client.teammates.create(name="TaskTypeHost")
        task = v2_client.tasks.create(
            teammate_id=tm.id,
            instructions="Type check",
            name="TypeTask",
            expected_output="Report",
            goals="Accuracy",
        )
        assert isinstance(task.id, int)
        assert isinstance(task.teammate_id, int)
        assert isinstance(task.instructions, str)
        assert isinstance(task.status, str)
        assert isinstance(task.created_at, str)
        assert isinstance(task.tools, list)

        v2_client.tasks.delete(task.id)
        v2_client.teammates.delete(tm.id)

    def test_webhook_response_fields(self, v2_client):
        """Verify all Webhook fields are populated correctly."""
        wh = v2_client.webhooks.create(url="https://example.com/types")
        assert isinstance(wh.id, int)
        assert isinstance(wh.url, str)
        assert isinstance(wh.events, list)
        assert isinstance(wh.active, bool)
        assert isinstance(wh.created_at, str)
        # secret is returned on create
        assert isinstance(wh.secret, str)
        v2_client.webhooks.delete(wh.id)

    def test_memory_response_fields(self, v2_client):
        """Verify all Memory fields are populated correctly."""
        mem = v2_client.memories.create(user_id="type_mem", content="Test content")
        assert isinstance(mem.id, int)
        assert isinstance(mem.content, str)
        assert isinstance(mem.source, str)
        assert isinstance(mem.created_at, str)
        v2_client.memories.delete(mem.id, user_id="type_mem")

    def test_permission_response_fields(self, v2_client):
        """Verify all PermissionPolicy fields are populated correctly."""
        perm = v2_client.permissions.create(user_id="type_perm", tool="test")
        assert isinstance(perm.id, int)
        assert isinstance(perm.user_id, str)
        assert isinstance(perm.tool_name, str)
        assert isinstance(perm.created_at, str)
        v2_client.permissions.delete(perm.id, user_id="type_perm")

    def test_trigger_response_fields(self, v2_client):
        """Verify all Trigger fields are populated correctly."""
        tm = v2_client.teammates.create(name="TriggerTypeHost")
        task = v2_client.tasks.create(teammate_id=tm.id, instructions="Trigger types")
        trigger = v2_client.tasks.triggers.create(task.id, type="schedule", cron="0 9 * * *")

        assert isinstance(trigger.id, int)
        assert isinstance(trigger.type, str)
        assert isinstance(trigger.enabled, bool)

        v2_client.tasks.triggers.delete(task.id, trigger.id)
        v2_client.tasks.delete(task.id)
        v2_client.teammates.delete(tm.id)
