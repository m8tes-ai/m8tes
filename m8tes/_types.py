"""Dataclass models mirroring v2 API response schemas."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class PermissionMode(StrEnum):
    """Permission modes for controlling tool access during runs.

    Use these constants instead of raw strings when setting permission_mode.
    """

    AUTONOMOUS = "autonomous"
    APPROVAL = "approval"
    PLAN = "plan"


@dataclass
class SyncPage(Generic[T]):
    """Paginated list response matching the backend ListResponse envelope."""

    data: list[T]
    has_more: bool
    _fetch_next: Callable[..., SyncPage[T]] | None = field(default=None, repr=False)

    def auto_paging_iter(self) -> Iterator[T]:
        """Iterate through all pages automatically."""
        page: SyncPage[T] = self
        while True:
            yield from page.data
            if not page.has_more or not page.data or not page._fetch_next:
                break
            last: Any = page.data[-1]
            # Most SDK resources use integer `id` cursors. App pages use `name`.
            cursor = getattr(last, "id", None)
            if cursor is None:
                cursor = getattr(last, "name", None)
            if cursor is None:
                break
            page = page._fetch_next(starting_after=cursor)


@dataclass
class ModelPricing:
    """USD price per MILLION tokens (from the same table that bills runs).

    ``cache_read``/``cache_write`` are the prompt-cache rates: on Anthropic models cache_read is
    discounted and cache_write a premium; on providers without prompt caching both equal the input
    rate (so an estimate never under-counts).
    """

    input_per_mtok: float
    output_per_mtok: float
    cache_read_per_mtok: float
    cache_write_per_mtok: float
    currency: str = "usd"

    @classmethod
    def from_dict(cls, data: dict) -> ModelPricing:
        return cls(
            input_per_mtok=data["input_per_mtok"],
            output_per_mtok=data["output_per_mtok"],
            cache_read_per_mtok=data["cache_read_per_mtok"],
            cache_write_per_mtok=data["cache_write_per_mtok"],
            currency=data.get("currency", "usd"),
        )


@dataclass
class Model:
    """A selectable model. Pass ``id`` as ``model`` on a agent or a run."""

    id: str
    name: str
    description: str
    provider: str  # "anthropic", "openai", … — who serves it
    default: bool  # used when ``model`` is omitted / null
    # Highest effort tier the model accepts ("max" Claude, "high" others);
    # higher requested effort is clamped, never rejected.
    max_effort: str = "max"
    pricing: ModelPricing | None = None

    @classmethod
    def from_dict(cls, data: dict) -> Model:
        pricing = data.get("pricing")
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            provider=data.get("provider", "unknown"),
            default=data["default"],
            max_effort=data.get("max_effort", "max"),
            pricing=ModelPricing.from_dict(pricing) if pricing else None,
        )


@dataclass
class Teammate:
    """An agent persona with tools and instructions (canonical name: Agent)."""

    id: int
    name: str
    instructions: str | None
    tools: list[str]
    role: str | None
    goals: str | None
    user_id: str | None
    metadata: dict | None
    allowed_senders: list[str] | None
    default_permission_mode: str
    status: str
    created_at: str
    updated_at: str | None = None
    inbound_email_enabled: bool = False
    email_address: str | None = None
    inbound_imessage_enabled: bool = False
    imessage_chat_guid: str | None = None
    bridge_id: int | None = None
    allowed_imessage_senders: list[str] | None = None
    inbound_slack_enabled: bool = False
    slack_slug: str | None = None
    allowed_slack_senders: list[str] | None = None
    fetchmail_enabled: bool = False
    fetchmail_address: str | None = None
    webhook_enabled: bool = False
    webhook_url: str | None = None
    # Claude model alias ("sonnet" | "opus"); None = platform default.
    model: str | None = None
    # Reasoning effort ("low"|"medium"|"high"|"xhigh"|"max"); None = platform
    # default (max on Claude models, high on others; see Model.max_effort).
    effort: str | None = None
    # Built-in tool defaults; None = inherit the platform default (enabled).
    enable_memory: bool | None = None
    enable_history: bool | None = None
    enable_task_setup_tools: bool | None = None
    enable_feedback: bool | None = None
    # When True, the agent runs a weekly review-and-improve task over its own runs.
    enable_self_improvement: bool | None = None

    @classmethod
    def from_dict(cls, data: dict) -> Teammate:
        return cls(
            id=data["id"],
            name=data["name"],
            instructions=data.get("instructions"),
            tools=data.get("tools", []),
            role=data.get("role"),
            goals=data.get("goals"),
            user_id=data.get("user_id"),
            metadata=data.get("metadata"),
            allowed_senders=data.get("allowed_senders"),
            default_permission_mode=data.get("default_permission_mode", "autonomous"),
            inbound_email_enabled=data.get("inbound_email_enabled", False),
            email_address=data.get("email_address"),
            inbound_imessage_enabled=data.get("inbound_imessage_enabled", False),
            imessage_chat_guid=data.get("imessage_chat_guid"),
            bridge_id=data.get("bridge_id"),
            allowed_imessage_senders=data.get("allowed_imessage_senders"),
            inbound_slack_enabled=data.get("inbound_slack_enabled", False),
            slack_slug=data.get("slack_slug"),
            allowed_slack_senders=data.get("allowed_slack_senders"),
            fetchmail_enabled=data.get("fetchmail_enabled", False),
            fetchmail_address=data.get("fetchmail_address"),
            webhook_enabled=data.get("webhook_enabled", False),
            webhook_url=data.get("webhook_url"),
            model=data.get("model"),
            effort=data.get("effort"),
            enable_memory=data.get("enable_memory"),
            enable_history=data.get("enable_history"),
            enable_task_setup_tools=data.get("enable_task_setup_tools"),
            enable_feedback=data.get("enable_feedback"),
            enable_self_improvement=data.get("enable_self_improvement"),
            status=data.get("status", "enabled"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at"),
        )


@dataclass
class Bridge:
    """A BlueBubbles bridge (Apple Messages connection).

    Two kinds: ``hosted`` (m8tes-hosted shared server — one-click ``provision()``; creds are
    platform-managed) and ``self_hosted`` (you run your own BlueBubbles server). For hosted
    bridges, ``m8tes_handle`` is the number your team texts and ``link_code`` is the code each
    member texts once to link their phone. The password is write-only (never returned);
    ``webhook_secret`` is populated ONLY on self-hosted create / rotate_secret (shown once).
    """

    id: int
    name: str
    server_url: str
    status: str
    created_at: str
    kind: str = "self_hosted"
    owner_handle: str | None = None
    last_seen_at: str | None = None
    last_outbound_ok_at: str | None = None
    # Hosted bridges: the m8tes number/email your team texts + the active link code.
    m8tes_handle: str | None = None
    link_code: str | None = None
    link_code_expires_at: str | None = None
    # Hosted bridges: True when the active code links exactly one phone, then is consumed.
    link_code_single_use: bool = False
    # Managed (blooio) bridges: the dedicated iMessage number connected to this account.
    provider_number: str | None = None
    webhook_secret: str | None = None
    # Connection health-check result — populated only on self-hosted create.
    connection_ok: bool | None = None
    connection_error: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> Bridge:
        return cls(
            id=data["id"],
            name=data["name"],
            server_url=data["server_url"],
            status=data.get("status", "active"),
            created_at=data.get("created_at", ""),
            kind=data.get("kind", "self_hosted"),
            owner_handle=data.get("owner_handle"),
            last_seen_at=data.get("last_seen_at"),
            last_outbound_ok_at=data.get("last_outbound_ok_at"),
            m8tes_handle=data.get("m8tes_handle"),
            link_code=data.get("link_code"),
            link_code_expires_at=data.get("link_code_expires_at"),
            link_code_single_use=bool(data.get("link_code_single_use", False)),
            provider_number=data.get("provider_number"),
            webhook_secret=data.get("webhook_secret"),
            connection_ok=data.get("connection_ok"),
            connection_error=data.get("connection_error"),
        )


@dataclass
class HandleLink:
    """A verified iMessage handle (phone/email) linked to a hosted bridge's account."""

    id: int
    handle: str
    verified_at: str
    label: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> HandleLink:
        return cls(
            id=data["id"],
            handle=data["handle"],
            verified_at=data.get("verified_at", ""),
            label=data.get("label"),
        )


