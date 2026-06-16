"""MCP servers resource — register your own REST endpoints as custom agent tools.

Each server exposes one or more typed REST endpoints (``tool_defs``) that the agent calls
by name. Egress happens server-side, IP-pinned, with your secret injected and never shown
to the agent. Attach a server to a teammate by passing its ``slug`` in ``tools=[...]``:

    srv = client.mcp_servers.create(
        name="acme billing", url="https://api.acme.com/v1",
        auth_type="bearer", secret="sk-...",
        tool_defs=[{"name": "get_invoice", "method": "GET", "path": "/invoices/{id}"}],
    )
    client.teammates.create(name="ops", tools=[srv.slug])
"""

from __future__ import annotations

import builtins
from typing import TYPE_CHECKING, Any

from .._types import McpServer

if TYPE_CHECKING:
    from .._http import HTTPClient

# Sentinel so update() can distinguish "omit" from "explicitly set to None" (e.g. clear secret).
_UNSET: Any = object()


class McpServers:
    """client.mcp_servers — CRUD for user-defined custom tool servers."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def create(
        self,
        *,
        name: str,
        url: str,
        tool_defs: builtins.list[dict[str, Any]],
        auth_type: str = "none",
        auth_config: dict[str, Any] | None = None,
        secret: str | None = None,
        description: str | None = None,
        user_id: str | None = None,
    ) -> McpServer:
        """Register a custom tool server. ``auth_type`` is one of none/bearer/
        custom_header/api_key_in_url/oauth_token; ``secret`` is write-only."""
        body: dict[str, Any] = {
            "name": name,
            "url": url,
            "tool_defs": tool_defs,
            "auth_type": auth_type,
            "auth_config": auth_config or {},
        }
        if secret is not None:
            body["secret"] = secret
        if description is not None:
            body["description"] = description
        if user_id is not None:
            body["user_id"] = user_id
        resp = self._http.request("POST", "/mcp-servers", json=body)
        return McpServer.from_dict(resp.json())

    def list(self, *, user_id: str | None = None) -> builtins.list[McpServer]:
        params = {"user_id": user_id} if user_id else None
        resp = self._http.request("GET", "/mcp-servers", params=params)
        return [McpServer.from_dict(d) for d in resp.json()["data"]]

    def get(self, server_id: int, *, user_id: str | None = None) -> McpServer:
        params = {"user_id": user_id} if user_id else None
        resp = self._http.request("GET", f"/mcp-servers/{server_id}", params=params)
        return McpServer.from_dict(resp.json())

    def update(
        self,
        server_id: int,
        *,
        name: str | None = None,
        url: str | None = None,
        auth_type: str | None = None,
        auth_config: dict[str, Any] | None = None,
        secret: Any = _UNSET,
        tool_defs: builtins.list[dict[str, Any]] | None = None,
        description: str | None = None,
        status: str | None = None,
        user_id: str | None = None,
    ) -> McpServer:
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if url is not None:
            body["url"] = url
        if auth_type is not None:
            body["auth_type"] = auth_type
        if auth_config is not None:
            body["auth_config"] = auth_config
        if secret is not _UNSET:
            body["secret"] = secret  # None clears the stored secret
        if tool_defs is not None:
            body["tool_defs"] = tool_defs
        if description is not None:
            body["description"] = description
        if status is not None:
            body["status"] = status
        params = {"user_id": user_id} if user_id else None
        resp = self._http.request("PATCH", f"/mcp-servers/{server_id}", json=body, params=params)
        return McpServer.from_dict(resp.json())

    def delete(self, server_id: int, *, user_id: str | None = None) -> None:
        params = {"user_id": user_id} if user_id else None
        self._http.request("DELETE", f"/mcp-servers/{server_id}", params=params)
