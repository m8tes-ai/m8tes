"""Runs resource — execute agents and stream results."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._streaming import RunStream
from .._types import PermissionRequest, Run, SyncPage

if TYPE_CHECKING:
    from .._http import HTTPClient


class Runs:
    """client.runs — execute agents, stream events, manage runs."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def create(
        self,
        *,
        task: str,
        teammate_id: int | None = None,
        tools: list[str] | None = None,
        stream: bool = True,
        name: str | None = None,
        instructions: str | None = None,
        user_id: str | None = None,
        metadata: dict | None = None,
        memory: bool = True,
        history: bool = True,
        permission_mode: str = "autonomous",
    ) -> RunStream | Run:
        """Create and execute a run.

        With stream=True (default): returns iterable RunStream of events.
        With stream=False: returns Run with output after execution completes.
        """
        body: dict = {"task": task, "stream": stream}
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
        if not memory:
            body["memory"] = False
        if not history:
            body["history"] = False
        if permission_mode != "autonomous":
            body["permission_mode"] = permission_mode

        if stream:
            resp = self._http.stream("POST", "/runs", json=body)
            return RunStream(resp)

        resp = self._http.request("POST", "/runs", json=body)
        return Run.from_dict(resp.json())

    def list(self, *, teammate_id: int | None = None, user_id: str | None = None) -> SyncPage[Run]:
        params = {}
        if teammate_id is not None:
            params["teammate_id"] = teammate_id
        if user_id is not None:
            params["user_id"] = user_id
        resp = self._http.request("GET", "/runs", params=params)
        body = resp.json()
        return SyncPage(data=[Run.from_dict(d) for d in body["data"]], has_more=body["has_more"])

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
        """Follow-up message on an existing run."""
        body = {"message": message, "stream": stream}
        if stream:
            resp = self._http.stream("POST", f"/runs/{run_id}/reply", json=body)
            return RunStream(resp)
        resp = self._http.request("POST", f"/runs/{run_id}/reply", json=body)
        return Run.from_dict(resp.json())

    def cancel(self, run_id: int) -> Run:
        resp = self._http.request("POST", f"/runs/{run_id}/cancel")
        return Run.from_dict(resp.json())

    def permissions(self, run_id: int) -> list[PermissionRequest]:
        """List tool permission requests for a run."""
        resp = self._http.request("GET", f"/runs/{run_id}/permissions")
        return [PermissionRequest.from_dict(d) for d in resp.json()]

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
