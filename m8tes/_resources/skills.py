"""Skills resource — author custom Agent Skills (markdown SKILL.md playbooks).

A skill is a reusable playbook the agent loads on demand at run start: a short
``description`` (when to use it) plus a markdown ``body`` (the steps). Scope mirrors
memory — ``account`` (every Mate) or ``teammate`` (one Mate, via ``teammate_id``):

    client.skills.create(
        name="acme refund playbook",
        description="How to process an Acme refund end-to-end.",
        body="# Steps\\n1. Pull the order in Stripe\\n2. ...",
    )
"""

from __future__ import annotations

import builtins
from typing import TYPE_CHECKING, Any

from .._types import Skill

if TYPE_CHECKING:
    from .._http import HTTPClient


class Skills:
    """client.skills — CRUD for user-authored Agent Skills."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def create(
        self,
        *,
        name: str,
        description: str,
        body: str,
        scope: str = "account",
        teammate_id: int | None = None,
        user_id: str | None = None,
    ) -> Skill:
        """Author a skill. ``scope`` is "account" (all Mates) or "teammate" (requires
        ``teammate_id``). The slug is derived from ``name`` server-side."""
        payload: dict[str, Any] = {
            "name": name,
            "description": description,
            "body": body,
            "scope": scope,
        }
        if teammate_id is not None:
            payload["teammate_id"] = teammate_id
        if user_id is not None:
            payload["user_id"] = user_id
        resp = self._http.request("POST", "/skills", json=payload)
        return Skill.from_dict(resp.json())

    def list(self, *, user_id: str | None = None) -> builtins.list[Skill]:
        params = {"user_id": user_id} if user_id else None
        resp = self._http.request("GET", "/skills", params=params)
        return [Skill.from_dict(d) for d in resp.json()["data"]]

    def get(self, skill_id: int, *, user_id: str | None = None) -> Skill:
        params = {"user_id": user_id} if user_id else None
        resp = self._http.request("GET", f"/skills/{skill_id}", params=params)
        return Skill.from_dict(resp.json())

    def update(
        self,
        skill_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
        body: str | None = None,
        status: str | None = None,
        user_id: str | None = None,
    ) -> Skill:
        """Patch a skill. Omitted fields are unchanged; ``status`` is "active"/"disabled"."""
        payload: dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        if description is not None:
            payload["description"] = description
        if body is not None:
            payload["body"] = body
        if status is not None:
            payload["status"] = status
        params = {"user_id": user_id} if user_id else None
        resp = self._http.request("PATCH", f"/skills/{skill_id}", json=payload, params=params)
        return Skill.from_dict(resp.json())

    def delete(self, skill_id: int, *, user_id: str | None = None) -> None:
        params = {"user_id": user_id} if user_id else None
        self._http.request("DELETE", f"/skills/{skill_id}", params=params)
