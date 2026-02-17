"""V2 SDK integration tests — real M8tes client against real FastAPI backend.

Tests CRUD endpoints only (no run execution, no Claude SDK calls).

Requirements:
    1. Backend running at localhost:8000 (or E2E_BACKEND_URL)
    2. Database running (via docker compose)

Run: pytest tests/integration/test_v2_integration.py -v -m integration
"""

import pytest

from m8tes._exceptions import NotFoundError
from m8tes._types import (
    Memory,
    PermissionPolicy,
    SyncPage,
    Task,
    Teammate,
    Trigger,
    Webhook,
)

# ── Teammates ────────────────────────────────────────────────────────


@pytest.mark.integration
class TestTeammatesCRUD:
    def test_full_lifecycle(self, v2_client):
        """Create → list → get → update → delete → verify 404."""
        # Create
        t = v2_client.teammates.create(name="IntegBot", instructions="Test bot")
        assert isinstance(t, Teammate)
        assert t.id is not None
        assert t.name == "IntegBot"

        # List — should include newly created teammate
        page = v2_client.teammates.list()
        assert isinstance(page, SyncPage)
        assert any(tm.id == t.id for tm in page.data)

        # Get
        fetched = v2_client.teammates.get(t.id)
        assert fetched.id == t.id
        assert fetched.name == "IntegBot"

        # Update
        updated = v2_client.teammates.update(t.id, name="UpdatedBot", tools=["gmail"])
        assert updated.name == "UpdatedBot"
        assert "gmail" in (updated.tools or [])

        # Delete
        v2_client.teammates.delete(t.id)

        # Verify deleted
        with pytest.raises(NotFoundError):
            v2_client.teammates.get(t.id)

    def test_create_with_all_fields(self, v2_client):
        """Create teammate with every optional field."""
        t = v2_client.teammates.create(
            name="FullBot",
            instructions="Help with everything",
            tools=["gmail", "slack"],
            role="support",
            goals="Resolve tickets",
            user_id="tenant_1",
            metadata={"team": "ops"},
            allowed_senders=["@acme.com"],
        )
        assert t.name == "FullBot"
        assert t.user_id == "tenant_1"

        # Cleanup
        v2_client.teammates.delete(t.id)

    def test_user_id_filtering(self, v2_client):
        """List with user_id only returns matching teammates."""
        t1 = v2_client.teammates.create(name="TenantA", user_id="a")
        t2 = v2_client.teammates.create(name="TenantB", user_id="b")

        page_a = v2_client.teammates.list(user_id="a")
        ids = [tm.id for tm in page_a.data]
        assert t1.id in ids
        assert t2.id not in ids

        # Cleanup
        v2_client.teammates.delete(t1.id)
        v2_client.teammates.delete(t2.id)


# ── Tasks ────────────────────────────────────────────────────────────


@pytest.mark.integration
class TestTasksCRUD:
    def test_full_lifecycle(self, v2_client):
        """Create → list → get → update → delete."""
        # Need a teammate first
        tm = v2_client.teammates.create(name="TaskHost")

        task = v2_client.tasks.create(
            teammate_id=tm.id, instructions="Weekly summary", name="Weekly"
        )
        assert isinstance(task, Task)
        assert task.teammate_id == tm.id

        # List
        page = v2_client.tasks.list(teammate_id=tm.id)
        assert any(t.id == task.id for t in page.data)

        # Get
        fetched = v2_client.tasks.get(task.id)
        assert fetched.instructions == "Weekly summary"

        # Update
        updated = v2_client.tasks.update(task.id, instructions="Daily summary")
        assert updated.instructions == "Daily summary"

        # Delete
        v2_client.tasks.delete(task.id)
        with pytest.raises(NotFoundError):
            v2_client.tasks.get(task.id)

        # Cleanup
        v2_client.teammates.delete(tm.id)


# ── Task Triggers ────────────────────────────────────────────────────


@pytest.mark.integration
class TestTaskTriggers:
    def test_schedule_trigger_lifecycle(self, v2_client):
        """Create schedule trigger → list → delete."""
        tm = v2_client.teammates.create(name="TriggerHost")
        task = v2_client.tasks.create(teammate_id=tm.id, instructions="Cron job")

        trigger = v2_client.tasks.triggers.create(task.id, type="schedule", cron="0 9 * * 1")
        assert isinstance(trigger, Trigger)
        assert trigger.type == "schedule"

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


