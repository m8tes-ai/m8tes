"""Runs resource — execute agents and stream results."""

from __future__ import annotations

from collections.abc import Generator
from typing import TYPE_CHECKING, Any

from .._streaming import RunStream
from .._types import PermissionRequest, Run, RunFile, SyncPage
from ._utils import _build_params

_list = list  # preserve builtin; shadowed by .list() method

if TYPE_CHECKING:
    from .._http import HTTPClient


class Runs:
    """client.runs — execute agents, stream events, manage runs."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def create(
        self,
        *,
        message: str,
        teammate_id: int | None = None,
        tools: list[str] | None = None,
        stream: bool = True,
        name: str | None = None,
        instructions: str | None = None,
        user_id: str | None = None,
        metadata: dict | None = None,
        memory: bool = True,
        history: bool = True,
        ask_user: bool = True,
        permission_mode: str = "autonomous",
    ) -> RunStream | Run:
        """Create and execute a run.

        With stream=True (default): returns iterable RunStream of events.
        With stream=False: returns Run immediately (status="running").
            Poll GET /runs/{id} until status is terminal to get output.

        Set ask_user=False to prevent the agent from asking clarifying questions.
        """
        body: dict = {"message": message, "stream": stream}
        if teammate_id is not None:
            body["teammate_id"] = teammate_id
        if tools is not None:
            body["tools"] = tools
        if name is not None:
            body["name"] = name
        if instructions is not None:
            body["instructions"] = instructions
        if user_id is not None:
            body["user_id"] = user_id
        if metadata is not None:
            body["metadata"] = metadata
        body["memory"] = memory
        body["history"] = history
        if not ask_user:
            body["ask_user"] = False
        if permission_mode != "autonomous":
            body["permission_mode"] = permission_mode

        if stream:
            resp = self._http.stream("POST", "/runs", json=body)
            return RunStream(resp)

        resp = self._http.request("POST", "/runs", json=body)
        return Run.from_dict(resp.json())

    def poll(self, run_id: int, *, interval: float = 2.0, timeout: float = 300.0) -> Run:
        """Poll until the run reaches a terminal status. Returns the completed Run."""
        import time as _time

        from .._exceptions import APIError

        _TERMINAL = {"completed", "failed", "cancelled"}
        deadline = _time.monotonic() + timeout
        while True:
            try:
                run = self.get(run_id)
            except APIError:
                if _time.monotonic() >= deadline:
                    raise TimeoutError(f"Run {run_id} did not complete within {timeout}s") from None
                _time.sleep(interval)
                continue
            if run.status in _TERMINAL:
                return run
            if _time.monotonic() >= deadline:
                raise TimeoutError(f"Run {run_id} did not complete within {timeout}s")
            _time.sleep(interval)

    def create_and_wait(
        self,
        *,
        message: str,
        teammate_id: int | None = None,
        tools: list[str] | None = None,
        name: str | None = None,
        instructions: str | None = None,
        user_id: str | None = None,
        metadata: dict | None = None,
        memory: bool = True,
        history: bool = True,
        ask_user: bool = True,
        permission_mode: str = "autonomous",
        poll_interval: float = 2.0,
        poll_timeout: float = 300.0,
    ) -> Run:
        """Create a run and poll until it completes. Returns the finished Run."""
        run = self.create(
            message=message,
            teammate_id=teammate_id,
            tools=tools,
            stream=False,
            name=name,
            instructions=instructions,
            user_id=user_id,
            metadata=metadata,
            memory=memory,
            history=history,
            ask_user=ask_user,
            permission_mode=permission_mode,
        )
        assert isinstance(run, Run)
        return self.poll(run.id, interval=poll_interval, timeout=poll_timeout)

    def reply_and_wait(
        self,
        run_id: int,
        *,
        message: str,
        poll_interval: float = 2.0,
        poll_timeout: float = 300.0,
    ) -> Run:
        """Send a follow-up and poll until it completes. Returns the finished Run."""
        run = self.reply(run_id, message=message, stream=False)
        assert isinstance(run, Run)
        return self.poll(run.id, interval=poll_interval, timeout=poll_timeout)

    def stream_text(
        self,
        *,
        message: str,
        teammate_id: int | None = None,
        tools: list[str] | None = None,
        name: str | None = None,
        instructions: str | None = None,
        user_id: str | None = None,
        metadata: dict | None = None,
        memory: bool = True,
        history: bool = True,
        ask_user: bool = True,
        permission_mode: str = "autonomous",
    ) -> Generator[str, None, None]:
        """Create a streaming run and yield only text delta strings.

        Usage:
            for chunk in client.runs.stream_text(message="Summarize news"):
                print(chunk, end="", flush=True)
        """
        from ..streaming import StreamEventType

        stream = self.create(
            message=message,
            teammate_id=teammate_id,
            tools=tools,
            stream=True,
            name=name,
            instructions=instructions,
            user_id=user_id,
            metadata=metadata,
            memory=memory,
            history=history,
            ask_user=ask_user,
            permission_mode=permission_mode,
        )
        assert isinstance(stream, RunStream)
        with stream:
            for event in stream:
                if event.type == StreamEventType.TEXT_DELTA:
                    yield event.raw.get("textDelta", "")

    def list(
        self,
        *,
        teammate_id: int | None = None,
        user_id: str | None = None,
        status: str | None = None,
        limit: int = 20,
        starting_after: int | None = None,
    ) -> SyncPage[Run]:
        params = _build_params(
            teammate_id=teammate_id,
            user_id=user_id,
            status=status,
            limit=limit,
            starting_after=starting_after,
        )
        resp = self._http.request("GET", "/runs", params=params)
        body = resp.json()

        def _fetch_next(**kw: object) -> SyncPage[Run]:
            return self.list(teammate_id=teammate_id, user_id=user_id, status=status, **kw)  # type: ignore[arg-type]

        return SyncPage(
            data=[Run.from_dict(d) for d in body["data"]],
            has_more=body["has_more"],
            _fetch_next=_fetch_next,
        )

    def get(self, run_id: int) -> Run:
        resp = self._http.request("GET", f"/runs/{run_id}")
        return Run.from_dict(resp.json())

    def reply(
        self,
        run_id: int,
        *,
        message: str,
        stream: bool = True,
    ) -> RunStream | Run:
        """Follow-up message on an existing run. Creates a new run ID.

        With stream=True (default): returns iterable RunStream of events.
        With stream=False: returns Run immediately (status="running").
            Poll GET /runs/{id} until status is terminal to get output.
        """
        body = {"message": message, "stream": stream}
        if stream:
            resp = self._http.stream("POST", f"/runs/{run_id}/reply", json=body)
            return RunStream(resp)
        resp = self._http.request("POST", f"/runs/{run_id}/reply", json=body)
        return Run.from_dict(resp.json())

    def cancel(self, run_id: int) -> Run:
        resp = self._http.request("POST", f"/runs/{run_id}/cancel")
        return Run.from_dict(resp.json())

    def permissions(self, run_id: int) -> _list[PermissionRequest]:
        """List tool permission requests for a run."""
        resp = self._http.request("GET", f"/runs/{run_id}/permissions")
        return [PermissionRequest.from_dict(d) for d in resp.json()]

    def answer(self, run_id: int, *, answers: dict[str, str]) -> dict[str, Any]:
        """Submit an answer to an agent's AskUserQuestion.

        Use this when the run is paused waiting for user input (AskUserQuestion).
        The answers dict maps question text to the selected option label.
        """
        resp = self._http.request("POST", f"/runs/{run_id}/answer", json={"answers": answers})
        result: dict[str, Any] = resp.json()
        return result

    def approve(
        self,
        run_id: int,
        *,
        request_id: str,
        decision: str = "allow",
        remember: bool = False,
    ) -> PermissionRequest:
        """Approve or deny a pending tool permission request."""
        body = {"request_id": request_id, "decision": decision, "remember": remember}
        resp = self._http.request("POST", f"/runs/{run_id}/approve", json=body)
        return PermissionRequest.from_dict(resp.json())

    def list_files(self, run_id: int) -> _list[RunFile]:
        """List files generated by a run."""
        resp = self._http.request("GET", f"/runs/{run_id}/files")
        return [RunFile.from_dict(f) for f in resp.json()]

    def download_file(self, run_id: int, filename: str) -> bytes:
        """Download a file generated by a run. Returns raw file bytes."""
        resp = self._http.request("GET", f"/runs/{run_id}/files/{filename}/download")
        return resp.content
