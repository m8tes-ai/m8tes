"""Teammates resource — CRUD + trigger management for agent personas."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._types import Task, Teammate, Trigger

if TYPE_CHECKING:
    from .._http import HTTPClient


class TeammatesTriggers:
    """Triggers on teammates. Creates a task internally, attaches the trigger."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def create(
        self,
        teammate_id: int,
        *,
        instructions: str,
        type: str,
        cron: str | None = None,
        interval_seconds: int | None = None,
        timezone: str = "UTC",
    ) -> Trigger:
        """Create a trigger on a teammate. Internally creates a task, then attaches the trigger."""
        # 1. Create task for this trigger
        task_resp = self._http.request(
            "POST",
            "/tasks",
            json={"teammate_id": teammate_id, "instructions": instructions},
        )
        task = Task.from_dict(task_resp.json())

        # 2. Attach trigger to the task
        trigger_body: dict = {"type": type, "timezone": timezone}
        if cron:
            trigger_body["cron"] = cron
        if interval_seconds:
            trigger_body["interval_seconds"] = interval_seconds

        resp = self._http.request("POST", f"/tasks/{task.id}/triggers", json=trigger_body)
        return Trigger.from_dict(resp.json())

    def list(self, teammate_id: int) -> list[Trigger]:
        """List all triggers across all tasks for a teammate."""
        tasks_resp = self._http.request("GET", "/tasks", params={"teammate_id": teammate_id})
        triggers: list[Trigger] = []
        for task_data in tasks_resp.json():
            resp = self._http.request("GET", f"/tasks/{task_data['id']}/triggers")
            triggers.extend(Trigger.from_dict(t) for t in resp.json())
        return triggers

    def delete(self, teammate_id: int, trigger_id: int) -> None:
        """Delete a trigger. Searches tasks for the teammate to find the trigger."""
        tasks_resp = self._http.request("GET", "/tasks", params={"teammate_id": teammate_id})
        for task_data in tasks_resp.json():
            resp = self._http.request("GET", f"/tasks/{task_data['id']}/triggers")
            for t in resp.json():
                if t["id"] == trigger_id:
                    self._http.request("DELETE", f"/tasks/{task_data['id']}/triggers/{trigger_id}")
                    return
        from .._exceptions import NotFoundError

        raise NotFoundError(f"Trigger {trigger_id} not found", status_code=404)


class Teammates:
    """client.teammates — agent persona CRUD."""

    def __init__(self, http: HTTPClient):
        self._http = http
        self.triggers = TeammatesTriggers(http)

    def create(
        self,
        *,
        name: str,
        tools: list[str] | None = None,
        instructions: str | None = None,
        role: str | None = None,
        goals: str | None = None,
        user_id: str | None = None,
        metadata: dict | None = None,
        allowed_senders: list[str] | None = None,
    ) -> Teammate:
        body: dict = {"name": name}
        if tools is not None:
            body["tools"] = tools
        if instructions is not None:
            body["instructions"] = instructions
        if role is not None:
            body["role"] = role
        if goals is not None:
            body["goals"] = goals
        if user_id is not None:
            body["user_id"] = user_id
        if metadata is not None:
            body["metadata"] = metadata
        if allowed_senders is not None:
            body["allowed_senders"] = allowed_senders
        resp = self._http.request("POST", "/teammates", json=body)
        return Teammate.from_dict(resp.json())

    def list(self, *, user_id: str | None = None) -> list[Teammate]:
        params = {}
        if user_id is not None:
            params["user_id"] = user_id
        resp = self._http.request("GET", "/teammates", params=params)
        return [Teammate.from_dict(d) for d in resp.json()]

    def get(self, teammate_id: int) -> Teammate:
        resp = self._http.request("GET", f"/teammates/{teammate_id}")
        return Teammate.from_dict(resp.json())

    def update(self, teammate_id: int, **kwargs) -> Teammate:
        resp = self._http.request("PATCH", f"/teammates/{teammate_id}", json=kwargs)
        return Teammate.from_dict(resp.json())

    def delete(self, teammate_id: int) -> None:
        self._http.request("DELETE", f"/teammates/{teammate_id}")
