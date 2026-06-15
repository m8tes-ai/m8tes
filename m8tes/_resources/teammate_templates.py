"""Teammate templates resource — read-only catalog of pre-built teammates.

The catalog is the discovery surface for `teammates.create(from_template=slug)`:
it lists each template's slug, required integrations, and seeded default tasks so
you don't have to hardcode slugs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._types import TeammateTemplate

if TYPE_CHECKING:
    from .._http import HTTPClient


class TeammateTemplates:
    """client.teammate_templates — list the pre-built teammate template catalog."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def list(self) -> list[TeammateTemplate]:
        """List all teammate templates.

        Pass a returned `.slug` to `client.teammates.create(from_template=...)`.
        """
        resp = self._http.request("GET", "/teammate-templates/")
        body = resp.json()
        items = body["data"] if isinstance(body, dict) and "data" in body else body
        return [TeammateTemplate.from_dict(d) for d in items]