@dataclass
class RunUsage:
    """Token counts + USD cost for one run. `cost_usd` is a Decimal string and
    matches what billing meters (SDK-authoritative cost with calculated fallback)."""

    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    total_tokens: int
    cost_usd: str

    @classmethod
    def from_dict(cls, data: dict) -> RunUsage:
        return cls(
            input_tokens=data.get("input_tokens", 0),
            output_tokens=data.get("output_tokens", 0),
            cache_read_tokens=data.get("cache_read_tokens", 0),
            cache_creation_tokens=data.get("cache_creation_tokens", 0),
            total_tokens=data.get("total_tokens", 0),
            cost_usd=data.get("cost_usd", "0"),
        )


@dataclass
class Run:
    """A run (execution) of a agent."""

    id: int
    teammate_id: int | None
    status: str
    output: str | None
    error: str | None
    user_id: str | None
    metadata: dict | None
    created_at: str
    updated_at: str | None
    permission_mode: str | None = None
    email_address: str | None = None
    # The task this run executed (every run belongs to exactly one task; ad-hoc runs
    # get an auto-created one). Pull a task's run history: client.runs.list(task_id=...)
    task_id: int | None = None
    # Failure / retry metadata. A retry creates a NEW run; `retry_of_run_id` links
    # it to the one it retried. `retryable` says whether runs.retry() will be
    # accepted; `error_code` is the machine-readable failure class when known.
    error_code: str | None = None
    retryable: bool = False
    retry_of_run_id: int | None = None
    retry_count: int = 0
    # Scheduled-run auto-retry: how many automatic retries this lineage has used,
    # and when the next one fires (ISO timestamp, None when none is scheduled).
    auto_retry_count: int = 0
    next_retry_at: str | None = None
    # Structured result matching the `output_schema` the run was created with. None when no schema
    # was requested — and also None when the model produced no structured result (a run cut short
    # by truncation, a pause, or a spend limit still completes, with its text `output` intact).
    # Always None-check before indexing.
    output_data: dict | None = None
    # Token counts + USD cost for this run; None until metrics arrive.
    usage: RunUsage | None = None

    @property
    def agent_id(self) -> int | None:
        """Canonical alias for the wire field teammate_id."""
        return self.teammate_id

    @classmethod
    def from_dict(cls, data: dict) -> Run:
        return cls(
            id=data["id"],
            teammate_id=data.get("teammate_id"),
            status=data.get("status", "running"),
            output=data.get("output"),
            error=data.get("error"),
            user_id=data.get("user_id"),
            metadata=data.get("metadata"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at"),
            permission_mode=data.get("permission_mode"),
            email_address=data.get("email_address"),
            task_id=data.get("task_id"),
            error_code=data.get("error_code"),
            retryable=data.get("retryable", False),
            retry_of_run_id=data.get("retry_of_run_id"),
            retry_count=data.get("retry_count", 0),
            auto_retry_count=data.get("auto_retry_count", 0),
            next_retry_at=data.get("next_retry_at"),
            output_data=data.get("output_data"),
            usage=RunUsage.from_dict(data["usage"]) if data.get("usage") else None,
        )


@dataclass
class Task:
    """A reusable task definition attached to a agent."""

    id: int
    teammate_id: int
    name: str | None
    instructions: str
    tools: list[str]
    expected_output: str | None
    goals: str | None
    user_id: str | None
    status: str
    created_at: str
    updated_at: str | None = None
    app_trigger_count: int = 0
    email_notifications: bool = True
    webhook_url: str | None = None
    webhook_enabled: bool = False
    # Template propagation metadata (null on custom tasks). Set when a task
    # was seeded from a agent template — see /api/v2/teammate-templates
    # and Teammates.create(from_template=...).
    source_template_task_slug: str | None = None
    is_modified: bool = False
    user_recommends_removal: bool = False
    # Built-in tool defaults; None = inherit from the agent (then platform default).
    enable_memory: bool | None = None
    enable_history: bool | None = None
    enable_task_setup_tools: bool | None = None
    enable_feedback: bool | None = None
    # Self-improvement lessons toggle (task-level, non-null; default on).
    enable_lessons: bool = True

    @property
    def agent_id(self) -> int | None:
        """Canonical alias for the wire field teammate_id."""
        return self.teammate_id

    @classmethod
    def from_dict(cls, data: dict) -> Task:
        return cls(
            id=data["id"],
            teammate_id=data["teammate_id"],
            name=data.get("name"),
            instructions=data["instructions"],
            tools=data.get("tools", []),
            expected_output=data.get("expected_output"),
            goals=data.get("goals"),
            user_id=data.get("user_id"),
            status=data.get("status", "enabled"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at"),
            app_trigger_count=data.get("app_trigger_count", 0),
            email_notifications=data.get("email_notifications", True),
            webhook_url=data.get("webhook_url"),
            webhook_enabled=data.get("webhook_enabled", False),
            source_template_task_slug=data.get("source_template_task_slug"),
            is_modified=data.get("is_modified", False),
            user_recommends_removal=data.get("user_recommends_removal", False),
            enable_memory=data.get("enable_memory"),
            enable_history=data.get("enable_history"),
            enable_task_setup_tools=data.get("enable_task_setup_tools"),
            enable_feedback=data.get("enable_feedback"),
            enable_lessons=data.get("enable_lessons", True),
        )


@dataclass
class Trigger:
    """A trigger (schedule, webhook, email, or app) attached to a task."""

    id: int
    type: str
    enabled: bool
    cron: str | None = None
    interval_seconds: int | None = None
    timezone: str = "UTC"
    next_run: str | None = None
    url: str | None = None
    address: str | None = None
    # App trigger fields (Composio)
    app: str | None = None
    trigger_name: str | None = None
    trigger_config: dict | None = None

    @classmethod
    def from_dict(cls, data: dict) -> Trigger:
        return cls(
            id=data["id"],
            type=data["type"],
            enabled=data.get("enabled", True),
            cron=data.get("cron"),
            interval_seconds=data.get("interval_seconds"),
            timezone=data.get("timezone", "UTC"),
            next_run=data.get("next_run"),
            url=data.get("url"),
            address=data.get("address"),
            app=data.get("app"),
            trigger_name=data.get("trigger_name"),
            trigger_config=data.get("trigger_config"),
        )


@dataclass
class AppTriggerType:
    """Available trigger type for an app (Composio discovery)."""

    slug: str
    name: str
    description: str | None = None
    config: dict = field(default_factory=dict)
    payload: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> AppTriggerType:
        return cls(
            slug=data["slug"],
            name=data["name"],
            description=data.get("description"),
            config=data.get("config", {}),
            payload=data.get("payload", {}),
        )


@dataclass
class TeammateDocument:
    """A agent's persistent document (e.g. latest-report).

    `content` is None on list responses — fetch one document to get its text.
    """

    id: int
    name: str
    summary: str
    mime_type: str
    size_bytes: int
    source: str
    source_run_id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None
    content: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> TeammateDocument:
        return cls(
            id=data["id"],
            name=data["name"],
            summary=data.get("summary", ""),
            mime_type=data.get("mime_type", "text/markdown"),
            size_bytes=data.get("size_bytes", 0),
            source=data.get("source", ""),
            source_run_id=data.get("source_run_id"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            content=data.get("content"),
        )


@dataclass
class RunOutcome:
    """Condensed result of a run — the outcome, not the transcript.

    `summary` is the agent's closing message (None when the run ended on a tool
    call); `cost_usd` is the run's metered cost as a decimal string (None until
    cost is recorded); `needs_reply` flags a closing message that asks for a
    decision — reply via runs.reply().
    """

    run_id: int
    status: str
    summary: str | None
    headline: str | None
    needs_reply: bool
    output_data: dict | None
    message_count: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: str | None

    @classmethod
    def from_dict(cls, data: dict) -> RunOutcome:
        return cls(
            run_id=data["run_id"],
            status=data.get("status", "running"),
            summary=data.get("summary"),
            headline=data.get("headline"),
            needs_reply=data.get("needs_reply", False),
            output_data=data.get("output_data"),
            message_count=data.get("message_count", 0),
            input_tokens=data.get("input_tokens", 0),
            output_tokens=data.get("output_tokens", 0),
            total_tokens=data.get("total_tokens", 0),
            cost_usd=data.get("cost_usd"),
        )


@dataclass
class RunFile:
    """A file generated by a run."""

    name: str
    size: int

    @classmethod
    def from_dict(cls, data: dict) -> RunFile:
        return cls(name=data["name"], size=data["size"])


@dataclass
class AuditLog:
    """A single API request audit record."""

    id: int
    method: str
    path: str
    status_code: int
    duration_ms: int
    action: str | None
    resource_type: str | None
    resource_id: str | None
    api_key_prefix: str | None
    created_at: str

    @classmethod
    def from_dict(cls, data: dict) -> AuditLog:
        return cls(
            id=data["id"],
            method=data["method"],
            path=data["path"],
            status_code=data["status_code"],
            duration_ms=data["duration_ms"],
            action=data.get("action"),
            resource_type=data.get("resource_type"),
            resource_id=data.get("resource_id"),
            api_key_prefix=data.get("api_key_prefix"),
            created_at=data.get("created_at", ""),
        )


@dataclass
class TeammateWebhook:
    """Teammate webhook trigger details (returned when enabling webhook)."""

    enabled: bool
    url: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> TeammateWebhook:
        return cls(enabled=data["enabled"], url=data.get("url"))


@dataclass
class EmailInbox:
    """Teammate email inbox status (returned when enabling email inbox)."""

    enabled: bool
    address: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> EmailInbox:
        return cls(enabled=data["enabled"], address=data.get("address"))


@dataclass
class FetchmailInbox:
    """Teammate fetchmail (read-only) inbox status."""

    enabled: bool
    address: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> FetchmailInbox:
        return cls(enabled=data["enabled"], address=data.get("address"))


@dataclass
class App:
    """An available tool/integration."""

    name: str
    display_name: str
    category: str
    connected: bool
    auth_type: str = ""  # "composio" | "api_key" | "api_key_proxy" | "platform_provisioned"

    @property
    def needs_oauth(self) -> bool:
        """True for OAuth-based integrations (Gmail, Slack, etc.).
        False for API key integrations (Gemini, OpenAI, etc.).

        Use to route to the right helper:
            if app.needs_oauth:
                conn = client.apps.connect_oauth(
                    app.name, redirect_uri=callback_url, user_id=uid
                )
            else:
                conn = client.apps.connect_api_key(app.name, api_key=user_key, user_id=uid)
        """
        return self.auth_type == "composio"

    @classmethod
    def from_dict(cls, data: dict) -> App:
        return cls(
            name=data["name"],
            display_name=data.get("display_name", data["name"]),
            category=data.get("category", "general"),
            connected=data.get("connected", False),
            auth_type=data.get("auth_type", ""),
        )


@dataclass
class BuiltInTool:
    """A platform built-in tool (memory, task history, task setup, feedback, etc.).

    Built-ins are NOT passed in the ``tools=[...]`` array — that's for integrations
    and custom MCP servers. The four ``configurable`` ones (memory, history,
    task_setup_tools, feedback) are toggled via the ``enable_*`` fields on
    agents/tasks/runs. ``multi_tenant_safe=False`` means the tool is skipped on
    end-user (``user_id``-scoped) runs.
    """

    name: str
    server_name: str
    display_name: str
    description: str
    enabled: bool
    multi_tenant_safe: bool
    configurable: bool

    @classmethod
    def from_dict(cls, data: dict) -> BuiltInTool:
        return cls(
            name=data["name"],
            server_name=data.get("server_name", ""),
            display_name=data.get("display_name", data["name"]),
            description=data.get("description", ""),
            enabled=data.get("enabled", False),
            multi_tenant_safe=data.get("multi_tenant_safe", False),
            configurable=data.get("configurable", False),
        )


@dataclass
class AppConnectionInitiation:
    """Returned by apps.connect() — redirect the user to authorization_url to complete OAuth."""

    authorization_url: str
    connection_id: str

    @classmethod
    def from_dict(cls, data: dict) -> AppConnectionInitiation:
        return cls(
            authorization_url=data["authorization_url"],
            connection_id=data["connection_id"],
        )


@dataclass
class AppConnectionResult:
    """Returned by apps.connect_complete() — confirms the connection is active."""

    status: str
    app: str

    @classmethod
    def from_dict(cls, data: dict) -> AppConnectionResult:
        return cls(
            status=data["status"],
            app=data["app"],
        )


@dataclass
class AppProvisionResult:
    """Returned by apps.provision() — a platform-managed resource (e.g. a Twilio number)."""

    status: str
    app: str
    phone_number: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> AppProvisionResult:
        return cls(
            status=data["status"],
            app=data["app"],
            phone_number=data.get("phone_number"),
        )


# Legacy alias kept for backwards compatibility — use AppConnectionInitiation or AppConnectionResult
AppConnection = AppConnectionInitiation


@dataclass
class Memory:
    """A saved memory for an end-user."""

    id: int
    user_id: str | None
    content: str
    source: str
    created_at: str

    @classmethod
    def from_dict(cls, data: dict) -> Memory:
        return cls(
            id=data["id"],
            user_id=data.get("user_id"),
            content=data["content"],
            source=data.get("source", "api"),
            created_at=data.get("created_at", ""),
        )


@dataclass
class PermissionRequest:
    """A pending or resolved tool permission request on a run."""

    request_id: str
    tool_name: str
    tool_input: dict | None
    status: str
    created_at: str
    resolved_at: str | None
    # True when the platform resolved the request itself: a question whose options
    # carried a "(Recommended)" label auto-continued after ~10 minutes without an
    # answer (or immediately for a non-blocking ask). Auto-selected answer values
    # in tool_input["answers"] end with an "[auto-selected …]" marker. Answering
    # an auto-resolved question via runs.answer() raises ConflictError
    # ("auto_continued") — send a follow-up message to redirect instead.
    auto_resolved: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> PermissionRequest:
        return cls(
            request_id=data["request_id"],
            tool_name=data["tool_name"],
            tool_input=data.get("tool_input"),
            status=data["status"],
            created_at=data.get("created_at", ""),
            resolved_at=data.get("resolved_at"),
            auto_resolved=data.get("auto_resolved", False),
        )

    @property
    def is_plan_approval(self) -> bool:
        """True if this is a plan mode approval pause (agent proposing a plan)."""
        if self.tool_name != "AskUserQuestion" or not self.tool_input:
            return False
        return any(q.get("header") == "Plan Approval" for q in self.tool_input.get("questions", []))

    @property
    def plan_text(self) -> str | None:
        """The proposed plan text. Only set for plan approval requests."""
        if not self.is_plan_approval or not self.tool_input:
            return None
        for q in self.tool_input.get("questions", []):
            if q.get("header") == "Plan Approval":
                return q.get("question") or None
        return None


@dataclass
class PermissionPolicy:
    """A pre-configured tool permission policy."""

    id: int
    user_id: str
    tool_name: str
    created_at: str

    @classmethod
    def from_dict(cls, data: dict) -> PermissionPolicy:
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            tool_name=data["tool_name"],
            created_at=data.get("created_at", ""),
        )


@dataclass
class PermissionModeResponse:
    """Current permission mode for a run."""

    permission_mode: str

    @classmethod
    def from_dict(cls, data: dict) -> PermissionModeResponse:
        return cls(permission_mode=data["permission_mode"])


@dataclass
class Webhook:
    """A registered webhook endpoint."""

    id: int
    url: str
    events: list[str]
    secret: str | None
    active: bool
    created_at: str
    updated_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> Webhook:
        return cls(
            id=data["id"],
            url=data["url"],
            events=data.get("events", []),
            secret=data.get("secret"),
            active=data.get("active", True),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at"),
        )


@dataclass
class WebhookDelivery:
    """A webhook delivery attempt."""

    id: int
    webhook_endpoint_id: int
    event_type: str
    event_id: str
    run_id: int
    status: str
    response_status_code: int | None
    response_body: str | None
    attempts: int
    next_retry_at: str | None
    created_at: str

    @classmethod
    def from_dict(cls, data: dict) -> WebhookDelivery:
        return cls(
            id=data["id"],
            webhook_endpoint_id=data["webhook_endpoint_id"],
            event_type=data["event_type"],
            event_id=data["event_id"],
            run_id=data["run_id"],
            status=data["status"],
            response_status_code=data.get("response_status_code"),
            response_body=data.get("response_body"),
            attempts=data.get("attempts", 0),
            next_retry_at=data.get("next_retry_at"),
            created_at=data.get("created_at", ""),
        )


@dataclass
class EndUser:
    """A structured end-user profile."""

    id: int
    user_id: str
    name: str | None
    email: str | None
    company: str | None
    metadata: dict | None
    created_at: str
    updated_at: str | None = None
    # Per-individual sub-cap overrides (None = inherit account defaults).
    run_limit: int | None = None
    cost_limit_cents: int | None = None
    rate_per_minute: int | None = None

    @classmethod
    def from_dict(cls, data: dict) -> EndUser:
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            name=data.get("name"),
            email=data.get("email"),
            company=data.get("company"),
            metadata=data.get("metadata"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at"),
            run_limit=data.get("run_limit"),
            cost_limit_cents=data.get("cost_limit_cents"),
            rate_per_minute=data.get("rate_per_minute"),
        )


@dataclass
class EndUserUsage:
    """One end-user's usage for the current billing period."""

    id: int
    user_id: str
    runs_used: int
    cost_used: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    last_active_at: str | None
    runs_limit: int | None
    cost_limit_cents: int | None
    period_end: str
    rate_per_minute: int | None = None

    @classmethod
    def from_dict(cls, data: dict) -> EndUserUsage:
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            runs_used=data["runs_used"],
            cost_used=data["cost_used"],
            input_tokens=data["input_tokens"],
            output_tokens=data["output_tokens"],
            total_tokens=data["total_tokens"],
            last_active_at=data.get("last_active_at"),
            runs_limit=data.get("runs_limit"),
            cost_limit_cents=data.get("cost_limit_cents"),
            period_end=data.get("period_end", ""),
            rate_per_minute=data.get("rate_per_minute"),
        )


@dataclass
class AccountSettings:
    """Account-level settings."""

    # Per-end-user (multi-tenant) sub-caps; None = no cap.
    per_end_user_run_limit: int | None = None
    per_end_user_cost_limit_cents: int | None = None
    per_end_user_rate_per_minute: int | None = None
    # Data retention: "standard" or "metadata_only" (zero data retention).
    retention_mode: str = "standard"
    # Strict multi-tenant mode: user_id required on every scoped request.
    require_end_user_id: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> AccountSettings:
        return cls(
            per_end_user_run_limit=data.get("per_end_user_run_limit"),
            per_end_user_cost_limit_cents=data.get("per_end_user_cost_limit_cents"),
            per_end_user_rate_per_minute=data.get("per_end_user_rate_per_minute"),
            retention_mode=data.get("retention_mode", "standard"),
            require_end_user_id=data.get("require_end_user_id", False),
        )


@dataclass
class ApiKeyInfo:
    """Current API key state (masked — the secret is never returned here)."""

    has_key: bool
    prefix: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> ApiKeyInfo:
        return cls(has_key=data["has_key"], prefix=data.get("prefix"))


@dataclass
class ApiKeyRotated:
    """A freshly rotated API key. ``api_key`` is shown ONCE — store it now."""

    api_key: str
    prefix: str

    @classmethod
    def from_dict(cls, data: dict) -> ApiKeyRotated:
        return cls(api_key=data["api_key"], prefix=data["prefix"])


@dataclass
class ApiKeyCreated:
    """A newly created or rotated named key. ``api_key`` is shown ONCE — store it now."""

    id: int
    name: str
    api_key: str
    prefix: str
    expires_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> ApiKeyCreated:
        return cls(
            id=data["id"],
            name=data["name"],
            api_key=data["api_key"],
            prefix=data["prefix"],
            expires_at=data.get("expires_at"),
        )


@dataclass
class NamedApiKey:
    """A managed API key (no secret — the key value is never returned in a list)."""

    id: int
    name: str
    prefix: str
    created_at: str
    active: bool
    last_used_at: str | None = None
    expires_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> NamedApiKey:
        return cls(
            id=data["id"],
            name=data["name"],
            prefix=data["prefix"],
            created_at=data.get("created_at", ""),
            active=data.get("active", True),
            last_used_at=data.get("last_used_at"),
            expires_at=data.get("expires_at"),
        )


@dataclass
class SignupResult:
    """Returned by m8tes.signup() — new account with API key.

    `verification` is "pending" until the user clicks the one-tap activation link
    emailed to them, then "verified". The link itself is never returned here: an API
    key holder must not also hold a login-as-the-user link. Poll client.auth.is_verified()
    (or use signup_and_wait) to learn when the user has activated.
    """

    api_key: str
    email: str
    message: str
    verification: str = "pending"

    @classmethod
    def from_dict(cls, data: dict) -> SignupResult:
        return cls(
            api_key=data["api_key"],
            email=data["email"],
            message=data["message"],
            verification=data.get("verification", "pending"),
        )


@dataclass
class TokenResult:
    """Returned by m8tes.get_token() — newly generated API key."""

    api_key: str
    email: str
    message: str

    @classmethod
    def from_dict(cls, data: dict) -> TokenResult:
        return cls(api_key=data["api_key"], email=data["email"], message=data["message"])


@dataclass
class Usage:
    """Billing usage and limits for the authenticated user.

    Overage fields (opt-in usage overage) and trial_ends_at are optional with
    safe defaults so older backends that omit them don't break parsing.
    """

    plan: str
    runs_used: int
    runs_limit: int
    cost_used: str
    cost_limit: str
    period_end: str
    subscription_status: str | None
    # Opt-in usage overage — meter your own spend against the per-account cap.
    overage_enabled: bool = False
    overage_used_cents: int = 0
    overage_cap_cents: int = 0
    overage_rate_cents: int = 0
    trial_ends_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> Usage:
        return cls(
            plan=data["plan"],
            runs_used=data["runs_used"],
            runs_limit=data["runs_limit"],
            cost_used=data["cost_used"],
            cost_limit=data["cost_limit"],
            period_end=data["period_end"],
            subscription_status=data.get("subscription_status"),
            overage_enabled=data.get("overage_enabled", False),
            overage_used_cents=data.get("overage_used_cents", 0),
            overage_cap_cents=data.get("overage_cap_cents", 0),
            overage_rate_cents=data.get("overage_rate_cents", 0),
            trial_ends_at=data.get("trial_ends_at"),
        )


@dataclass
class Plan:
    """A public (paid) plan from the canonical catalog. Prices are in cents."""

    slug: str
    display_name: str
    included_runs: int
    monthly_price_cents: int
    annual_price_cents: int
    overage_rate_cents: int
    # Per-period model-spend fair-use cap; 0 when the server predates the field.
    fair_use_cost_limit_cents: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> Plan:
        return cls(
            slug=data["slug"],
            display_name=data["display_name"],
            included_runs=data["included_runs"],
            monthly_price_cents=data["monthly_price_cents"],
            annual_price_cents=data["annual_price_cents"],
            overage_rate_cents=data["overage_rate_cents"],
            fair_use_cost_limit_cents=data.get("fair_use_cost_limit_cents", 0),
        )


@dataclass
class TokenTransaction:
    """One prepaid token-balance ledger entry (micro-USD; debits are negative)."""

    type: str
    amount_micros: int
    balance_after_micros: int
    run_id: int | None
    description: str | None
    created_at: str

    @classmethod
    def from_dict(cls, data: dict) -> TokenTransaction:
        return cls(
            type=data["type"],
            amount_micros=data["amount_micros"],
            balance_after_micros=data["balance_after_micros"],
            run_id=data.get("run_id"),
            description=data.get("description"),
            created_at=data["created_at"],
        )


@dataclass
class Balance:
    """Prepaid token balance + recent ledger (for accounts on prepaid billing).

    Balances are micro-USD (1e-6 USD); `balance_usd` is a rounded display string. Runs
    debit this balance at official provider prices.
    """

    balance_micros: int
    balance_usd: str
    currency: str
    # Warning thresholds (micro-USD): low is configurable; critical is 20% of it; depleted is 0.
    low_balance_threshold_micros: int
    critical_balance_threshold_micros: int
    transactions: list[TokenTransaction]
    # Auto-reload: when enabled, a balance below threshold_cents triggers an off-session
    # charge of amount_cents to the saved card. Configure via set_auto_reload().
    auto_reload_enabled: bool = False
    auto_reload_threshold_cents: int | None = None
    auto_reload_amount_cents: int | None = None

    @classmethod
    def from_dict(cls, data: dict) -> Balance:
        return cls(
            balance_micros=data["balance_micros"],
            balance_usd=data["balance_usd"],
            currency=data["currency"],
            low_balance_threshold_micros=data.get("low_balance_threshold_micros", 0),
            critical_balance_threshold_micros=data.get("critical_balance_threshold_micros", 0),
            transactions=[TokenTransaction.from_dict(t) for t in data.get("transactions", [])],
            auto_reload_enabled=data.get("auto_reload_enabled", False),
            auto_reload_threshold_cents=data.get("auto_reload_threshold_cents"),
            auto_reload_amount_cents=data.get("auto_reload_amount_cents"),
        )


def _usage_lanes(data: dict) -> dict:
    """The token/cost lanes shared by every usage shape — one extraction, reused by
    UsageTotals / UsageModelSlice / UsageBucket so adding a lane touches one place."""
    return {
        "input_tokens": data.get("input_tokens", 0),
        "output_tokens": data.get("output_tokens", 0),
        "cache_read_tokens": data.get("cache_read_tokens", 0),
        "cache_creation_tokens": data.get("cache_creation_tokens", 0),
        "total_tokens": data.get("total_tokens", 0),
        "cost_usd": data.get("cost_usd", "0"),
    }


@dataclass
class UsageTotals:
    """Token + USD totals over a usage-timeseries window."""

    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    total_tokens: int
    cost_usd: str

    @classmethod
    def from_dict(cls, data: dict) -> UsageTotals:
        return cls(**_usage_lanes(data))


@dataclass
class UsageModelSlice(UsageTotals):
    """One model's share of a day bucket ("unknown" for pre-attribution history)."""

    model: str = "unknown"

    @classmethod
    def from_dict(cls, data: dict) -> UsageModelSlice:
        return cls(**_usage_lanes(data), model=data.get("model", "unknown"))


@dataclass
class UsageBucket(UsageTotals):
    """One UTC-day bucket of token + USD usage (ISO date string)."""

    date: str = ""
    # Per-model slices — populated only when the series was requested with
    # group_by="model"; None otherwise.
    models: list[UsageModelSlice] | None = None

    @classmethod
    def from_dict(cls, data: dict) -> UsageBucket:
        return cls(
            **_usage_lanes(data),
            date=data.get("date", ""),
            models=(
                [UsageModelSlice.from_dict(s) for s in data["models"]]
                if data.get("models") is not None
                else None
            ),
        )


@dataclass
class UsageTimeseries:
    """Daily usage buckets, zero-filled across [start_date, end_date] (UTC days)."""

    start_date: str
    end_date: str
    buckets: list[UsageBucket]
    totals: UsageTotals

    @classmethod
    def from_dict(cls, data: dict) -> UsageTimeseries:
        return cls(
            start_date=data.get("start_date", ""),
            end_date=data.get("end_date", ""),
            buckets=[UsageBucket.from_dict(b) for b in data.get("buckets", [])],
            totals=UsageTotals.from_dict(data.get("totals", {})),
        )


@dataclass
class Receipt:
    """One prepaid top-up with its Stripe-hosted receipt link (may be None when
    the underlying checkout session is no longer retrievable)."""

    id: int
    amount_cents: int
    currency: str
    description: str | None
    receipt_url: str | None
    created_at: str

    @classmethod
    def from_dict(cls, data: dict) -> Receipt:
        return cls(
            id=data.get("id", 0),
            amount_cents=data.get("amount_cents", 0),
            currency=data.get("currency", "usd"),
            description=data.get("description"),
            receipt_url=data.get("receipt_url"),
            created_at=data.get("created_at", ""),
        )


@dataclass
class TeammateTemplate:
    """A pre-built agent template from the public catalog.

    Use `slug` with `client.agents.create(from_template=slug)`. The nested
    task/question lists are kept as plain dicts (read e.g. `t.default_tasks[0]["slug"]`).
    """

    slug: str
    name: str
    description: str
    logo_ref: str
    required_integrations: list[str]
    role: str | None = None
    goals: str | None = None
    default_tasks: list[dict] = field(default_factory=list)
    bootstrap_tasks: list[dict] = field(default_factory=list)
    questions: list[dict] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> TeammateTemplate:
        return cls(
            slug=data["slug"],
            name=data["name"],
            description=data.get("description", ""),
            logo_ref=data.get("logo_ref", ""),
            required_integrations=data.get("required_integrations", []),
            role=data.get("role"),
            goals=data.get("goals"),
            default_tasks=data.get("default_tasks", []),
            bootstrap_tasks=data.get("bootstrap_tasks", []),
            questions=data.get("questions", []),
        )


@dataclass
class Lesson:
    """A lesson a task's agent has saved for future runs."""

    id: str
    text: str
    when_applicable: str
    created_at: str
    last_reaffirmed_at: str
    source_run_id: int | None = None
    reaffirm_count: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> Lesson:
        return cls(
            id=data["id"],
            text=data.get("text", ""),
            when_applicable=data.get("when_applicable", ""),
            created_at=data.get("created_at", ""),
            last_reaffirmed_at=data.get("last_reaffirmed_at", ""),
            source_run_id=data.get("source_run_id"),
            reaffirm_count=data.get("reaffirm_count", 0),
        )


@dataclass
class LessonList:
    """A task's lessons plus capacity metadata."""

    data: list[Lesson]
    capacity_used: int
    capacity_limit: int

    @classmethod
    def from_dict(cls, data: dict) -> LessonList:
        return cls(
            data=[Lesson.from_dict(d) for d in data.get("data", [])],
            capacity_used=data.get("capacity_used", 0),
            capacity_limit=data.get("capacity_limit", 0),
        )


@dataclass
class McpServer:
    """A user-defined custom tool server (BYO REST endpoints exposed as agent tools).

    The auth secret is write-only (set on create/update, never returned) — ``has_secret``
    reports whether one is stored. Attach to a agent by passing ``slug`` in the
    agent's ``tools=[...]`` list.
    """

    id: int
    slug: str
    name: str
    url: str
    kind: str
    auth_type: str
    status: str
    description: str | None = None
    tool_defs: list[dict[str, Any]] = field(default_factory=list)
    has_secret: bool = False
    auto_approve: bool = False
    user_id: str | None = None
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> McpServer:
        return cls(
            id=data["id"],
            slug=data["slug"],
            name=data["name"],
            url=data["url"],
            kind=data.get("kind", "rest_api"),
            auth_type=data.get("auth_type", "none"),
            status=data.get("status", "active"),
            description=data.get("description"),
            tool_defs=data.get("tool_defs", []),
            has_secret=data.get("has_secret", False),
            auto_approve=data.get("auto_approve", False),
            user_id=data.get("user_id"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


@dataclass
class Skill:
    """A user/agent-authored Agent Skill (a markdown SKILL.md playbook the agent loads
    on demand). ``scope`` is "account" (all Mates) or "teammate" (one Mate, ``teammate_id``).
    ``source`` is "user" or "agent". Skills the agent loads at run start guide its work."""

    id: int
    slug: str
    name: str
    description: str
    body: str
    scope: str
    source: str
    status: str
    teammate_id: int | None = None
    user_id: str | None = None
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> Skill:
        return cls(
            id=data["id"],
            slug=data["slug"],
            name=data["name"],
            description=data["description"],
            body=data["body"],
            scope=data.get("scope", "account"),
            source=data.get("source", "user"),
            status=data.get("status", "active"),
            teammate_id=data.get("teammate_id"),
            user_id=data.get("user_id"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


# Canonical naming: "agent" is the developer-facing term; Teammate is the same
# class under its legacy name. NOTE: the alias is NOT re-exported at package top
# level — the legacy v1 module m8tes/agent.py already owns the public name
# `m8tes.Agent`. Import from m8tes._types if you want the v2 alias explicitly.
Agent = Teammate
AgentTemplate = TeammateTemplate
