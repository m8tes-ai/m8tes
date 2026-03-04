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
class Teammate:
    """A teammate (agent persona) with tools and instructions."""

    id: int
    name: str
    instructions: str | None
    tools: list[str]
    role: str | None
    goals: str | None
    user_id: str | None
    metadata: dict | None
    allowed_senders: list[str] | None
    status: str
    created_at: str
    updated_at: str | None = None
    inbound_email_enabled: bool = False
    email_address: str | None = None
    webhook_enabled: bool = False
    webhook_url: str | None = None

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
            inbound_email_enabled=data.get("inbound_email_enabled", False),
            email_address=data.get("email_address"),
            webhook_enabled=data.get("webhook_enabled", False),
            webhook_url=data.get("webhook_url"),
            status=data.get("status", "enabled"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at"),
        )


@dataclass
class Run:
    """A run (execution) of a teammate."""

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
        )


@dataclass
class Task:
    """A reusable task definition attached to a teammate."""

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
    email_notifications: bool = True
    webhook_url: str | None = None
    webhook_enabled: bool = False

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
            email_notifications=data.get("email_notifications", True),
            webhook_url=data.get("webhook_url"),
            webhook_enabled=data.get("webhook_enabled", False),
        )


@dataclass
class Trigger:
    """A trigger (schedule, webhook, or email) attached to a task."""

    id: int
    type: str
    enabled: bool
    cron: str | None = None
    interval_seconds: int | None = None
    timezone: str = "UTC"
    next_run: str | None = None
    url: str | None = None
    address: str | None = None

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
class App:
    """An available tool/integration."""

    name: str
    display_name: str
    category: str
    connected: bool
    auth_type: str = ""  # "composio" | "api_key" | "api_key_proxy"

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

    @classmethod
    def from_dict(cls, data: dict) -> PermissionRequest:
        return cls(
            request_id=data["request_id"],
            tool_name=data["tool_name"],
            tool_input=data.get("tool_input"),
            status=data["status"],
            created_at=data.get("created_at", ""),
            resolved_at=data.get("resolved_at"),
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
        )


@dataclass
class AccountSettings:
    """Account-level settings."""

    company_research: bool

    @classmethod
    def from_dict(cls, data: dict) -> AccountSettings:
        return cls(company_research=data["company_research"])


@dataclass
class SignupResult:
    """Returned by m8tes.signup() — new account with API key."""

    api_key: str
    email: str
    message: str

    @classmethod
    def from_dict(cls, data: dict) -> SignupResult:
        return cls(api_key=data["api_key"], email=data["email"], message=data["message"])


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
    """Billing usage and limits for the authenticated user."""

    plan: str
    runs_used: int
    runs_limit: int
    cost_used: str
    cost_limit: str
    period_end: str
    subscription_status: str | None

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
        )
