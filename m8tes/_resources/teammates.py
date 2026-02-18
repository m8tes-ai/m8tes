"""Teammates resource — CRUD for agent personas."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._types import EmailInbox, SyncPage, Teammate, TeammateWebhook
from ._utils import _build_params

_list = list  # preserve builtin; shadowed by .list() method

if TYPE_CHECKING:
    from .._http import HTTPClient


class Teammates:
    """client.teammates — agent persona CRUD."""

    def __init__(self, http: HTTPClient):
        self._http = http

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

    def list(
        self,
        *,
        user_id: str | None = None,
        limit: int = 20,
        starting_after: int | None = None,
    ) -> SyncPage[Teammate]:
        params = _build_params(user_id=user_id, limit=limit, starting_after=starting_after)
        resp = self._http.request("GET", "/teammates", params=params)
        body = resp.json()

        def _fetch_next(**kw: object) -> SyncPage[Teammate]:
            return self.list(user_id=user_id, **kw)  # type: ignore[arg-type]

        return SyncPage(
            data=[Teammate.from_dict(d) for d in body["data"]],
            has_more=body["has_more"],
            _fetch_next=_fetch_next,
        )

    def get(self, teammate_id: int) -> Teammate:
        resp = self._http.request("GET", f"/teammates/{teammate_id}")
        return Teammate.from_dict(resp.json())

    def update(
        self,
        teammate_id: int,
        *,
        name: str | None = None,
        instructions: str | None = None,
        tools: _list[str] | None = None,
        role: str | None = None,
        goals: str | None = None,
        metadata: dict | None = None,
        allowed_senders: _list[str] | None = None,
    ) -> Teammate:
        body: dict = {}
        if name is not None:
            body["name"] = name
        if instructions is not None:
            body["instructions"] = instructions
        if tools is not None:
            body["tools"] = tools
        if role is not None:
            body["role"] = role
        if goals is not None:
            body["goals"] = goals
        if metadata is not None:
            body["metadata"] = metadata
        if allowed_senders is not None:
            body["allowed_senders"] = allowed_senders
        resp = self._http.request("PATCH", f"/teammates/{teammate_id}", json=body)
        return Teammate.from_dict(resp.json())

    def delete(self, teammate_id: int) -> None:
        self._http.request("DELETE", f"/teammates/{teammate_id}")

    def enable_webhook(self, teammate_id: int) -> TeammateWebhook:
        """Enable webhook trigger on a teammate. Returns the webhook URL (shown once)."""
        resp = self._http.request("POST", f"/teammates/{teammate_id}/webhook")
        return TeammateWebhook.from_dict(resp.json())

    def disable_webhook(self, teammate_id: int) -> None:
        """Disable webhook trigger on a teammate."""
        self._http.request("DELETE", f"/teammates/{teammate_id}/webhook")

    def enable_email_inbox(self, teammate_id: int) -> EmailInbox:
        """Enable email inbox on a teammate. Returns the email address."""
        resp = self._http.request("POST", f"/teammates/{teammate_id}/email-inbox")
        return EmailInbox.from_dict(resp.json())

    def disable_email_inbox(self, teammate_id: int) -> None:
        """Disable email inbox on a teammate."""
        self._http.request("DELETE", f"/teammates/{teammate_id}/email-inbox")
