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

import contextlib
import os
import uuid

import pytest

from m8tes import M8tes
from m8tes._exceptions import (
    AuthenticationError,
    BillingError,
    ConflictError,
    M8tesError,
    NotFoundError,
    ValidationError,
)
from m8tes._types import (
    AccountSettings,
    AuditLog,
    BuiltInTool,
    EmailInbox,
    EndUser,
    FetchmailInbox,
    McpServer,
    Memory,
    Model,
    PermissionPolicy,
    Run,
    Skill,
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


def _chat_guid() -> str:
    """Generate a unique iMessage chat GUID for integration tests."""
    return f"iMessage;-;+1555{uuid.uuid4().hex[:10]}"


def _strict_test_catalog() -> bool:
    """True when integration tests should fail instead of skip on missing seeded apps."""
    return os.getenv("E2E_REQUIRE_TEST_CATALOG") == "1"


def _require_available_apps(v2_client: M8tes, count: int) -> list[str]:
    """Return app names or fail/skip depending on whether a deterministic catalog is required."""
    available = [a.name for a in v2_client.apps.list().data]
    if len(available) >= count:
        return available

    message = f"Need >={count} tools, got {len(available)}"
    if _strict_test_catalog():
        raise AssertionError(message)
    pytest.skip(message)


def _require_api_key_app(v2_client: M8tes):
    """Return an API-key app or fail/skip depending on deterministic catalog requirements."""
    app = next(
        (
            item
            for item in v2_client.apps.list().data
            if item.auth_type in ("api_key", "api_key_proxy")
        ),
        None,
    )
    if app is not None:
        return app

    message = "No api_key app available in the backend catalog"
    if _strict_test_catalog():
        raise AssertionError(message)
    pytest.skip(message)


def _new_v2_client(backend_url: str, *, email_prefix: str) -> M8tes:
    """Register a throwaway user and return an authenticated V2 client."""
    import requests

    email = f"{email_prefix}-{uuid.uuid4().hex[:8]}@test.m8tes.ai"
    resp = requests.post(
        f"{backend_url}/api/v1/auth/register",
        json={
            "email": email,
            "password": "TestPassword123!",
            "first_name": "SDKInteg",
        },
    )
    assert resp.status_code == 201, f"Registration failed: {resp.text}"
    token = resp.json()["api_key"]
    return M8tes(api_key=token, base_url=f"{backend_url}/api/v2")


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

    def test_model_roundtrip(self, v2_client):
        """model persists on create, updates via PATCH, clears via null, survives GET."""
        t = v2_client.teammates.create(name="ModelBot", model="sonnet")
        try:
            assert t.model == "sonnet"
            updated = v2_client.teammates.update(t.id, model="opus")
            assert updated.model == "opus"
            fetched = v2_client.teammates.get(t.id)
            assert fetched.model == "opus"
            # model=None sends JSON null → clears back to platform default (D4)
            cleared = v2_client.teammates.update(t.id, model=None)
            assert cleared.model is None
            assert v2_client.teammates.get(t.id).model is None
        finally:
            v2_client.teammates.delete(t.id)

    def test_model_defaults_to_none(self, v2_client):
        """Omitting model leaves it None (platform default)."""
        t = v2_client.teammates.create(name="NoModelBot")
        try:
            assert t.model is None
        finally:
            v2_client.teammates.delete(t.id)

    def test_invalid_model_rejected(self, v2_client):
        """model outside sonnet|opus is rejected with 422."""
        with pytest.raises(ValidationError):
            v2_client.teammates.create(name="BadModelBot", model="gpt-5")

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
        available = _require_available_apps(v2_client, 2)
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
        available = _require_available_apps(v2_client, 1)
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

    def test_imessage_roundtrip(self, v2_client):
        """Create and update iMessage config through the public V2 SDK surface.

        iMessage now routes through a per-account bridge, so we register one first
        (example.com resolves to a public IP and passes the SSRF egress check) and
        bind the teammate to it via bridge_id.
        """
        original_guid = _chat_guid()
        updated_guid = _chat_guid()
        bridge = v2_client.bridges.create(
            name="it-bridge", server_url="https://example.com", password="bb-pw"
        )
        assert bridge.webhook_secret  # returned once on create
        t = v2_client.teammates.create(
            name="messages-bot",
            inbound_imessage_enabled=True,
            bridge_id=bridge.id,
            imessage_chat_guid=original_guid,
        )
        try:
            assert t.inbound_imessage_enabled is True
            assert t.imessage_chat_guid == original_guid
            assert t.bridge_id == bridge.id

            fetched = v2_client.teammates.get(t.id)
            assert fetched.inbound_imessage_enabled is True
            assert fetched.imessage_chat_guid == original_guid

            updated = v2_client.teammates.update(
                t.id,
                inbound_imessage_enabled=True,
                imessage_chat_guid=updated_guid,
            )
            assert updated.inbound_imessage_enabled is True
            assert updated.imessage_chat_guid == updated_guid
        finally:
            v2_client.teammates.delete(t.id)
            v2_client.bridges.delete(bridge.id)

    def test_imessage_duplicate_conflict(self, v2_client):
        """Duplicate iMessage chat GUIDs on the SAME bridge raise a conflict."""
        chat_guid = _chat_guid()
        bridge = v2_client.bridges.create(
            name="it-bridge-dup", server_url="https://example.com", password="bb-pw"
        )
        first = v2_client.teammates.create(
            name="messages-owner",
            inbound_imessage_enabled=True,
            bridge_id=bridge.id,
            imessage_chat_guid=chat_guid,
        )
        second = v2_client.teammates.create(name="messages-contender")
        try:
            with pytest.raises(ConflictError):
                v2_client.teammates.update(
                    second.id,
                    inbound_imessage_enabled=True,
                    bridge_id=bridge.id,
                    imessage_chat_guid=chat_guid,
                )
        finally:
            v2_client.teammates.delete(first.id)
            v2_client.teammates.delete(second.id)
            v2_client.bridges.delete(bridge.id)

    def test_bridge_owner_handle_and_connection_test(self, v2_client):
        """owner_handle round-trips (normalized) and the /test endpoint returns a verdict."""
        bridge = v2_client.bridges.create(
            name="it-bridge-owner",
            server_url="https://example.com",
            password="bb-pw",
            owner_handle="+1 (555) 000-1111",
        )
        try:
            # Stored normalized; create surfaces the registration connection probe result.
            assert bridge.owner_handle == "+15550001111"
            # The probe ran (example.com is not a real BlueBubbles server).
            assert bridge.connection_ok in (True, False)

            fetched = v2_client.bridges.get(bridge.id)
            assert fetched.owner_handle == "+15550001111"

            # The explicit connection test returns an ok/detail verdict (no message sent).
            result = v2_client.bridges.test(bridge.id)
            assert "ok" in result
        finally:
            v2_client.bridges.delete(bridge.id)

    def test_hosted_imessage_provision(self, v2_client):
        """One-click hosted iMessage: provision is idempotent and exposes the handle + link
        code — or raises 503 when the platform's central server isn't configured."""
        try:
            bridge = v2_client.bridges.provision()
        except M8tesError as e:
            assert e.status_code == 503  # central server not configured on this backend
            return
        try:
            assert bridge.kind == "hosted"
            assert bridge.name == "m8tes"
            assert bridge.link_code
            assert bridge.webhook_secret is None  # never shown for hosted
            # Idempotent: a second provision returns the same bridge.
            assert v2_client.bridges.provision().id == bridge.id
            # Listing verified handles works (empty until someone texts the code).
            assert isinstance(v2_client.bridges.list_handles(bridge.id), list)

            # A single-use rotate issues a new, one-shot code; the default rotate is multi-use.
            single = v2_client.bridges.regenerate_link_code(bridge.id, single_use=True)
            assert single.link_code_single_use is True
            assert single.link_code and single.link_code != bridge.link_code
            multi = v2_client.bridges.regenerate_link_code(bridge.id)
            assert multi.link_code_single_use is False
        finally:
            v2_client.bridges.delete(bridge.id)

    def test_blooio_provision_endpoint_reachable(self, v2_client):
        """The managed-Blooio provision endpoint is reachable via the SDK. A bogus number
        yields 503 (Blooio unconfigured) or 400/502 (number not on the account / provider
        failure) — either proves the SDK method + HTTP contract without registering a real
        webhook. If it unexpectedly succeeds (a genuinely owned number), clean up."""
        try:
            bridge = v2_client.bridges.provision_blooio("+15550009999")
        except M8tesError as e:
            assert e.status_code in (400, 502, 503)
            return
        try:
            assert bridge.kind == "blooio"
            assert bridge.provider_number
        finally:
            v2_client.bridges.delete(bridge.id)


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

    def test_create_with_webhook(self, v2_client):
        """Create teammate with webhook=True — URL returned immediately, enabled on GET."""
        tm = v2_client.teammates.create(name="wh-create-test", webhook=True)
        try:
            assert tm.webhook_enabled is True
            assert tm.webhook_url is not None
            assert "mates" in tm.webhook_url
            # URL not available on subsequent GET (shown once)
            fetched = v2_client.teammates.get(tm.id)
            assert fetched.webhook_enabled is True
            assert fetched.webhook_url is None
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

    def test_create_with_email_inbox(self, v2_client):
        """Create teammate with email_inbox=True — address returned immediately."""
        tm = v2_client.teammates.create(name="inbox-create-test", email_inbox=True)
        try:
            assert tm.inbound_email_enabled is True
            assert tm.email_address is not None
            assert "@" in tm.email_address
        finally:
            v2_client.teammates.delete(tm.id)


@pytest.mark.integration
class TestTeammateFetchmail:
    """Fetchmail (read-only inbox) lifecycle tests."""

    def test_enable_disable_lifecycle(self, v2_client):
        """Enable fetchmail → verify FetchmailInbox → disable → 204."""
        tm = v2_client.teammates.create(name="FetchmailHost")
        try:
            inbox = v2_client.teammates.enable_fetchmail(tm.id)
            assert isinstance(inbox, FetchmailInbox)
            assert inbox.enabled is True
            assert inbox.address is not None
            assert "@" in inbox.address

            v2_client.teammates.disable_fetchmail(tm.id)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_enable_idempotent(self, v2_client):
        """Enable twice returns the same address."""
        tm = v2_client.teammates.create(name="FetchmailIdem")
        try:
            inbox1 = v2_client.teammates.enable_fetchmail(tm.id)
            inbox2 = v2_client.teammates.enable_fetchmail(tm.id)
            assert inbox1.address == inbox2.address
        finally:
            v2_client.teammates.delete(tm.id)

    def test_fetchmail_fields_in_get(self, v2_client):
        """Fetchmail fields appear in teammate.get() response."""
        tm = v2_client.teammates.create(name="FetchmailGet")
        try:
            v2_client.teammates.enable_fetchmail(tm.id)
            fetched = v2_client.teammates.get(tm.id)
            assert fetched.fetchmail_enabled is True
            assert fetched.fetchmail_address is not None
            assert "@" in fetched.fetchmail_address
        finally:
            v2_client.teammates.delete(tm.id)

    def test_independent_from_email_inbox(self, v2_client):
        """Fetchmail and email inbox use different addresses."""
        tm = v2_client.teammates.create(name="FetchmailIndep")
        try:
            email = v2_client.teammates.enable_email_inbox(tm.id)
            fetchmail = v2_client.teammates.enable_fetchmail(tm.id)
            assert email.address != fetchmail.address
        finally:
            v2_client.teammates.delete(tm.id)

    def test_enable_nonexistent_404(self, v2_client):
        """Enable fetchmail on nonexistent teammate returns 404."""
        with pytest.raises(NotFoundError):
            v2_client.teammates.enable_fetchmail(999999)

    def test_disable_nonexistent_404(self, v2_client):
        """Disable fetchmail on nonexistent teammate returns 404."""
        with pytest.raises(NotFoundError):
            v2_client.teammates.disable_fetchmail(999999)


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
        available = _require_available_apps(v2_client, 2)
        tool_a, tool_b = available[0], available[1]
        tm = v2_client.teammates.create(name="TaskToolsHost")
        try:
            task = v2_client.tasks.create(
                teammate_id=tm.id, instructions="With tools", tools=[tool_a, tool_b]
            )
            try:
                assert set(task.tools) == {tool_a, tool_b}

                updated = v2_client.tasks.update(task.id, tools=[tool_b])
                assert updated.tools == [tool_b]

                fetched = v2_client.tasks.get(task.id)
                assert fetched.tools == [tool_b]
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

    def test_create_with_webhook(self, v2_client):
        """tasks.create(webhook=True) returns webhook_url at creation time."""
        tm = v2_client.teammates.create(name="WebhookTaskHost")
        try:
            task = v2_client.tasks.create(
                teammate_id=tm.id,
                instructions="webhook triggered task",
                webhook=True,
            )
            try:
                assert isinstance(task, Task)
                assert task.webhook_url is not None
                assert "webhooks/tasks" in task.webhook_url
                assert task.webhook_enabled is True
            finally:
                v2_client.tasks.delete(task.id)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_create_with_schedule(self, v2_client):
        """tasks.create(schedule=...) creates cron trigger at creation time."""
        tm = v2_client.teammates.create(name="ScheduleTaskHost")
        try:
            task = v2_client.tasks.create(
                teammate_id=tm.id,
                instructions="scheduled task",
                schedule="0 9 * * 1",
            )
            try:
                assert isinstance(task, Task)
                assert task.id is not None
            finally:
                v2_client.tasks.delete(task.id)
        finally:
            v2_client.teammates.delete(tm.id)


# ── Task Email Notifications ──────────────────────────────────────────


@pytest.mark.integration
class TestTaskEmailNotifications:
    def test_create_defaults_to_true(self, v2_client):
        """email_notifications defaults to True when omitted."""
        tm = v2_client.teammates.create(name="EmailNotifDefault")
        try:
            task = v2_client.tasks.create(teammate_id=tm.id, instructions="Daily digest")
            try:
                assert task.email_notifications is True
            finally:
                v2_client.tasks.delete(task.id)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_create_with_false(self, v2_client):
        """email_notifications=False is persisted and returned."""
        tm = v2_client.teammates.create(name="EmailNotifFalse")
        try:
            task = v2_client.tasks.create(
                teammate_id=tm.id,
                instructions="Silent task",
                email_notifications=False,
            )
            try:
                assert task.email_notifications is False
                fetched = v2_client.tasks.get(task.id)
                assert fetched.email_notifications is False
            finally:
                v2_client.tasks.delete(task.id)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_update_toggle(self, v2_client):
        """email_notifications can be toggled via update."""
        tm = v2_client.teammates.create(name="EmailNotifToggle")
        try:
            task = v2_client.tasks.create(teammate_id=tm.id, instructions="Toggleable")
            try:
                assert task.email_notifications is True
                updated = v2_client.tasks.update(task.id, email_notifications=False)
                assert updated.email_notifications is False
                re_enabled = v2_client.tasks.update(task.id, email_notifications=True)
                assert re_enabled.email_notifications is True
            finally:
                v2_client.tasks.delete(task.id)
        finally:
            v2_client.teammates.delete(tm.id)


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
                v2_client.tasks.triggers.create(task.id, type="webhook")
                v2_client.tasks.triggers.create(task.id, type="email")

                triggers = v2_client.tasks.triggers.list(task.id)
                types = {tr.type for tr in triggers}
                assert {"schedule", "webhook", "email"} == types

                v2_client.tasks.triggers.delete(task.id, t_sched.id)
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


@pytest.mark.integration
class TestTaskWebhookToggle:
    """tasks.enable_webhook / disable_webhook — enable, rotate, disable."""

    def test_enable_disable_lifecycle(self, v2_client):
        tm = v2_client.teammates.create(name="TaskHookHost")
        try:
            task = v2_client.tasks.create(teammate_id=tm.id, instructions="hook target")
            try:
                hook = v2_client.tasks.enable_webhook(task.id)
                assert hook.enabled is True
                assert "/webhooks/tasks/" in hook.url

                # Re-enable rotates the token (old URL invalidated).
                rotated = v2_client.tasks.enable_webhook(task.id)
                assert rotated.url != hook.url

                # Disable removes the webhook trigger.
                v2_client.tasks.disable_webhook(task.id)
                triggers = v2_client.tasks.triggers.list(task.id)
                assert not any(tr.type == "webhook" for tr in triggers)
            finally:
                v2_client.tasks.delete(task.id)
        finally:
            v2_client.teammates.delete(tm.id)


@pytest.mark.integration
class TestByIdEndUserScope:
    """By-id get/update/delete honor the user_id end-user scope (404 on mismatch)."""

    def test_teammate_by_id_scope(self, v2_client):
        alice = v2_client.teammates.create(name="AliceBot", user_id="alice")
        try:
            assert v2_client.teammates.get(alice.id, user_id="alice").id == alice.id
            with pytest.raises(NotFoundError):
                v2_client.teammates.get(alice.id, user_id="bob")
            with pytest.raises(NotFoundError):
                v2_client.teammates.update(alice.id, user_id="bob", name="hijack")
        finally:
            v2_client.teammates.delete(alice.id)

    def test_task_by_id_scope(self, v2_client):
        alice = v2_client.teammates.create(name="AliceTaskBot", user_id="alice")
        try:
            task = v2_client.tasks.create(
                teammate_id=alice.id, instructions="scoped", user_id="alice"
            )
            try:
                assert v2_client.tasks.get(task.id, user_id="alice").id == task.id
                with pytest.raises(NotFoundError):
                    v2_client.tasks.get(task.id, user_id="bob")
            finally:
                v2_client.tasks.delete(task.id, user_id="alice")
        finally:
            v2_client.teammates.delete(alice.id)


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

    def test_account_scope_and_update(self, v2_client):
        """Account-level memories (no user_id) live in their own scope and are editable."""
        mem = v2_client.memories.create(content=f"Account fact {_uid()}")
        try:
            assert mem.user_id is None
            # Not visible in any end-user scope
            page = v2_client.memories.list(user_id=_uid())
            assert not any(m.id == mem.id for m in page.data)
            # Visible in the account scope
            page = v2_client.memories.list()
            assert any(m.id == mem.id for m in page.data)
            # Editable in place
            updated = v2_client.memories.update(mem.id, content=f"Corrected fact {_uid()}")
            assert updated.content.startswith("Corrected fact")
        finally:
            v2_client.memories.delete(mem.id)

    def test_update_end_user_memory(self, v2_client):
        user_id = _uid()
        mem = v2_client.memories.create(user_id=user_id, content="Prefers dark mode")
        try:
            updated = v2_client.memories.update(
                mem.id, content="Prefers light mode", user_id=user_id
            )
            assert updated.content == "Prefers light mode"
            with pytest.raises(NotFoundError):  # wrong scope never matches
                v2_client.memories.update(mem.id, content="X")
        finally:
            v2_client.memories.delete(mem.id, user_id=user_id)

    def test_search_by_query(self, v2_client):
        """list(query=...) keyword-filters the end-user's memories (case-insensitive)."""
        user_id = _uid()
        match = v2_client.memories.create(user_id=user_id, content="Prefers email over Slack")
        other = v2_client.memories.create(user_id=user_id, content="Budget is 5000 DKK")
        try:
            page = v2_client.memories.list(user_id=user_id, query="EMAIL")
            ids = {m.id for m in page.data}
            assert match.id in ids
            assert other.id not in ids
        finally:
            v2_client.memories.delete(match.id, user_id=user_id)
            v2_client.memories.delete(other.id, user_id=user_id)

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
        """After deleting a permission, can recreate same (user_id, tool)."""
        uid = _uid()
        p1 = v2_client.permissions.create(user_id=uid, tool="recreate_tool")
        v2_client.permissions.delete(p1.id, user_id=uid)

        p2 = v2_client.permissions.create(user_id=uid, tool="recreate_tool")
        try:
            assert p2.tool_name == "recreate_tool"
            assert p2.user_id == uid
            # Verify it actually exists via list
            listed = v2_client.permissions.list(user_id=uid)
            assert any(p.id == p2.id for p in listed.data)
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


# ── Webhook Isolation + Edges ────────────────────────────────────────


@pytest.mark.integration
class TestWebhookIsolationAndEdges:
    """Webhook behavior parity checks not covered by basic CRUD tests."""

    def test_default_events_match_v2_defaults(self, v2_client):
        """Create without events uses V2 defaults exactly."""
        wh = v2_client.webhooks.create(url="https://example.com/defaults-check")
        try:
            assert set(wh.events) == {"run.completed", "run.failed", "run.cancelled"}
        finally:
            v2_client.webhooks.delete(wh.id)

    def test_create_with_empty_events_list(self, v2_client):
        """Empty events list is accepted and roundtrips as empty."""
        wh = v2_client.webhooks.create(url="https://example.com/empty-events", events=[])
        try:
            assert wh.events == []
        finally:
            v2_client.webhooks.delete(wh.id)

    def test_get_other_users_webhook_hidden(self, v2_client, backend_url):
        """GET another account's webhook returns NotFoundError (404)."""
        other_client = _new_v2_client(backend_url, email_prefix="wh-get-cross")
        wh = v2_client.webhooks.create(url="https://example.com/cross-get")
        try:
            with pytest.raises(NotFoundError):
                other_client.webhooks.get(wh.id)
        finally:
            other_client.close()
            v2_client.webhooks.delete(wh.id)

    def test_update_other_users_webhook_hidden(self, v2_client, backend_url):
        """PATCH another account's webhook returns NotFoundError (404)."""
        other_client = _new_v2_client(backend_url, email_prefix="wh-update-cross")
        wh = v2_client.webhooks.create(url="https://example.com/cross-update")
        try:
            with pytest.raises(NotFoundError):
                other_client.webhooks.update(wh.id, url="https://example.com/forbidden")
        finally:
            other_client.close()
            v2_client.webhooks.delete(wh.id)

    def test_delete_other_users_webhook_hidden(self, v2_client, backend_url):
        """DELETE another account's webhook returns NotFoundError (404)."""
        other_client = _new_v2_client(backend_url, email_prefix="wh-delete-cross")
        wh = v2_client.webhooks.create(url="https://example.com/cross-delete")
        try:
            with pytest.raises(NotFoundError):
                other_client.webhooks.delete(wh.id)
            # Owner can still fetch it after failed cross-account delete attempt.
            owner_view = v2_client.webhooks.get(wh.id)
            assert owner_view.id == wh.id
        finally:
            other_client.close()
            v2_client.webhooks.delete(wh.id)

    def test_list_only_returns_own_webhooks(self, v2_client, backend_url):
        """Each account only sees its own webhooks in list()."""
        other_client = _new_v2_client(backend_url, email_prefix="wh-list-cross")
        wh_a = v2_client.webhooks.create(url="https://example.com/owner-a")
        wh_b = other_client.webhooks.create(url="https://example.com/owner-b")
        try:
            page_a = v2_client.webhooks.list(limit=100)
            ids_a = {w.id for w in page_a.data}
            assert wh_a.id in ids_a
            assert wh_b.id not in ids_a

            page_b = other_client.webhooks.list(limit=100)
            ids_b = {w.id for w in page_b.data}
            assert wh_b.id in ids_b
            assert wh_a.id not in ids_b
        finally:
            other_client.webhooks.delete(wh_b.id)
            v2_client.webhooks.delete(wh_a.id)
            other_client.close()

    def test_list_deliveries_other_users_webhook_hidden(self, v2_client, backend_url):
        """Listing deliveries for another account's webhook returns NotFoundError."""
        other_client = _new_v2_client(backend_url, email_prefix="wh-deliveries-cross")
        wh = v2_client.webhooks.create(url="https://example.com/cross-deliveries")
        try:
            with pytest.raises(NotFoundError):
                other_client.webhooks.list_deliveries(wh.id)
        finally:
            other_client.close()
            v2_client.webhooks.delete(wh.id)


# ── Audit logs ───────────────────────────────────────────────────────


@pytest.mark.integration
class TestAuditLogs:
    def test_list_returns_typed_page(self, v2_client):
        """Audit logs list returns a typed SyncPage."""
        page = v2_client.audit_logs.list(limit=5)
        assert isinstance(page, SyncPage)
        assert all(isinstance(log, AuditLog) for log in page.data)

    def test_filters_and_scoping(self, v2_client, backend_url):
        """Audit logs are account-scoped and support basic filters."""
        other_client = _new_v2_client(backend_url, email_prefix="audit-cross")

        # Generate one scoped log entry for this account.
        v2_client.runs.list(limit=1)
        own_logs = v2_client.audit_logs.list(resource_type="run", method="GET", limit=50)
        own_ids = {log.id for log in own_logs.data}

        # Generate logs on another account and ensure they are not visible here.
        other_client.runs.list(limit=1)
        try:
            other_logs = other_client.audit_logs.list(resource_type="run", method="GET", limit=50)
            other_ids = {log.id for log in other_logs.data}
            assert own_ids.isdisjoint(other_ids)
        finally:
            other_client.close()


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

    @pytest.mark.parametrize(
        "status",
        [
            "running",
            "paused",
            "awaiting_approval",
            "completed",
            "failed",
            "cancelled",
            "closed",
            "archived",
        ],
    )
    def test_list_with_all_valid_status_filters(self, v2_client, status):
        """All documented run status filters are accepted by V2."""
        page = v2_client.runs.list(status=status)
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

    def test_outcome_nonexistent_run(self, v2_client):
        """Outcome for nonexistent run returns 404."""
        with pytest.raises(NotFoundError):
            v2_client.runs.outcome(999999)


@pytest.mark.integration
class TestRunsWithFiles:
    def test_create_with_files_multipart(self, v2_client):
        """files= routes through /runs/with-files; local backends without sandbox
        reject attachments with a clean 400 instead of a silent drop."""
        from m8tes._exceptions import M8tesError

        tm = v2_client.teammates.create(name="FileReader")
        try:
            try:
                run = v2_client.runs.create(
                    teammate_id=tm.id,
                    message="Read the attached file",
                    files=[("note.txt", b"hello")],
                    stream=False,
                )
                assert run.id > 0  # sandbox-enabled backend accepted the upload
            except M8tesError as e:
                if e.status_code == 503:
                    pytest.skip("backend has no inference key configured")
                if e.status_code == 429:
                    pytest.skip("backend at run capacity")
                assert e.status_code == 400
                assert "sandbox" in str(e).lower()
        finally:
            v2_client.teammates.delete(tm.id)


@pytest.mark.integration
class TestTeammateEnableDisable:
    def test_disable_enable_round_trip(self, v2_client):
        """Disable pauses without archiving; enable restores."""
        tm = v2_client.teammates.create(name="PauseMe")
        try:
            paused = v2_client.teammates.disable(tm.id)
            assert paused.status == "disabled"
            page = v2_client.teammates.list()
            assert any(t.id == tm.id for t in page.data)  # still listed
            restored = v2_client.teammates.enable(tm.id)
            assert restored.status == "enabled"
        finally:
            v2_client.teammates.delete(tm.id)

    def test_disable_nonexistent_teammate(self, v2_client):
        with pytest.raises(NotFoundError):
            v2_client.teammates.disable(999999)

    def test_list_with_teammate_filter(self, v2_client):
        """Filter runs by teammate_id returns valid page."""
        page = v2_client.runs.list(teammate_id=999999)
        assert isinstance(page, SyncPage)
        assert len(page.data) == 0


# ── Runs: Human-in-the-Loop ─────────────────────────────────────────


@pytest.mark.integration
class TestRunTaskLinkage:
    """runs ↔ tasks pull-path: task_id on runs + runs.list(task_id=...).

    2026-07-13 QA: without this, a scheduled/webhook task's results could only be
    pushed via webhooks — no way to pull run history for a task.
    """

    def test_task_id_filter_accepted_and_scoped(self, v2_client):
        """The filter is a real filter (not silently ignored): a task with no runs
        yields an empty page even when the account has other runs."""
        tm = v2_client.teammates.create(name="TaskLinkage")
        try:
            task = v2_client.tasks.create(teammate_id=tm.id, instructions="never run")
            page = v2_client.runs.list(task_id=task.id)
            assert isinstance(page, SyncPage)
            assert page.data == []
        finally:
            v2_client.teammates.delete(tm.id)


@pytest.mark.integration
@pytest.mark.runtime
class TestRunTaskLinkageRuntime:
    def test_run_carries_task_id_and_filter_returns_it(self, v2_client):
        """Full loop: create run → task_id set → list(task_id=) finds exactly it."""
        tm = v2_client.teammates.create(name="TaskLinkageRun")
        try:
            run = v2_client.runs.create(teammate_id=tm.id, message="linkage", stream=False)
            assert isinstance(run.task_id, int)
            page = v2_client.runs.list(task_id=run.task_id)
            assert [r.id for r in page.data] == [run.id]
            assert page.data[0].task_id == run.task_id
            v2_client.runs.cancel(run.id)
        finally:
            v2_client.teammates.delete(tm.id)


@pytest.mark.integration
@pytest.mark.runtime
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

    def test_create_run_with_task_setup_tools_disabled(self, v2_client):
        """Public SDK can disable internal task-setup tools per run."""
        tm = v2_client.teammates.create(name="NoTaskSetupTools")
        try:
            run = v2_client.runs.create(
                teammate_id=tm.id,
                message="Test without task setup tools",
                stream=False,
                task_setup_tools=False,
            )
            assert isinstance(run, Run)
            assert run.status == "running"
        finally:
            v2_client.teammates.delete(tm.id)

    def test_create_run_with_feedback_disabled(self, v2_client):
        """Public SDK can disable internal feedback tool per run."""
        tm = v2_client.teammates.create(name="NoFeedback")
        try:
            run = v2_client.runs.create(
                teammate_id=tm.id,
                message="Test without feedback tool",
                stream=False,
                feedback=False,
            )
            assert isinstance(run, Run)
            assert run.status == "running"
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

    def test_task_run_approval_mode_without_hitl_rejected(self, v2_client):
        """Task run with permission_mode=approval without HITL raises ValidationError."""
        tm = v2_client.teammates.create(name="TaskApprovalNoHitl")
        try:
            task = v2_client.tasks.create(
                teammate_id=tm.id,
                instructions="Approval mode without hitl should fail",
            )
            try:
                with pytest.raises(ValidationError):
                    v2_client.tasks.run(
                        task.id,
                        stream=False,
                        permission_mode="approval",
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

    def test_task_run_with_task_setup_tools_disabled(self, v2_client):
        """Public SDK can disable internal task-setup tools for saved-task runs."""
        tm = v2_client.teammates.create(name="TaskNoSetupTools")
        try:
            task = v2_client.tasks.create(
                teammate_id=tm.id,
                instructions="Task run without task setup tools",
            )
            try:
                run = v2_client.tasks.run(
                    task.id,
                    stream=False,
                    task_setup_tools=False,
                )
                assert isinstance(run, Run)
            finally:
                v2_client.tasks.delete(task.id)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_task_run_with_feedback_disabled(self, v2_client):
        """Public SDK can disable internal feedback tool for saved-task runs."""
        tm = v2_client.teammates.create(name="TaskNoFeedback")
        try:
            task = v2_client.tasks.create(
                teammate_id=tm.id,
                instructions="Task run without feedback tool",
            )
            try:
                run = v2_client.tasks.run(
                    task.id,
                    stream=False,
                    feedback=False,
                )
                assert isinstance(run, Run)
            finally:
                v2_client.tasks.delete(task.id)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_task_run_approval_mode_with_hitl_accepted(self, v2_client):
        """Task run with permission_mode=approval + HITL is accepted."""
        tm = v2_client.teammates.create(name="TaskHitlApprovalOk")
        try:
            task = v2_client.tasks.create(
                teammate_id=tm.id,
                instructions="HITL approval task ok",
            )
            try:
                run = v2_client.tasks.run(
                    task.id,
                    stream=False,
                    human_in_the_loop=True,
                    permission_mode="approval",
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

    def test_permissions_returns_list_of_permission_requests(self, v2_client):
        """permissions() on a real run returns a typed list (empty on a fresh run)."""
        tm = v2_client.teammates.create(name="PermListCheck")
        try:
            run = v2_client.runs.create(
                teammate_id=tm.id,
                message="permission list test",
                stream=False,
            )
            perms = v2_client.runs.permissions(run.id)
            assert isinstance(perms, list)
            for p in perms:
                assert hasattr(p, "request_id")
                assert hasattr(p, "tool_name")
                assert hasattr(p, "status")
        finally:
            v2_client.teammates.delete(tm.id)

    def test_cross_account_run_hidden(self, v2_client, backend_url):
        """answer/approve/permissions on another account's run return NotFoundError (404).

        Uses a single run to avoid consuming extra monthly quota for each operation.
        """
        other_client = _new_v2_client(backend_url, email_prefix="cross-acct")
        tm = v2_client.teammates.create(name="CrossAccountOwner")
        try:
            run = v2_client.runs.create(
                teammate_id=tm.id,
                message="Cross-account isolation check",
                stream=False,
            )
            with pytest.raises(NotFoundError):
                other_client.runs.answer(run.id, answers={"Q": "A"})
            with pytest.raises(NotFoundError):
                other_client.runs.permissions(run.id)
            with pytest.raises(NotFoundError):
                other_client.runs.approve(run.id, request_id="fake-uuid")
        finally:
            other_client.close()
            v2_client.teammates.delete(tm.id)

    def test_approve_nonexistent_run(self, v2_client):
        """Approve on nonexistent run raises NotFoundError."""
        with pytest.raises(NotFoundError):
            v2_client.runs.approve(999999, request_id="fake-uuid")

    def test_answer_on_running_run(self, v2_client):
        """Answer on a run that's still running (not awaiting input) returns ConflictError."""
        tm = v2_client.teammates.create(name="AnswerRunning")
        try:
            run = v2_client.runs.create(
                teammate_id=tm.id,
                message="Answer test",
                stream=False,
            )
            with pytest.raises(ConflictError):
                v2_client.runs.answer(run.id, answers={"Q": "A"})
        finally:
            v2_client.teammates.delete(tm.id)

    def test_answer_empty_dict_rejected(self, v2_client):
        """Empty answers payload is rejected by V2 schema validation."""
        tm = v2_client.teammates.create(name="AnswerEmptyDict")
        try:
            run = v2_client.runs.create(
                teammate_id=tm.id,
                message="Answer empty dict test",
                stream=False,
            )
            with pytest.raises(ValidationError):
                v2_client.runs.answer(run.id, answers={})
        finally:
            v2_client.teammates.delete(tm.id)

    def test_answer_on_terminal_run_conflict(self, v2_client):
        """Answer on a terminal run returns ConflictError (409)."""
        tm = v2_client.teammates.create(name="AnswerTerminal")
        try:
            run = v2_client.runs.create(
                teammate_id=tm.id,
                message="respond with ok",
                stream=False,
            )
            terminal = v2_client.runs.poll(run.id, interval=1.0, timeout=120.0)
            assert terminal.status in ("completed", "failed", "cancelled")
            with pytest.raises(ConflictError):
                v2_client.runs.answer(terminal.id, answers={"Q": "A"})
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

    def test_approve_invalid_decision_rejected(self, v2_client):
        """Invalid decision value is rejected by V2 schema validation."""
        tm = v2_client.teammates.create(name="ApproveInvalidDecision")
        try:
            run = v2_client.runs.create(
                teammate_id=tm.id,
                message="Approve invalid decision test",
                stream=False,
            )
            with pytest.raises(ValidationError):
                v2_client.runs.approve(run.id, request_id="req_fake", decision="maybe")
        finally:
            v2_client.teammates.delete(tm.id)


# ── Run Creation Edge Cases ──────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.runtime
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

    def test_create_run_with_model_override(self, v2_client):
        """Per-run model override is accepted (resolution happens server-side)."""
        tm = v2_client.teammates.create(name="ModelRunHost")
        try:
            run = v2_client.runs.create(
                teammate_id=tm.id,
                message="With model",
                stream=False,
                model="sonnet",
            )
            assert isinstance(run, Run)
            assert run.status == "running"
        finally:
            v2_client.teammates.delete(tm.id)

    def test_create_run_invalid_model_rejected(self, v2_client):
        """model outside sonnet|opus is rejected with 422."""
        tm = v2_client.teammates.create(name="BadModelRunHost")
        try:
            with pytest.raises(ValidationError):
                v2_client.runs.create(
                    teammate_id=tm.id, message="Bad model", stream=False, model="gpt-5"
                )
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
@pytest.mark.runtime
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
        """Cancel a running run returns a Run object.

        In test-mode servers, background runs complete instantly (FAILED status) before
        the cancel request arrives, which is a valid 409. Accept both outcomes.
        """
        from m8tes._exceptions import ConflictError

        tm = v2_client.teammates.create(name="CancelRunHost")
        try:
            run = v2_client.runs.create(
                teammate_id=tm.id,
                message="Cancel test",
                stream=False,
            )
            try:
                result = v2_client.runs.cancel(run.id)
                assert isinstance(result, Run)
            except ConflictError:
                # Run completed before cancel in test environments where execution is instant
                pass
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
@pytest.mark.runtime
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
@pytest.mark.runtime
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
@pytest.mark.runtime
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


@pytest.mark.integration
class TestAppsWritable:
    def test_connect_api_key_and_disconnect(self, v2_client):
        """API key apps can be connected and disconnected through explicit SDK helpers."""
        app = _require_api_key_app(v2_client)

        user_id = _uid()
        result = v2_client.apps.connect_api_key(app.name, "test-api-key", user_id=user_id)
        assert result.status == "connected"
        assert result.app == app.name

        connected_page = v2_client.apps.list(user_id=user_id)
        connected = next((item for item in connected_page.data if item.name == app.name), None)
        assert connected is not None
        assert connected.connected is True

        v2_client.apps.disconnect(app.name, user_id=user_id)

        disconnected_page = v2_client.apps.list(user_id=user_id)
        disconnected = next(
            (item for item in disconnected_page.data if item.name == app.name),
            None,
        )
        assert disconnected is not None
        assert disconnected.connected is False


@pytest.mark.integration
class TestAppsProvision:
    """Provision/release platform-managed resources (e.g. Twilio phone numbers)."""

    def test_provision_rejects_non_platform_app(self, v2_client):
        """provision() on a non-platform-provisioned app (an API-key app) is a 400."""
        app = _require_api_key_app(v2_client)
        with pytest.raises(ValidationError):
            v2_client.apps.provision(app.name)

    def test_provision_nonexistent_app(self, v2_client):
        """provision() on an unknown app is a 404."""
        with pytest.raises(NotFoundError):
            v2_client.apps.provision(f"missing-{uuid.uuid4().hex[:8]}")

    def test_provision_and_release_roundtrip(self, v2_client):
        """Full provision -> release happy path. Opt-in: buys a real phone number."""
        if os.getenv("E2E_TWILIO_PROVISION") != "1":
            pytest.skip(
                "Set E2E_TWILIO_PROVISION=1 to run live provisioning (buys a real Twilio number)"
            )
        app = next(
            (a for a in v2_client.apps.list().data if a.auth_type == "platform_provisioned"),
            None,
        )
        if app is None:
            pytest.skip("No platform_provisioned app in catalog")

        user_id = _uid()
        result = v2_client.apps.provision(app.name, user_id=user_id)
        try:
            assert result.status == "provisioned"
            assert result.app == app.name
            assert result.phone_number
            # The end-user now sees the app connected (strictly scoped to this user_id).
            page = v2_client.apps.list(user_id=user_id)
            connected = next((a for a in page.data if a.name == app.name), None)
            assert connected is not None and connected.connected is True
        finally:
            v2_client.apps.release(app.name, user_id=user_id)


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

    def test_run_inherits_scoped_teammate_user_id(self, v2_client):
        """Run should inherit the teammate user_id when omitted."""
        uid = _uid()
        tm = v2_client.teammates.create(name="ScopedRunHost", user_id=uid)
        try:
            run = v2_client.runs.create(teammate_id=tm.id, message="Test", stream=False)
            assert run.user_id == uid
        finally:
            v2_client.teammates.delete(tm.id)

    def test_run_rejects_mismatched_scoped_teammate_user_id(self, v2_client):
        """Run should reject a user_id that does not match a scoped teammate."""
        uid_a, uid_b = _uid(), _uid()
        tm = v2_client.teammates.create(name="ScopedMismatchRunHost", user_id=uid_a)
        try:
            with pytest.raises(NotFoundError):
                v2_client.runs.create(
                    teammate_id=tm.id,
                    message="Test",
                    stream=False,
                    user_id=uid_b,
                )
        finally:
            v2_client.teammates.delete(tm.id)

    def test_task_rejects_mismatched_scoped_teammate_user_id(self, v2_client):
        """Task creation should reject a user_id that does not match a scoped teammate."""
        uid_a, uid_b = _uid(), _uid()
        tm = v2_client.teammates.create(name="ScopedMismatchTaskHost", user_id=uid_a)
        try:
            with pytest.raises(NotFoundError):
                v2_client.tasks.create(
                    teammate_id=tm.id,
                    instructions="Do the thing",
                    user_id=uid_b,
                )
        finally:
            v2_client.teammates.delete(tm.id)

    def test_task_run_inherits_scoped_task_user_id(self, v2_client):
        """Saved-task runs should inherit the task scope when user_id is omitted."""
        uid = _uid()
        tm = v2_client.teammates.create(name="ScopedTaskRunHost", user_id=uid)
        try:
            task = v2_client.tasks.create(
                teammate_id=tm.id,
                instructions="Review the inbox",
            )
            try:
                run = v2_client.tasks.run(task.id, stream=False)
                assert run.user_id == uid
            finally:
                v2_client.tasks.delete(task.id)
        finally:
            v2_client.teammates.delete(tm.id)

    def test_task_run_rejects_mismatched_scoped_task_user_id(self, v2_client):
        """Saved-task runs should reject a user_id that does not match the task scope."""
        uid_a, uid_b = _uid(), _uid()
        tm = v2_client.teammates.create(name="ScopedTaskRunMismatchHost", user_id=uid_a)
        try:
            task = v2_client.tasks.create(
                teammate_id=tm.id,
                instructions="Review the inbox",
            )
            try:
                with pytest.raises(NotFoundError):
                    v2_client.tasks.run(task.id, stream=False, user_id=uid_b)
            finally:
                v2_client.tasks.delete(task.id)
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
    def test_empty_teammate_name_auto_generates(self, v2_client):
        """Empty teammate name falls back to the backend-generated default name."""
        teammate = v2_client.teammates.create(name="")
        try:
            assert teammate.name
            assert teammate.name.strip()
        finally:
            v2_client.teammates.delete(teammate.id)

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
            v2_client.memories.delete(mem.id, user_id=uid)
            v2_client.users.delete(uid)

    def test_end_user_usage_rollup(self, v2_client):
        """usage() returns a zero row for a fresh end-user, with period metadata."""
        uid = _uid()
        v2_client.users.create(user_id=uid)
        try:
            page = v2_client.users.usage(uid)
            assert len(page.data) == 1
            row = page.data[0]
            assert row.user_id == uid
            assert row.runs_used == 0
            assert row.cost_used == "0"
            assert row.total_tokens == 0
            assert row.last_active_at is None
            assert row.period_end  # period metadata always present
        finally:
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
        """Default settings: standard retention, no sub-caps."""
        settings = v2_client.settings.get()
        assert isinstance(settings, AccountSettings)
        assert settings.retention_mode == "standard"

    def test_per_end_user_sub_caps(self, v2_client):
        """Set, read back, and clear the per-end-user multi-tenant sub-caps."""
        # Default: no caps.
        assert v2_client.settings.get().per_end_user_run_limit is None

        # Set both caps.
        updated = v2_client.settings.update(
            per_end_user_run_limit=25, per_end_user_cost_limit_cents=500
        )
        assert updated.per_end_user_run_limit == 25
        assert updated.per_end_user_cost_limit_cents == 500
        assert v2_client.settings.get().per_end_user_run_limit == 25

        # Clear the run cap (explicit null); cost cap stays.
        cleared = v2_client.settings.update(per_end_user_run_limit=None)
        assert cleared.per_end_user_run_limit is None
        assert cleared.per_end_user_cost_limit_cents == 500

        # Cleanup.
        v2_client.settings.update(per_end_user_cost_limit_cents=None)

    def test_retention_mode(self, v2_client):
        """Toggle zero-data-retention on and back off."""
        assert v2_client.settings.get().retention_mode == "standard"
        assert v2_client.settings.update(retention_mode="metadata_only").retention_mode == (
            "metadata_only"
        )
        assert v2_client.settings.get().retention_mode == "metadata_only"
        # Restore.
        assert v2_client.settings.update(retention_mode="standard").retention_mode == "standard"


# ── Runs: SDK Convenience Methods ────────────────────────────────────


@pytest.mark.integration
@pytest.mark.runtime
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

    def test_create_and_wait_email_inbox(self, v2_client):
        """create_and_wait(email_inbox=True) returns a run with email_address set."""
        run = v2_client.runs.create_and_wait(
            message="say hello",
            instructions="you are a test assistant",
            email_inbox=True,
            poll_interval=1.0,
            poll_timeout=120.0,
        )
        try:
            assert isinstance(run, Run)
            assert run.email_address is not None
            assert "@" in run.email_address
        finally:
            if run.teammate_id:
                with contextlib.suppress(Exception):
                    v2_client.teammates.delete(run.teammate_id)

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
        from m8tes._streaming import RunStream
        from m8tes.streaming import DoneEvent, ErrorEvent, TextDeltaEvent

        tm = v2_client.teammates.create(name="StreamTextHost")
        try:
            with v2_client.runs.create(
                teammate_id=tm.id,
                message="Say the word 'hello'",
                stream=True,
            ) as stream:
                assert isinstance(stream, RunStream)
                events = list(stream)
                assert len(events) > 0, "Stream had zero events"

                # Skip if no text produced (fake API key in CI, CLI not installed, or auth error)
                has_text = any(isinstance(e, TextDeltaEvent) for e in events)
                has_terminal = any(isinstance(e, DoneEvent | ErrorEvent) for e in events)
                if not has_text and has_terminal:
                    pytest.skip("Claude produced no text — likely CI with fake API key")

                event_types = [e.type for e in events]
                text_delta_count = sum(1 for e in events if isinstance(e, TextDeltaEvent))
                assert text_delta_count > 0, (
                    f"No TextDeltaEvent in stream. Got {len(events)} events: {event_types}"
                )

            chunks = list(
                v2_client.runs.stream_text(
                    teammate_id=tm.id,
                    message="Say the word 'banana'",
                )
            )
            assert len(chunks) > 0, "stream_text yielded 0 chunks"
            full_text = "".join(chunks)
            assert len(full_text) > 0, f"stream_text chunks were all empty: {chunks!r}"
        finally:
            v2_client.teammates.delete(tm.id)

    def test_update_permission_mode(self, v2_client):
        """update_permission_mode() switches a run into approval mode."""
        tm = v2_client.teammates.create(name="ModeSwitchHost")
        try:
            run = v2_client.runs.create(
                teammate_id=tm.id,
                message="Switch modes",
                stream=False,
            )
            result = v2_client.runs.update_permission_mode(run.id, permission_mode="approval")
            assert result.permission_mode == "approval"
        finally:
            with contextlib.suppress(ConflictError, UnboundLocalError):
                v2_client.runs.cancel(run.id)
            v2_client.teammates.delete(tm.id)

    def test_update_permission_mode_auto_approves_pending_tool_request(self, v2_client):
        """SDK mode switch auto-approves an outstanding tool permission request."""
        import requests

        tm = v2_client.teammates.create(name="ModeSwitchAutoApproveHost")
        try:
            run = v2_client.runs.create(
                teammate_id=tm.id,
                message="Switch modes",
                stream=False,
            )

            backend_url = v2_client._http._base_url.rsplit("/api/v2", 1)[0]
            resp = requests.post(
                f"{backend_url}/api/v1/runs/{run.id}/permission-request",
                headers={"Authorization": v2_client._http._session.headers["Authorization"]},
                json={"tool_name": "gmail_send", "tool_input": {"to": "user@example.com"}},
                timeout=30,
            )
            assert resp.status_code == 200, resp.text

            result = v2_client.runs.update_permission_mode(run.id, permission_mode="autonomous")
            assert result.permission_mode == "autonomous"

            permissions = v2_client.runs.permissions(run.id)
            request_id = resp.json()["request_id"]
            request = next(req for req in permissions if req.request_id == request_id)
            assert request.status == "allowed"
        finally:
            with contextlib.suppress(ConflictError, UnboundLocalError):
                v2_client.runs.cancel(run.id)
            v2_client.teammates.delete(tm.id)


# ── Runs: Parameter Combinations ────────────────────────────────────


@pytest.mark.integration
@pytest.mark.runtime
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

    def test_approve_no_pending_request_returns_404(self, v2_client):
        """approve() on a real run with no pending permission request → 404 regardless of decision.

        Consolidates deny + remember=True into one run to reduce background task pressure in CI.
        """
        tm = v2_client.teammates.create(name="ApproveNoPendingHost")
        try:
            run = v2_client.runs.create(
                teammate_id=tm.id,
                message="approve edge case test",
                stream=False,
            )
            # Cancel immediately so the background task terminates and doesn't saturate CI.
            # Ignore ConflictError: in production the run may complete before we cancel.
            try:  # noqa: SIM105
                v2_client.runs.cancel(run.id)
            except ConflictError:
                pass
            # Wait for the background task to terminate before calling approve().
            # Without this, the task (retrying the fake Anthropic key) holds a SQLite
            # write lock, causing approve()'s DB queries to hang until SDK timeout fires.
            v2_client.runs.poll(run.id, interval=1.0, timeout=15.0)
            with pytest.raises(NotFoundError):
                v2_client.runs.approve(run.id, request_id="fake-uuid", decision="deny")
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


# ── Auth Endpoints ───────────────────────────────────────────────────


@pytest.mark.integration
class TestAuthEndpoints:
    """Integration tests for the V2 auth endpoints: signup, token, verify, usage.

    These use raw requests (not the SDK client) — the auth endpoints are used to
    bootstrap accounts before the SDK client exists.
    """

    def test_signup_creates_account_and_returns_key(self, backend_url):
        """POST /api/v2/signup returns 201 with api_key, email, and message."""
        import requests

        email = f"signup-{uuid.uuid4().hex[:8]}@test.m8tes.ai"
        resp = requests.post(
            f"{backend_url}/api/v2/signup",
            json={"email": email, "password": "TestPassword123!", "first_name": "SDKTest"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["api_key"].startswith("m8_")
        assert data["email"] == email
        assert "message" in data

    def test_signup_returns_pending_verification_without_link(self, backend_url):
        """Signup reports verification='pending' and never returns an activation/login link."""
        import requests

        email = f"signup-pending-{uuid.uuid4().hex[:8]}@test.m8tes.ai"
        resp = requests.post(
            f"{backend_url}/api/v2/signup",
            json={"email": email, "password": "TestPassword123!", "first_name": "SDKTest"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["verification"] == "pending"
        # Security: the activation link is emailed to the user, never returned to the caller.
        assert "http" not in data["message"].lower()
        assert "token" not in data

    def test_sdk_signup_exposes_verification_and_is_verified_poll(self, backend_url):
        """SDK signup() carries verification status; client.auth.is_verified() polls it."""
        from m8tes import M8tes, signup

        email = f"sdk-signup-{uuid.uuid4().hex[:8]}@test.m8tes.ai"
        result = signup(
            email=email,
            password="TestPassword123!",
            first_name="SDKTest",
            base_url=f"{backend_url}/api/v2",
        )
        assert result.api_key.startswith("m8_")
        assert result.verification == "pending"

        client = M8tes(api_key=result.api_key, base_url=f"{backend_url}/api/v2")
        assert client.auth.is_verified() is False  # fresh account, user hasn't clicked yet

    def test_signup_key_is_usable_immediately(self, backend_url):
        """API key from signup works on authenticated V2 endpoints."""
        import requests

        email = f"signup-use-{uuid.uuid4().hex[:8]}@test.m8tes.ai"
        api_key = requests.post(
            f"{backend_url}/api/v2/signup",
            json={"email": email, "password": "TestPassword123!", "first_name": "SDKTest"},
        ).json()["api_key"]

        resp = requests.get(
            f"{backend_url}/api/v2/teammates",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert resp.status_code == 200

    def test_signup_duplicate_email_returns_409(self, backend_url):
        """Second signup with the same email returns 409 Conflict."""
        import requests

        email = f"dup-{uuid.uuid4().hex[:8]}@test.m8tes.ai"
        payload = {"email": email, "password": "TestPassword123!", "first_name": "SDKTest"}
        requests.post(f"{backend_url}/api/v2/signup", json=payload)
        resp = requests.post(f"{backend_url}/api/v2/signup", json=payload)
        assert resp.status_code == 409

    def test_token_exchanges_credentials_for_key(self, backend_url):
        """POST /api/v2/token with valid credentials returns a working API key."""
        import requests

        email = f"token-{uuid.uuid4().hex[:8]}@test.m8tes.ai"
        password = "TestPassword123!"
        # Create account first (via V1 register which is known-stable)
        requests.post(
            f"{backend_url}/api/v1/auth/register",
            json={"email": email, "password": password, "first_name": "SDKTest"},
        )
        resp = requests.post(
            f"{backend_url}/api/v2/token",
            json={"email": email, "password": password},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["api_key"].startswith("m8_")
        assert data["email"] == email

        # New key works immediately
        usage = requests.get(
            f"{backend_url}/api/v2/usage",
            headers={"Authorization": f"Bearer {data['api_key']}"},
        )
        assert usage.status_code == 200

    def test_token_wrong_password_returns_401(self, backend_url):
        """Wrong password returns 401 with generic error (no user enumeration)."""
        import requests

        resp = requests.post(
            f"{backend_url}/api/v2/token",
            json={"email": "nobody@test.m8tes.ai", "password": "wrong"},
        )
        assert resp.status_code == 401

    def test_verify_resend_returns_200(self, backend_url):
        """POST /api/v2/verify/resend with valid API key returns 200."""
        import requests

        email = f"verify-{uuid.uuid4().hex[:8]}@test.m8tes.ai"
        api_key = requests.post(
            f"{backend_url}/api/v1/auth/register",
            json={"email": email, "password": "TestPassword123!", "first_name": "SDKTest"},
        ).json()["api_key"]

        resp = requests.post(
            f"{backend_url}/api/v2/verify/resend",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Verification email sent."

    def test_verify_resend_without_auth_returns_401(self, backend_url):
        """POST /api/v2/verify/resend without auth returns 401."""
        import requests

        resp = requests.post(f"{backend_url}/api/v2/verify/resend")
        assert resp.status_code == 401

    def test_usage_returns_plan_and_limits(self, backend_url):
        """GET /api/v2/usage returns plan, run counts, costs, and period_end."""
        import requests

        email = f"usage-{uuid.uuid4().hex[:8]}@test.m8tes.ai"
        signup = requests.post(
            f"{backend_url}/api/v1/auth/register",
            json={"email": email, "password": "TestPassword123!", "first_name": "SDKTest"},
        )
        if signup.status_code == 429:
            # The suite's cumulative signups can trip the register IP rate limit —
            # environmental, not a product failure (died as KeyError before 2026-07-13).
            pytest.skip("register IP rate limit hit — rerun after the window resets")
        assert signup.status_code in (200, 201), signup.text[:200]
        api_key = signup.json()["api_key"]

        resp = requests.get(
            f"{backend_url}/api/v2/usage",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # New signups default to the time-boxed trial plan (free was removed).
        assert data["plan"] == "trial"
        assert isinstance(data["runs_used"], int)
        assert data["runs_limit"] == 5
        assert "cost_used" in data
        assert "cost_limit" in data
        assert "period_end" in data
        assert "subscription_status" in data
        # Overage read fields are present on the usage payload.
        assert "overage_enabled" in data
        assert "overage_rate_cents" in data

    def test_usage_without_auth_returns_401(self, backend_url):
        """GET /api/v2/usage without auth returns 401."""
        import requests

        resp = requests.get(f"{backend_url}/api/v2/usage")
        assert resp.status_code == 401


# ── Auth SDK ─────────────────────────────────────────────────────────


@pytest.mark.integration
class TestAuthSDK:
    """Tests for SDK-level auth helpers: signup(), get_token(), client.auth.*"""

    def test_signup_returns_signup_result(self, backend_url):
        import m8tes

        email = f"sdk-signup-{uuid.uuid4().hex[:8]}@test.m8tes.ai"
        result = m8tes.signup(
            email=email,
            password="TestPassword123!",
            first_name="SDK",
            base_url=f"{backend_url}/api/v2",
        )
        assert isinstance(result, m8tes.SignupResult)
        assert result.api_key.startswith("m8_")
        assert result.email == email
        assert result.message

    def test_signup_conflict_on_duplicate(self, backend_url):
        import m8tes

        email = f"sdk-dup-{uuid.uuid4().hex[:8]}@test.m8tes.ai"
        m8tes.signup(
            email=email,
            password="TestPassword123!",
            first_name="Dup",
            base_url=f"{backend_url}/api/v2",
        )
        with pytest.raises(ConflictError):
            m8tes.signup(
                email=email,
                password="TestPassword123!",
                first_name="Dup",
                base_url=f"{backend_url}/api/v2",
            )

    def test_get_token_returns_token_result(self, backend_url):
        import m8tes

        email = f"sdk-tok-{uuid.uuid4().hex[:8]}@test.m8tes.ai"
        password = "TestPassword123!"
        m8tes.signup(
            email=email, password=password, first_name="Tok", base_url=f"{backend_url}/api/v2"
        )
        result = m8tes.get_token(email=email, password=password, base_url=f"{backend_url}/api/v2")
        assert isinstance(result, m8tes.TokenResult)
        assert result.api_key.startswith("m8_")
        assert result.email == email

    def test_get_token_wrong_creds_raises_authentication_error(self, backend_url):
        import m8tes

        with pytest.raises(AuthenticationError):
            m8tes.get_token(
                email="nobody@test.m8tes.ai", password="wrong", base_url=f"{backend_url}/api/v2"
            )

    def test_get_usage_returns_usage(self, v2_client):
        from m8tes._types import Usage

        usage = v2_client.auth.get_usage()
        assert isinstance(usage, Usage)
        # New signups land on the time-boxed trial plan (free is retired).
        assert usage.plan in ("trial", "pro", "max_5x", "max_20x", "inactive")
        assert usage.runs_used >= 0
        assert usage.runs_limit > 0
        assert usage.cost_used
        assert usage.cost_limit
        assert usage.period_end

    def test_resend_verify_returns_message(self, v2_client):
        msg = v2_client.auth.resend_verify()
        assert isinstance(msg, str)
        assert msg


@pytest.mark.integration
class TestV2Billing:
    """client.billing — usage overage fields, plan catalog, and set_overage."""

    def test_usage_carries_overage_fields(self, v2_client):
        from m8tes._types import Usage

        usage = v2_client.billing.usage()
        assert isinstance(usage, Usage)
        # Overage fields are present with safe defaults (off by default).
        assert isinstance(usage.overage_enabled, bool)
        assert isinstance(usage.overage_used_cents, int)
        assert isinstance(usage.overage_cap_cents, int)
        assert usage.overage_rate_cents == 1000  # platform $10/run rate

    def test_plans_returns_catalog(self, v2_client):
        from m8tes._types import Plan

        plans = v2_client.billing.plans()
        assert all(isinstance(p, Plan) for p in plans)
        slugs = {p.slug for p in plans}
        assert {"pro", "max_5x", "max_20x"} <= slugs
        pro = next(p for p in plans if p.slug == "pro")
        assert pro.display_name == "Pro"
        assert pro.included_runs == 100
        assert pro.annual_price_cents == pro.monthly_price_cents * 10

    def test_enable_overage_without_subscription_is_rejected(self, v2_client):
        # Overage can only be enabled on an account that carries the metered Stripe
        # subscription item; the integration user has none, so enabling 402s
        # (OVERAGE_UNAVAILABLE) instead of silently accruing cents nothing can bill.
        with pytest.raises(BillingError) as exc:
            v2_client.billing.set_overage(enabled=True, monthly_cap_cents=2500)
        assert exc.value.status_code == 402

        # Disabling is always allowed (and round-trips) regardless of subscription.
        disabled = v2_client.billing.set_overage(enabled=False, monthly_cap_cents=2500)
        assert disabled.overage_enabled is False

    def test_set_overage_rejects_cap_over_max(self, v2_client):
        with pytest.raises(ValidationError):
            v2_client.billing.set_overage(enabled=True, monthly_cap_cents=10_000_01)

    def test_balance_returns_prepaid_state(self, v2_client):
        from m8tes._types import Balance

        balance = v2_client.billing.balance()
        assert isinstance(balance, Balance)
        assert isinstance(balance.balance_micros, int)
        assert balance.currency == "usd"
        assert isinstance(balance.transactions, list)
        assert isinstance(balance.low_balance_threshold_micros, int)
        assert isinstance(balance.critical_balance_threshold_micros, int)

    def test_topup_rejects_below_minimum(self, v2_client):
        # The $5 minimum is enforced server-side before any Stripe call.
        with pytest.raises(ValidationError):
            v2_client.billing.topup(amount_cents=100)

    def test_set_alert_threshold_rejects_over_max(self, v2_client):
        # The $100k ceiling on the low-balance warning threshold is enforced server-side.
        with pytest.raises(ValidationError):
            v2_client.billing.set_alert_threshold(low_balance_threshold_cents=100_000_01)

    def test_usage_timeseries_default_window(self, v2_client):
        from m8tes._types import UsageBucket, UsageTimeseries

        series = v2_client.billing.usage_timeseries()
        assert isinstance(series, UsageTimeseries)
        assert len(series.buckets) == 30  # default: last 30 UTC days, zero-filled
        assert all(isinstance(b, UsageBucket) for b in series.buckets)
        assert series.buckets[-1].date == series.end_date
        # Totals reconcile with the buckets.
        assert series.totals.total_tokens == sum(b.total_tokens for b in series.buckets)

    def test_usage_timeseries_rejects_inverted_range(self, v2_client):
        with pytest.raises(ValidationError):
            v2_client.billing.usage_timeseries(start_date="2026-07-02", end_date="2026-07-01")

    def test_usage_timeseries_filters_accepted(self, v2_client):
        series = v2_client.billing.usage_timeseries(
            start_date="2026-07-01", end_date="2026-07-03", user_id="nonexistent-euid"
        )
        assert len(series.buckets) == 3
        assert series.totals.total_tokens == 0  # unknown end-user → strictly empty

    def test_usage_timeseries_group_by_model(self, v2_client):
        series = v2_client.billing.usage_timeseries(
            start_date="2026-07-01", end_date="2026-07-02", group_by="model"
        )
        assert all(b.models is not None for b in series.buckets)  # [] on empty days
        with pytest.raises(ValidationError):
            v2_client.billing.usage_timeseries(group_by="teammate")

    def test_receipts_lists_empty_for_fresh_account(self, v2_client):
        page = v2_client.billing.receipts()
        assert isinstance(page.data, list)
        assert isinstance(page.has_more, bool)

    def test_balance_carries_auto_reload_fields(self, v2_client):
        bal = v2_client.billing.balance()
        assert bal.auto_reload_enabled is False  # off by default
        assert bal.auto_reload_threshold_cents is None

    def test_set_auto_reload_rejected_for_tiers_account(self, v2_client):
        # The integration account bills via tiers — auto-reload is prepaid-only (403).
        from m8tes._exceptions import PermissionDeniedError

        with pytest.raises(PermissionDeniedError):
            v2_client.billing.set_auto_reload(enabled=True, threshold_cents=500, amount_cents=2000)

    def test_set_auto_reload_requires_amounts_to_enable(self, v2_client):
        with pytest.raises(ValidationError):
            v2_client.billing.set_auto_reload(enabled=True)


@pytest.mark.integration
@pytest.mark.runtime
class TestRunUsageField:
    """DevRunResponse.usage parses through the SDK on real run responses."""

    def test_run_carries_usage_field(self, v2_client):
        """The `usage` key must be PRESENT on every run response (null until metrics
        arrive) — asserted on the raw payload, since `usage is None` alone would also
        pass if the field were dropped entirely."""
        tm = v2_client.teammates.create(name="UsageField")
        try:
            run = v2_client.runs.create(teammate_id=tm.id, message="ping", stream=False)
            raw = v2_client._http.request("GET", f"/runs/{run.id}").json()
            assert "usage" in raw  # falsifiable: fails if the field is dropped
            fetched = v2_client.runs.get(run.id)
            if fetched.usage is not None:
                assert fetched.usage.total_tokens >= 0
                assert fetched.usage.cost_usd is not None
            with contextlib.suppress(Exception):
                v2_client.runs.cancel(run.id)
        finally:
            v2_client.teammates.delete(tm.id)


@pytest.mark.integration
class TestTeammateTemplates:
    """Verticalized teammate templates: from_template enable + reset.

    Requires a backend with the ppc-manager template registered and the
    Google Ads AppIntegration seeded. The happy path also requires the test
    user to have a connected Google Ads Integration row — when absent the
    backend returns 400 missing_integration, which we assert as a fall-through
    path. The unknown-slug and conflict tests don't depend on integrations.
    """

    def test_from_template_unknown_slug_raises_not_found(self, v2_client):
        with pytest.raises(NotFoundError):
            v2_client.teammates.create(from_template="no-such-template-zzz")

    def test_from_template_conflicting_fields_raises_validation(self, v2_client):
        # tools + from_template should be rejected with 400 from_template_conflict.
        # Backend returns 400 which the SDK maps to ValidationError.
        with pytest.raises(ValidationError):
            v2_client.teammates.create(
                from_template="ppc-manager",
                tools=["gmail"],
                instructions="custom override should be rejected",
            )

    def test_from_template_missing_integration_or_happy_path(self, v2_client):
        """Either creates the teammate (Google Ads connected) or 400s
        with missing_integration. Both are valid backend states for this
        integration test."""
        try:
            teammate = v2_client.teammates.create(from_template="ppc-manager")
        except ValidationError as e:
            # Without a connected Google Ads integration we get a 400 with
            # missing_integration error code. The teammate is NOT created.
            assert e.status_code == 400
            return

        try:
            assert teammate.name == "Google Ads"
            assert "google_ads" in (teammate.tools or [])
            # Reset on a freshly enabled teammate with no customizations is
            # a no-op — returns empty list.
            reset_fields = v2_client.teammates.reset(teammate.id)
            assert reset_fields == []

            # Customize a field, then reset it.
            v2_client.teammates.update(
                teammate.id,
                instructions="my custom prompt that overrides the template",
            )
            cleared = v2_client.teammates.reset(teammate.id, fields=["instructions"])
            assert "instructions" in cleared

            # After reset, the next GET should show the template's default
            # back in place of the override.
            refreshed = v2_client.teammates.get(teammate.id)
            assert "my custom prompt" not in (refreshed.instructions or "")
        finally:
            v2_client.teammates.delete(teammate.id)

    def test_reset_unlinked_teammate_returns_empty_list(self, v2_client):
        """Custom (non-templated) teammate has no overrides — reset is a no-op."""
        teammate = v2_client.teammates.create(name="Custom mate for reset test")
        try:
            cleared = v2_client.teammates.reset(teammate.id, fields=["instructions"])
            assert cleared == []
        finally:
            v2_client.teammates.delete(teammate.id)


class TestTeammateTemplateCatalog:
    """client.teammate_templates.list() — the discovery surface for from_template."""

    def test_list_returns_typed_templates(self, v2_client):
        tpls = v2_client.teammate_templates.list()
        assert isinstance(tpls, list) and tpls, "catalog should be non-empty"
        slugs = {t.slug for t in tpls}
        assert "ppc-manager" in slugs
        ppc = next(t for t in tpls if t.slug == "ppc-manager")
        assert ppc.name and ppc.required_integrations

    def test_listed_slug_is_recognized_by_create(self, v2_client):
        """A catalog slug round-trips into teammates.create(from_template=).

        Pass ONLY from_template (no other fields) so we don't trip the
        from_template_conflict 400 — that would make the test pass for the wrong
        reason. With just the slug, create either succeeds or 400s on a missing
        required integration; both prove the slug was recognized (an *unknown*
        slug 404s instead).
        """
        slug = v2_client.teammate_templates.list()[0].slug
        try:
            mate = v2_client.teammates.create(from_template=slug)
        except ValidationError as e:
            assert e.status_code == 400  # missing integration — slug WAS recognized
            return
        try:
            assert mate.id
        finally:
            v2_client.teammates.delete(mate.id)


class TestTaskLessons:
    """client.tasks lesson curation: view, delete, clear."""

    def test_lessons_view_and_clear(self, v2_client):
        mate = v2_client.teammates.create(name="LessonsHost")
        task = v2_client.tasks.create(teammate_id=mate.id, instructions="do the thing")
        try:
            ll = v2_client.tasks.lessons(task.id)
            assert ll.capacity_limit > 0
            assert ll.capacity_used == 0
            assert ll.data == []
            # clear is safe (idempotent) on a task with no lessons
            cleared = v2_client.tasks.clear_lessons(task.id)
            assert cleared.capacity_used == 0
        finally:
            v2_client.tasks.delete(task.id)
            v2_client.teammates.delete(mate.id)


@pytest.mark.integration
class TestMcpServersCRUD:
    """client.mcp_servers — custom-tool server CRUD, write-only secret, slug attach, scope."""

    def test_full_lifecycle(self, v2_client):
        """create -> list -> get -> update (clear/preserve secret) -> delete -> gone."""
        srv = v2_client.mcp_servers.create(
            name="acme billing",
            url="https://example.com/v1",
            auth_type="bearer",
            secret="sk-integ-secret",
            tool_defs=[{"name": "get_invoice", "method": "GET", "path": "/invoices/{id}"}],
        )
        try:
            assert isinstance(srv, McpServer)
            assert srv.id is not None
            assert srv.slug == "acme-billing"
            assert srv.has_secret is True
            assert not hasattr(srv, "secret")  # write-only, never returned

            assert any(s.id == srv.id for s in v2_client.mcp_servers.list())
            assert v2_client.mcp_servers.get(srv.id).name == "acme billing"

            # secret=None clears the stored secret (the _UNSET sentinel distinguishes this
            # from omission)...
            assert v2_client.mcp_servers.update(srv.id, secret=None).has_secret is False
            # ...and omitting secret preserves it across an unrelated patch.
            v2_client.mcp_servers.update(srv.id, secret="sk-again")
            renamed = v2_client.mcp_servers.update(srv.id, name="acme v2")
            assert renamed.name == "acme v2"
            assert renamed.has_secret is True
            assert renamed.slug == "acme-billing"  # slug stable across rename

            # auto_approve ("trusted" → runs unattended): defaults off, toggles via update
            assert srv.auto_approve is False
            assert v2_client.mcp_servers.update(srv.id, auto_approve=True).auto_approve is True
        finally:
            v2_client.mcp_servers.delete(srv.id)
        assert all(s.id != srv.id for s in v2_client.mcp_servers.list())

    def test_attach_to_teammate_by_slug(self, v2_client):
        srv = v2_client.mcp_servers.create(
            name="crm sync",
            url="https://example.com/v1",
            tool_defs=[{"name": "lookup", "method": "GET", "path": "/lookup"}],
        )
        mate = None
        try:
            mate = v2_client.teammates.create(name="CrmBot", tools=[srv.slug])
            assert srv.slug in mate.tools  # custom slug rides the by-name tools=[...] array
        finally:
            if mate:
                v2_client.teammates.delete(mate.id)
            v2_client.mcp_servers.delete(srv.id)

    def test_end_user_scope_isolation(self, v2_client):
        uid = _uid()
        scoped = v2_client.mcp_servers.create(
            name="scoped",
            url="https://example.com/v1",
            tool_defs=[{"name": "x", "method": "GET", "path": "/x"}],
            user_id=uid,
        )
        try:
            assert v2_client.mcp_servers.get(scoped.id, user_id=uid).id == scoped.id
            # account-level list/get must NOT reach the end-user-scoped row
            assert all(s.id != scoped.id for s in v2_client.mcp_servers.list())
            with pytest.raises(NotFoundError):
                v2_client.mcp_servers.get(scoped.id)
            assert any(s.id == scoped.id for s in v2_client.mcp_servers.list(user_id=uid))
        finally:
            v2_client.mcp_servers.delete(scoped.id, user_id=uid)

    def test_cross_account_isolation(self, v2_client, backend_url):
        srv = v2_client.mcp_servers.create(
            name="private",
            url="https://example.com/v1",
            tool_defs=[{"name": "x", "method": "GET", "path": "/x"}],
        )
        try:
            other = _new_v2_client(backend_url, email_prefix="mcp-cross")
            with pytest.raises(NotFoundError):
                other.mcp_servers.get(srv.id)
        finally:
            v2_client.mcp_servers.delete(srv.id)

    def test_custom_header_requires_config(self, v2_client):
        """auth_config is validated at create — a custom_header server needs header_name."""
        with pytest.raises(ValidationError):
            v2_client.mcp_servers.create(
                name="bad auth",
                url="https://example.com/v1",
                auth_type="custom_header",
                tool_defs=[{"name": "x", "method": "GET", "path": "/x"}],
            )


@pytest.mark.integration
class TestSkillsCRUD:
    """client.skills — Agent Skill CRUD, account/teammate scope, end-user isolation.

    Requires the backend to run with custom_skills_enabled=True (same as mcp_servers).
    """

    def test_full_lifecycle(self, v2_client):
        skill = v2_client.skills.create(
            name="acme refund playbook",
            description="How to process an Acme refund end-to-end.",
            body="# Steps\n1. Pull the order\n2. Issue the refund",
        )
        try:
            assert isinstance(skill, Skill)
            assert skill.slug == "acme-refund-playbook"
            assert skill.scope == "account"
            assert skill.source == "user"

            assert any(s.id == skill.id for s in v2_client.skills.list())
            assert v2_client.skills.get(skill.id).name == "acme refund playbook"

            disabled = v2_client.skills.update(skill.id, status="disabled", name="acme v2")
            assert disabled.status == "disabled"
            assert disabled.name == "acme v2"
            assert disabled.slug == "acme-refund-playbook"  # slug stable across rename
        finally:
            v2_client.skills.delete(skill.id)
        assert all(s.id != skill.id for s in v2_client.skills.list())

    def test_teammate_scope(self, v2_client):
        mate = v2_client.teammates.create(name="SkillBot")
        try:
            skill = v2_client.skills.create(
                name="bot playbook",
                description="bot-only steps",
                body="# do",
                scope="teammate",
                teammate_id=mate.id,
            )
            assert skill.scope == "teammate"
            assert skill.teammate_id == mate.id
            v2_client.skills.delete(skill.id)
        finally:
            v2_client.teammates.delete(mate.id)

    def test_end_user_scope_isolation(self, v2_client):
        uid = _uid()
        scoped = v2_client.skills.create(
            name="scoped",
            description="d",
            body="b",
            user_id=uid,
        )
        try:
            assert v2_client.skills.get(scoped.id, user_id=uid).id == scoped.id
            assert all(s.id != scoped.id for s in v2_client.skills.list())
            with pytest.raises(NotFoundError):
                v2_client.skills.get(scoped.id)
            assert any(s.id == scoped.id for s in v2_client.skills.list(user_id=uid))
        finally:
            v2_client.skills.delete(scoped.id, user_id=uid)

    def test_cross_account_isolation(self, v2_client, backend_url):
        skill = v2_client.skills.create(name="private", description="d", body="b")
        try:
            other = _new_v2_client(backend_url, email_prefix="skills-cross")
            with pytest.raises(NotFoundError):
                other.skills.get(skill.id)
        finally:
            v2_client.skills.delete(skill.id)


@pytest.mark.integration
class TestKeysCRUD:
    def test_rotate_then_revoke(self, v2_client, backend_url):
        """Rotate yields a working API key; revoke makes it stop authenticating."""
        from m8tes import M8tes
        from m8tes._exceptions import AuthenticationError

        rotated = v2_client.keys.rotate()
        assert rotated.api_key.startswith("m8_")
        assert rotated.prefix == rotated.api_key[:12]

        # The rotated key authenticates the API-key path end to end.
        keyed = M8tes(api_key=rotated.api_key, base_url=f"{backend_url}/api/v2", timeout=30)
        try:
            info = keyed.keys.info()
            assert info.has_key is True
            assert info.prefix == rotated.prefix

            # Revoke (via the JWT-authed session client) kills the rotated key.
            assert v2_client.keys.revoke().has_key is False
            with pytest.raises(AuthenticationError):
                keyed.keys.info()
        finally:
            keyed.close()

    def test_named_key_lifecycle(self, v2_client, backend_url):
        """A named key authenticates, lists, rotates in place, and revokes — all by id,
        independently of the account's default key."""
        from m8tes import M8tes
        from m8tes._exceptions import AuthenticationError

        created = v2_client.keys.create(name="production", expires_in_days=30)
        assert created.api_key.startswith("m8_")
        assert created.name == "production"
        assert created.expires_at is not None

        keyed = M8tes(api_key=created.api_key, base_url=f"{backend_url}/api/v2", timeout=30)
        try:
            # The named key authenticates the API-key path end to end, and the account's
            # key list (fetched WITH that named key) includes it. We assert auth via
            # list() not info() — info() reports the legacy *default* key, not this one.
            listed = keyed.keys.list()
            assert any(k.id == created.id and k.name == "production" and k.active for k in listed)

            # Rotate in place: same id, fresh secret, old secret dies.
            rotated = v2_client.keys.rotate(created.id)
            assert rotated.id == created.id
            assert rotated.api_key != created.api_key
            with pytest.raises(AuthenticationError):
                keyed.keys.list()

            # Revoke by id: the rotated secret stops authenticating too.
            revoked = v2_client.keys.revoke(created.id)
            assert revoked.id == created.id
            assert revoked.active is False
            rekeyed = M8tes(api_key=rotated.api_key, base_url=f"{backend_url}/api/v2", timeout=30)
            try:
                with pytest.raises(AuthenticationError):
                    rekeyed.keys.list()
            finally:
                rekeyed.close()
        finally:
            keyed.close()


@pytest.mark.integration
class TestModels:
    """client.models — discover selectable models + prices."""

    def test_list_models(self, v2_client):
        page = v2_client.models.list()
        assert isinstance(page, SyncPage)
        models = {m.id: m for m in page.data}
        # Publicly selectable set (not the internal-only gpt-4o).
        assert set(models) == {"sonnet", "fable", "opus", "gpt-5.5", "glm-5.2", "deepseek-v3-2"}
        assert isinstance(models["opus"], Model)
        assert models["opus"].default is True
        assert models["sonnet"].default is False
        assert models["opus"].provider == "anthropic"
        # Pricing is populated with real USD-per-MTok numbers (incl. both cache rates).
        p = models["opus"].pricing
        assert p is not None
        assert p.input_per_mtok > 0 and p.output_per_mtok > 0
        assert p.cache_read_per_mtok > 0 and p.cache_write_per_mtok > 0
        assert p.currency == "usd"
        # A returned id is accepted as `model` on a teammate (round-trips, no 422).
        t = v2_client.teammates.create(name="ModelPick", model=models["sonnet"].id)
        try:
            assert t.model == "sonnet"
        finally:
            v2_client.teammates.delete(t.id)


class TestBuiltInTools:
    """client.built_in_tools discovery + teammate/task enable_* defaults."""

    def test_list_catalog(self, v2_client):
        page = v2_client.built_in_tools.list()
        assert isinstance(page, SyncPage)
        tools = {t.name: t for t in page.data}
        assert isinstance(tools["memory"], BuiltInTool)
        # The four configurable toggles are present and flagged configurable.
        for name in ("memory", "history", "task_setup_tools", "feedback"):
            assert tools[name].configurable is True
        # First-party-only tools are flagged not multi-tenant safe.
        assert tools["notify"].multi_tenant_safe is False

    def test_teammate_default_reflected_in_discovery(self, v2_client):
        t = v2_client.teammates.create(name="ToggleBot", enable_feedback=False)
        try:
            assert t.enable_feedback is False
            tools = {x.name: x for x in v2_client.built_in_tools.list(teammate_id=t.id).data}
            assert tools["feedback"].enabled is False
            assert tools["memory"].enabled is True
            # Reset to inherit, then verify it's back to the platform default.
            reset = v2_client.teammates.update(t.id, enable_feedback=None)
            assert reset.enable_feedback is None
        finally:
            v2_client.teammates.delete(t.id)

    def test_user_id_scope_hides_first_party_only(self, v2_client):
        tools = {x.name: x for x in v2_client.built_in_tools.list(user_id=_uid()).data}
        assert tools["notify"].enabled is False
        assert tools["memory"].enabled is True

    def test_task_default_round_trips(self, v2_client):
        t = v2_client.teammates.create(name="TaskToggleBot")
        try:
            task = v2_client.tasks.create(
                teammate_id=t.id, instructions="weekly summary", enable_history=False
            )
            assert task.enable_history is False
            assert task.enable_memory is None
            fetched = v2_client.tasks.get(task.id)
            assert fetched.enable_history is False
        finally:
            v2_client.teammates.delete(t.id)


@pytest.mark.integration
class TestSlackInboundAndLessons:
    """Slack inbound enablement + Task.enable_lessons + tasks.update reset."""

    def test_slack_handle_round_trips(self, v2_client):
        t = v2_client.teammates.create(
            name="SlackBot", inbound_slack_enabled=True, slack_slug=f"ppc{uuid.uuid4().hex[:6]}"
        )
        try:
            assert t.inbound_slack_enabled is True
            assert t.slack_slug.startswith("ppc")
            fetched = v2_client.teammates.get(t.id)
            assert fetched.inbound_slack_enabled is True
        finally:
            v2_client.teammates.delete(t.id)

    def test_enable_slack_without_handle_rejected(self, v2_client):
        from m8tes._exceptions import ValidationError

        with pytest.raises(ValidationError):
            v2_client.teammates.create(name="NoHandle", inbound_slack_enabled=True)

    def test_task_enable_lessons_round_trips(self, v2_client):
        t = v2_client.teammates.create(name="LessonBot")
        try:
            task = v2_client.tasks.create(
                teammate_id=t.id, instructions="weekly", enable_lessons=False
            )
            assert task.enable_lessons is False
            assert v2_client.tasks.get(task.id).enable_lessons is False
        finally:
            v2_client.teammates.delete(t.id)

    def test_task_update_reset_enable_to_inherit(self, v2_client):
        t = v2_client.teammates.create(name="ResetBot")
        try:
            task = v2_client.tasks.create(teammate_id=t.id, instructions="x", enable_memory=False)
            assert task.enable_memory is False
            # Explicit None resets to inherit (null) — distinct from omitting.
            updated = v2_client.tasks.update(task.id, enable_memory=None)
            assert updated.enable_memory is None
        finally:
            v2_client.teammates.delete(t.id)