# ── Memories ─────────────────────────────────────────────────────────


@pytest.mark.integration
class TestMemoriesCRUD:
    def test_full_lifecycle(self, v2_client):
        """Create → list → delete → verify empty."""
        user_id = "mem_test_user"

        mem = v2_client.memories.create(user_id=user_id, content="Prefers dark mode")
        assert isinstance(mem, Memory)
        assert mem.content == "Prefers dark mode"

        # List
        page = v2_client.memories.list(user_id=user_id)
        assert any(m.id == mem.id for m in page.data)

        # Delete
        v2_client.memories.delete(mem.id, user_id=user_id)

        # Verify gone
        page_after = v2_client.memories.list(user_id=user_id)
        assert not any(m.id == mem.id for m in page_after.data)


# ── Permissions ──────────────────────────────────────────────────────


@pytest.mark.integration
class TestPermissionsCRUD:
    def test_full_lifecycle(self, v2_client):
        """Create → list → delete → verify gone."""
        user_id = "perm_test_user"

        perm = v2_client.permissions.create(user_id=user_id, tool="gmail")
        assert isinstance(perm, PermissionPolicy)

        # List
        page = v2_client.permissions.list(user_id=user_id)
        assert any(p.id == perm.id for p in page.data)

        # Delete
        v2_client.permissions.delete(perm.id, user_id=user_id)

        # Verify gone
        page_after = v2_client.permissions.list(user_id=user_id)
        assert not any(p.id == perm.id for p in page_after.data)


# ── Webhooks ─────────────────────────────────────────────────────────


@pytest.mark.integration
class TestWebhooksCRUD:
    def test_full_lifecycle(self, v2_client):
        """Create → list → get → update → delete."""
        wh = v2_client.webhooks.create(url="https://example.com/hook", events=["run.completed"])
        assert isinstance(wh, Webhook)
        assert wh.url == "https://example.com/hook"
        assert wh.secret is not None

        # List
        page = v2_client.webhooks.list()
        assert any(w.id == wh.id for w in page.data)

        # Get
        fetched = v2_client.webhooks.get(wh.id)
        assert fetched.id == wh.id

        # Update with secret rotation
        updated = v2_client.webhooks.update(
            wh.id, url="https://example.com/v2/hook", rotate_secret=True
        )
        assert updated.url == "https://example.com/v2/hook"

        # Delete
        v2_client.webhooks.delete(wh.id)

        with pytest.raises(NotFoundError):
            v2_client.webhooks.get(wh.id)

    def test_deliveries_empty(self, v2_client):
        """Newly created webhook has no deliveries."""
        wh = v2_client.webhooks.create(url="https://example.com/empty")
        page = v2_client.webhooks.list_deliveries(wh.id)
        assert isinstance(page, SyncPage)
        assert len(page.data) == 0

        # Cleanup
        v2_client.webhooks.delete(wh.id)


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

        # Collect all via pagination
        all_ids = set()
        cursor = None
        for _ in range(10):  # safety limit
            page = v2_client.teammates.list(limit=2, starting_after=cursor)
            for tm in page.data:
                all_ids.add(tm.id)
            if not page.has_more:
                break
            cursor = page.data[-1].id

        # All created teammates should appear
        for t in created:
            assert t.id in all_ids

        # Cleanup
        for t in created:
            v2_client.teammates.delete(t.id)


# ── Error Handling ───────────────────────────────────────────────────


@pytest.mark.integration
class TestErrorHandling:
    def test_not_found(self, v2_client):
        """404 mapped to NotFoundError with status_code."""
        with pytest.raises(NotFoundError) as exc_info:
            v2_client.teammates.get(999999)
        assert exc_info.value.status_code == 404

    def test_unauthenticated(self):
        """Invalid API key raises error on first request."""
        from m8tes import M8tes
        from m8tes._exceptions import AuthenticationError, M8tesError

        bad_client = M8tes(api_key="invalid_key", base_url="http://localhost:8000/api/v2")
        with pytest.raises((AuthenticationError, M8tesError)):
            bad_client.teammates.list()
        bad_client.close()


# ── Apps (read-only) ─────────────────────────────────────────────────


@pytest.mark.integration
class TestAppsReadOnly:
    def test_list_apps(self, v2_client):
        """List available apps (may be empty if no tools seeded)."""
        page = v2_client.apps.list()
        assert isinstance(page, SyncPage)
