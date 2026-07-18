"""Tasks resource — reusable task definitions with direct execution."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

from .._streaming import RunStream
from .._types import LessonList, PermissionRequest, Run, SyncPage, Task, TeammateWebhook, Trigger
from ._utils import _build_params, _resolve_agent_id

_list = list  # preserve builtin; shadowed by .list() method

# Sentinel distinguishing "not provided" (leave unchanged) from an explicit None
# (send JSON null → reset the toggle to the platform default). Mirrors agents.py.
_UNSET: Any = object()

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
        app: str | None = None,
        trigger_name: str | None = None,
        trigger_config: dict | None = None,
        user_id: str | None = None,
        allowed_senders: list[str] | None = None,
    ) -> Trigger:
        body: dict = {"type": type, "timezone": timezone}
        if cron:
            body["cron"] = cron
        if interval_seconds:
            body["interval_seconds"] = interval_seconds
        if app:
            body["app"] = app
        if trigger_name:
            body["trigger_name"] = trigger_name
        if trigger_config is not None:
            body["trigger_config"] = trigger_config
        if user_id:
            body["user_id"] = user_id
        if allowed_senders is not None:
            body["allowed_senders"] = allowed_senders
        resp = self._http.request("POST", f"/tasks/{task_id}/triggers/", json=body)
        return Trigger.from_dict(resp.json())

    def list(self, task_id: int) -> list[Trigger]:
        resp = self._http.request("GET", f"/tasks/{task_id}/triggers/")
        body = resp.json()
        items = body["data"] if isinstance(body, dict) and "data" in body else body
        return [Trigger.from_dict(d) for d in items]

    def update(
        self,
        task_id: int,
        trigger_id: int,
        *,
        enabled: bool | None = None,
        cron: str | None = None,
        interval_seconds: int | None = None,
        timezone: str | None = None,
    ) -> Trigger:
        """Update a trigger in place: pause/resume with ``enabled``, or reshape a
        schedule's cron/interval/timezone — no delete + re-create needed."""
        body: dict = {}
        if enabled is not None:
            body["enabled"] = enabled
        if cron is not None:
            body["cron"] = cron
        if interval_seconds is not None:
            body["interval_seconds"] = interval_seconds
        if timezone is not None:
            body["timezone"] = timezone
        resp = self._http.request("PATCH", f"/tasks/{task_id}/triggers/{trigger_id}", json=body)
        return Trigger.from_dict(resp.json())

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
        instructions: str,
        teammate_id: int | None = None,
        agent_id: int | None = None,
        name: str | None = None,
        tools: list[str] | None = None,
        expected_output: str | None = None,
        goals: str | None = None,
        user_id: str | None = None,
        email_notifications: bool = True,
        webhook: bool = False,
        schedule: str | None = None,
        schedule_timezone: str = "UTC",
        enable_memory: bool | None = None,
        enable_history: bool | None = None,
        enable_task_setup_tools: bool | None = None,
        enable_feedback: bool | None = None,
        enable_lessons: bool | None = None,
    ) -> Task:
        """Create a reusable task.

        The four enable_* fields set this task's default for the built-in tools;
        leave None to inherit the agent default (then the platform default).
        enable_lessons toggles whether the agent accumulates self-improvement
        lessons across this task's runs (task-level, default on).
        """
        teammate_id = _resolve_agent_id(teammate_id, agent_id)
        if teammate_id is None:
            raise ValueError("agent_id (or legacy teammate_id) is required")
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
        if enable_memory is not None:
            body["enable_memory"] = enable_memory
        if enable_history is not None:
            body["enable_history"] = enable_history
        if enable_task_setup_tools is not None:
            body["enable_task_setup_tools"] = enable_task_setup_tools
        if enable_feedback is not None:
            body["enable_feedback"] = enable_feedback
        if enable_lessons is not None:
            body["enable_lessons"] = enable_lessons
        if not email_notifications:
            body["email_notifications"] = False
        if webhook:
            body["webhook"] = True
        if schedule is not None:
            body["schedule"] = schedule
            body["schedule_timezone"] = schedule_timezone
        resp = self._http.request("POST", "/tasks/", json=body)
        return Task.from_dict(resp.json())

    def list(
        self,
        *,
        teammate_id: int | None = None,
        agent_id: int | None = None,
        user_id: str | None = None,
        limit: int = 20,
        starting_after: int | None = None,
    ) -> SyncPage[Task]:
        teammate_id = _resolve_agent_id(teammate_id, agent_id)
        params = _build_params(
            teammate_id=teammate_id, user_id=user_id, limit=limit, starting_after=starting_after
        )
        resp = self._http.request("GET", "/tasks/", params=params)
        body = resp.json()

        def _fetch_next(**kw: object) -> SyncPage[Task]:
            return self.list(teammate_id=teammate_id, user_id=user_id, **kw)  # type: ignore[arg-type]

        return SyncPage(
            data=[Task.from_dict(d) for d in body["data"]],
            has_more=body["has_more"],
            _fetch_next=_fetch_next,
        )

    def get(self, task_id: int, *, user_id: str | None = None) -> Task:
        """Get a task. Pass user_id to scope to one end-user (404 on mismatch)."""
        resp = self._http.request("GET", f"/tasks/{task_id}", params=_build_params(user_id=user_id))
        return Task.from_dict(resp.json())

    def update(
        self,
        task_id: int,
        *,
        user_id: str | None = None,
        name: str | None = None,
        instructions: str | None = None,
        tools: _list[str] | None = None,
        expected_output: str | None = None,
        goals: str | None = None,
        email_notifications: bool | None = None,
        enable_memory: bool | None = _UNSET,
        enable_history: bool | None = _UNSET,
        enable_task_setup_tools: bool | None = _UNSET,
        enable_feedback: bool | None = _UNSET,
        enable_lessons: bool | None = None,
    ) -> Task:
        """Update a task (PATCH — omitted fields unchanged).

        For the four ``enable_*`` built-in tool defaults: omit to leave unchanged,
        pass True/False to pin this task's default, or pass ``None`` to reset that
        toggle back to inherit-from-agent (sends JSON null). Mirrors
        ``agents.update``.
        """
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
        if email_notifications is not None:
            body["email_notifications"] = email_notifications
        # Explicit None -> JSON null -> resets the toggle to inherit-from-agent.
        if enable_memory is not _UNSET:
            body["enable_memory"] = enable_memory
        if enable_history is not _UNSET:
            body["enable_history"] = enable_history
        if enable_task_setup_tools is not _UNSET:
            body["enable_task_setup_tools"] = enable_task_setup_tools
        if enable_feedback is not _UNSET:
            body["enable_feedback"] = enable_feedback
        # enable_lessons is non-null (no reset-to-inherit); send only when set.
        if enable_lessons is not None:
            body["enable_lessons"] = enable_lessons
        resp = self._http.request(
            "PATCH", f"/tasks/{task_id}", json=body, params=_build_params(user_id=user_id)
        )
        return Task.from_dict(resp.json())

    def run(
        self,
        task_id: int,
        *,
        stream: bool = True,
        user_id: str | None = None,
        metadata: dict | None = None,
        memory: bool | None = None,
        history: bool | None = None,
        task_setup_tools: bool | None = None,
        feedback: bool | None = None,
        human_in_the_loop: bool | None = None,
        permission_mode: str | None = None,
        model: str | None = None,
    ) -> RunStream | Run:
        """Execute a saved task, creating a new run.

        With stream=True (default): returns iterable RunStream of events.
        With stream=False: returns Run immediately (status="running").
            Poll runs.poll(run.id) until status is terminal to get output.

        Set human_in_the_loop=True to enable interactive features
        (clarifying questions, tool approval, plan mode).

        The four built-in tool toggles (memory, history, task_setup_tools,
        feedback) are run-level overrides; leave them None to inherit the task
        then agent default (then the platform default, enabled).

        If the saved task is already scoped to an end user, omitting user_id
        inherits that scope. Passing a different user_id is rejected.
        """
        body: dict = {"stream": stream}
        if memory is not None:
            body["memory"] = memory
        if history is not None:
            body["history"] = history
        if task_setup_tools is not None:
            body["task_setup_tools"] = task_setup_tools
        if feedback is not None:
            body["feedback"] = feedback
        if user_id is not None:
            body["user_id"] = user_id
        if metadata is not None:
            body["metadata"] = metadata
        if human_in_the_loop is not None:
            body["human_in_the_loop"] = human_in_the_loop
        if permission_mode is not None:
            body["permission_mode"] = permission_mode
        if model is not None:
            body["model"] = model

        if stream:
            resp = self._http.stream("POST", f"/tasks/{task_id}/runs", json=body)
            return RunStream(resp)

        resp = self._http.request("POST", f"/tasks/{task_id}/runs", json=body)
        return Run.from_dict(resp.json())

    def run_and_wait(
        self,
        task_id: int,
        *,
        user_id: str | None = None,
        metadata: dict | None = None,
        memory: bool = True,
        history: bool = True,
        task_setup_tools: bool = True,
        feedback: bool = True,
        human_in_the_loop: bool | None = None,
        permission_mode: str | None = None,
        model: str | None = None,
        on_approval: Callable[[PermissionRequest], str] | None = None,
        on_question: Callable[[PermissionRequest], dict[str, str]] | None = None,
        poll_interval: float = 2.0,
        poll_timeout: float = 300.0,
    ) -> Run:
        """Execute a task and wait for completion. Returns the finished Run.

        Pass on_approval= and on_question= to handle human-in-the-loop pauses inline.
        """
        run = self.run(
            task_id,
            stream=False,
            user_id=user_id,
            metadata=metadata,
            memory=memory,
            history=history,
            task_setup_tools=task_setup_tools,
            feedback=feedback,
            human_in_the_loop=human_in_the_loop,
            permission_mode=permission_mode,
            model=model,
        )
        from .runs import Runs

        return Runs(self._http).wait(
            cast(Run, run).id,
            on_approval=on_approval,
            on_question=on_question,
            interval=poll_interval,
            timeout=poll_timeout,
        )

    def delete(self, task_id: int, *, user_id: str | None = None) -> None:
        """Archive a task. Pass user_id to scope to one end-user (404 on mismatch)."""
        self._http.request("DELETE", f"/tasks/{task_id}", params=_build_params(user_id=user_id))

    def enable_webhook(self, task_id: int) -> TeammateWebhook:
        """Enable (or rotate) the task's webhook trigger. Returns the URL (shown once).

        Calling again generates a fresh token, invalidating the previous URL —
        use this to rotate a leaked webhook URL.
        """
        resp = self._http.request("POST", f"/tasks/{task_id}/webhook")
        return TeammateWebhook.from_dict(resp.json())

    def disable_webhook(self, task_id: int) -> None:
        """Disable the task's webhook trigger. POSTs to the old URL stop starting runs."""
        self._http.request("DELETE", f"/tasks/{task_id}/webhook")

    # ── Lessons (what the task's agent has learned) ──────────────────────

    def lessons(self, task_id: int) -> LessonList:
        """List the lessons this task's agent has saved for future runs."""
        resp = self._http.request("GET", f"/tasks/{task_id}/lessons")
        return LessonList.from_dict(resp.json())

    def delete_lesson(self, task_id: int, lesson_id: str) -> LessonList:
        """Delete one saved lesson; returns the remaining lessons."""
        resp = self._http.request("DELETE", f"/tasks/{task_id}/lessons/{lesson_id}")
        return LessonList.from_dict(resp.json())

    def clear_lessons(self, task_id: int) -> LessonList:
        """Clear all saved lessons for a task. Returns the now-empty list."""
        resp = self._http.request(
            "POST", f"/tasks/{task_id}/lessons:clear", params={"confirm": "true"}
        )
        return LessonList.from_dict(resp.json())
