"""Tasks resource — reusable task definitions with direct execution."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._streaming import RunStream
from .._types import Run, SyncPage, Task, Trigger
from ._utils import _build_params

_list = list  # preserve builtin; shadowed by .list() method

if TYPE_CHECKING:
    from .._http import HTTPClient


class TaskTriggers:
    """Direct task trigger management for power users."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def create(
        self,
        task_id: int,
        *,
        type: str,
        cron: str | None = None,
        interval_seconds: int | None = None,
        timezone: str = "UTC",
    ) -> Trigger:
        body: dict = {"type": type, "timezone": timezone}
        if cron:
            body["cron"] = cron
        if interval_seconds:
            body["interval_seconds"] = interval_seconds
        resp = self._http.request("POST", f"/tasks/{task_id}/triggers", json=body)
        return Trigger.from_dict(resp.json())

    def list(self, task_id: int) -> list[Trigger]:
        resp = self._http.request("GET", f"/tasks/{task_id}/triggers")
        return [Trigger.from_dict(d) for d in resp.json()]

    def delete(self, task_id: int, trigger_id: int) -> None:
        self._http.request("DELETE", f"/tasks/{task_id}/triggers/{trigger_id}")


class Tasks:
    """client.tasks — reusable task CRUD (advanced)."""

    def __init__(self, http: HTTPClient):
        self._http = http
        self.triggers = TaskTriggers(http)

    def create(
        self,
        *,
        teammate_id: int,
        instructions: str,
        name: str | None = None,
        tools: list[str] | None = None,
        expected_output: str | None = None,
        goals: str | None = None,
        user_id: str | None = None,
    ) -> Task:
        body: dict = {"teammate_id": teammate_id, "instructions": instructions}
        if name is not None:
            body["name"] = name
        if tools is not None:
            body["tools"] = tools
        if expected_output is not None:
            body["expected_output"] = expected_output
        if goals is not None:
            body["goals"] = goals
        if user_id is not None:
            body["user_id"] = user_id
        resp = self._http.request("POST", "/tasks", json=body)
        return Task.from_dict(resp.json())

    def list(
        self,
        *,
        teammate_id: int | None = None,
        user_id: str | None = None,
        limit: int = 20,
        starting_after: int | None = None,
    ) -> SyncPage[Task]:
        params = _build_params(
            teammate_id=teammate_id, user_id=user_id, limit=limit, starting_after=starting_after
        )
        resp = self._http.request("GET", "/tasks", params=params)
        body = resp.json()

        def _fetch_next(**kw: object) -> SyncPage[Task]:
            return self.list(teammate_id=teammate_id, user_id=user_id, **kw)  # type: ignore[arg-type]

        return SyncPage(
            data=[Task.from_dict(d) for d in body["data"]],
            has_more=body["has_more"],
            _fetch_next=_fetch_next,
        )

    def get(self, task_id: int) -> Task:
        resp = self._http.request("GET", f"/tasks/{task_id}")
        return Task.from_dict(resp.json())

    def update(
        self,
        task_id: int,
        *,
        name: str | None = None,
        instructions: str | None = None,
        tools: _list[str] | None = None,
        expected_output: str | None = None,
        goals: str | None = None,
    ) -> Task:
        body: dict = {}
        if name is not None:
            body["name"] = name
        if instructions is not None:
            body["instructions"] = instructions
        if tools is not None:
            body["tools"] = tools
        if expected_output is not None:
            body["expected_output"] = expected_output
        if goals is not None:
            body["goals"] = goals
        resp = self._http.request("PATCH", f"/tasks/{task_id}", json=body)
        return Task.from_dict(resp.json())

    def run(
        self,
        task_id: int,
        *,
        stream: bool = True,
        user_id: str | None = None,
        metadata: dict | None = None,
        memory: bool = True,
        history: bool = True,
        human_in_the_loop: bool = False,
        permission_mode: str = "autonomous",
    ) -> RunStream | Run:
        """Execute a saved task, creating a new run.

        With stream=True (default): returns iterable RunStream of events.
        With stream=False: returns Run immediately (status="running").
            Poll runs.poll(run.id) until status is terminal to get output.

        Set human_in_the_loop=True to enable interactive features
        (clarifying questions, tool approval, plan mode).
        """
        body: dict = {"stream": stream, "memory": memory, "history": history}
        if user_id is not None:
            body["user_id"] = user_id
        if metadata is not None:
            body["metadata"] = metadata
        if human_in_the_loop:
            body["human_in_the_loop"] = True
        if permission_mode != "autonomous":
            body["permission_mode"] = permission_mode

        if stream:
            resp = self._http.stream("POST", f"/tasks/{task_id}/runs", json=body)
            return RunStream(resp)

        resp = self._http.request("POST", f"/tasks/{task_id}/runs", json=body)
        return Run.from_dict(resp.json())

    def delete(self, task_id: int) -> None:
        self._http.request("DELETE", f"/tasks/{task_id}")
