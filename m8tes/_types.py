"""Dataclass models mirroring v2 API response schemas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class SyncPage(Generic[T]):
    """Paginated list response matching the backend ListResponse envelope."""

    data: list[T]
    has_more: bool


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
    updated_at: str

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
            status=data.get("status", "enabled"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


@dataclass
class Run:
    """A run (execution) of a teammate."""

    id: int
    teammate_id: int | None
    status: str
    output: str | None
    user_id: str | None
    metadata: dict | None
    created_at: str

    @classmethod
    def from_dict(cls, data: dict) -> Run:
        return cls(
            id=data["id"],
            teammate_id=data.get("teammate_id"),
            status=data.get("status", "running"),
            output=data.get("output"),
            user_id=data.get("user_id"),
            metadata=data.get("metadata"),
            created_at=data.get("created_at", ""),
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
    updated_at: str

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
            updated_at=data.get("updated_at", ""),
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
class App:
    """An available tool/integration."""

    name: str
    display_name: str
    category: str
    connected: bool

    @classmethod
    def from_dict(cls, data: dict) -> App:
        return cls(
            name=data["name"],
            display_name=data.get("display_name", data["name"]),
            category=data.get("category", "general"),
            connected=data.get("connected", False),
        )


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


@dataclass
class PermissionPolicy:
    """A pre-configured tool permission policy."""

    id: int
    tool_name: str
    created_at: str

    @classmethod
    def from_dict(cls, data: dict) -> PermissionPolicy:
        return cls(
            id=data["id"],
            tool_name=data["tool_name"],
            created_at=data.get("created_at", ""),
        )


@dataclass
class Webhook:
    """A registered webhook endpoint."""

    id: int
    url: str
    events: list[str]
    secret: str | None
    active: bool
    delivery_status: str
    created_at: str

    @classmethod
    def from_dict(cls, data: dict) -> Webhook:
        return cls(
            id=data["id"],
            url=data["url"],
            events=data.get("events", []),
            secret=data.get("secret"),
            active=data.get("active", True),
            delivery_status=data.get("delivery_status", "coming_soon"),
            created_at=data.get("created_at", ""),
        )
