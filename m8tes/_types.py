"""Dataclass models mirroring v2 API response schemas."""

from __future__ import annotations

from dataclasses import dataclass


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
