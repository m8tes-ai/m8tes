"""Runs resource — execute agents and stream results."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._streaming import RunStream
from .._types import Run

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

        if stream:
            resp = self._http.stream("POST", "/runs", json=body)
            return RunStream(resp)

        resp = self._http.request("POST", "/runs", json=body)
        return Run.from_dict(resp.json())

    def list(self, *, teammate_id: int | None = None, user_id: str | None = None) -> list[Run]:
        params = {}
        if teammate_id is not None:
            params["teammate_id"] = teammate_id
        if user_id is not None:
            params["user_id"] = user_id
        resp = self._http.request("GET", "/runs", params=params)
        return [Run.from_dict(d) for d in resp.json()]

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
