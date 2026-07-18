"""Teammate templates resource — read-only catalog of pre-built agents.

The catalog is the discovery surface for `agents.create(from_template=slug)`:
it lists each template's slug, required integrations, and seeded default tasks so
you don't have to hardcode slugs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._types import TeammateTemplate

if TYPE_CHECKING:
    from .._http import HTTPClient


class AgentTemplates:
    """client.agent_templates (alias: client.teammate_templates) — pre-built template catalog."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def list(self) -> list[TeammateTemplate]:
        """List all agent templates.

        Pass a returned `.slug` to `client.agents.create(from_template=...)`.
        """
        resp = self._http.request("GET", "/agent-templates/")
        body = resp.json()
        items = body["data"] if isinstance(body, dict) and "data" in body else body
        return [TeammateTemplate.from_dict(d) for d in items]


# Permanent back-compat alias.
TeammateTemplates = AgentTemplates
