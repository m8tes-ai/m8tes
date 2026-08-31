"""Offline test doubles for building against the m8tes SDK — no network, no spend.

Runs are billable and have real side effects (they post to Slack, send email, act in
your tools), so integration code needs a way to be tested without executing anything.
This module provides that: a mock transport that answers the SDK's real HTTP client
from canned fixtures, factories for realistic v2 wire payloads, an SSE stream builder
the SDK's own parser consumes, and a v2 error-envelope builder for exception paths.

Everything runs through the REAL client code — request building, retry/idempotency
logic, typed error mapping, and SSE parsing are all exercised — only the socket is
replaced. Ships with the SDK and needs nothing beyond its runtime dependencies.

Usage:
    from m8tes.testing import MockM8tes, StreamBuilder, agent_payload

    client = MockM8tes()
    client.mock.add("POST", "/agents/", json=agent_payload(id=7, name="Ops Mate"))
    client.mock.add(
        "POST", "/runs/",
        stream=StreamBuilder().metadata(run_id=42).text("Hello world").done(),
    )

    agent = client.agents.create(name="Ops Mate")
    for event in client.runs.create(agent_id=agent.id, message="Do X"):
        ...  # your event-handling code, against a canned stream

    client.mock.calls  # every request the SDK sent, with parsed JSON bodies

To inject into code that constructs its own ``M8tes``, mount a transport on the
client instead: ``MockTransport().install(client)``.

Notes:
- Responses registered for the same (method, path) are consumed in order; when
  exhausted, the last one repeats (polling-friendly).
- 429/5xx fixtures are retried by the real client, real backoff sleeps included —
  prefer 4xx fixtures for error-path tests.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import io
import json as _json
from typing import Any
from urllib.parse import parse_qsl, urlparse
import uuid

import requests
from requests.adapters import BaseAdapter
from requests.structures import CaseInsensitiveDict

from ._client import M8tes

__all__ = [
    "MockM8tes",
    "MockTransport",
    "RecordedCall",
    "StreamBuilder",
    "agent_payload",
    "error_envelope",
    "page_payload",
    "run_payload",
    "task_payload",
]

#: Base URL MockM8tes constructs with — an unroutable host, so a fixture gap can
#: never fall through to the real API.
MOCK_BASE_URL = "https://mock.m8tes.invalid/api/v2"


# ── Payload factories (v2 wire shapes) ───────────────────────────────────────────
# Dicts, not dataclasses, because a mock response IS wire JSON. Each stays parseable
# by its `_types` dataclass — pinned by tests/unit/test_testing_module.py.


def agent_payload(**overrides: Any) -> dict[str, Any]:
    """A realistic v2 agent (teammate) response payload. Override any field."""
    payload: dict[str, Any] = {
        "id": 1,
        "name": "Ops Mate",
        "instructions": "Handle ops requests end to end.",
        "tools": ["gmail"],
        "role": None,
        "goals": None,
        "user_id": None,
        "metadata": None,
        "allowed_senders": None,
        "default_permission_mode": "autonomous",
        "status": "enabled",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": None,
    }
    payload.update(overrides)
    return payload


def run_payload(**overrides: Any) -> dict[str, Any]:
    """A realistic v2 run response payload (defaults to a completed run)."""
    payload: dict[str, Any] = {
        "id": 42,
        "teammate_id": 1,
        "task_id": 10,
        "status": "completed",
        "output": "Done. Sent the weekly recap.",
        "error": None,
        "error_code": None,
        "retryable": False,
        "user_id": None,
        "metadata": None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:01:00Z",
        # Both are stamped on every real run. Omitting them let a caller test the
        # documented "show me my API traffic" filter against a double that answers
        # "platform"/None for everything — the same wrong answer the parser gave
        # while billing_surface went unread.
        "billing_surface": "platform",
        "channel": "api",
        "usage": {
            "input_tokens": 1200,
            "output_tokens": 300,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "total_tokens": 1500,
            "cost_usd": "0.012000",
        },
    }
    payload.update(overrides)
    return payload


def task_payload(**overrides: Any) -> dict[str, Any]:
    """A realistic v2 task response payload."""
    payload: dict[str, Any] = {
        "id": 10,
        "teammate_id": 1,
        "name": "weekly recap",
        "instructions": "Summarize the week and email the team.",
        "tools": ["gmail"],
        "expected_output": None,
        "goals": None,
        "user_id": None,
        "status": "enabled",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": None,
    }
    payload.update(overrides)
    return payload


def page_payload(*items: dict[str, Any], has_more: bool = False) -> dict[str, Any]:
    """A v2 list envelope (`{"data": [...], "has_more": ...}`) for list endpoints."""
    return {"data": list(items), "has_more": has_more}


def error_envelope(
    message: str,
    *,
    status: int = 400,
    type: str = "api_error",
    error_code: str | None = None,
    details: dict[str, Any] | None = None,
    request_id: str | None = None,
    doc_url: str | None = None,
) -> dict[str, Any]:
    """A v2 error envelope, as the API sends it.

    Register with the matching HTTP ``status`` and the SDK raises its real typed
    exception (402 → BillingError, 404 → NotFoundError, ...). ``error_code`` (the
    semantic code, e.g. "TOKEN_BALANCE_DEPLETED") is placed both top-level and in
    ``details`` — matching current and future backends — so ``exc.error_code`` and
    ``exc.code`` both surface it.
    """
    error: dict[str, Any] = {
        "type": type,
        "message": message,
        "code": status,
        "request_id": request_id or f"req_mock_{uuid.uuid4().hex[:12]}",
    }
    merged_details = dict(details or {})
    if error_code is not None:
        error["error_code"] = error_code
        merged_details.setdefault("error_code", error_code)
    if merged_details:
        error["details"] = merged_details
    if doc_url is not None:
        error["doc_url"] = doc_url
    return {"error": error}


# ── Streaming fixtures ───────────────────────────────────────────────────────────


class StreamBuilder:
    """Builds an SSE body the SDK's stream parser consumes. Chainable.

    Example:
        StreamBuilder().metadata(run_id=42).text("Hello").done()

    Failure stream (so you can test your error paths):
        StreamBuilder().metadata(run_id=42).error(
            "Sandbox quota exhausted", error_code="SANDBOX_QUOTA_EXHAUSTED"
        ).done()
    """

    def __init__(self) -> None:
        self._frames: list[str] = []
        self._counter = 0

    def _next_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}_{self._counter}"

    def event(self, data: dict[str, Any]) -> StreamBuilder:
        """Append a raw event frame — escape hatch for any wire shape."""
        self._frames.append(_json.dumps(data))
        return self

    def metadata(self, *, run_id: int = 1, **extra: Any) -> StreamBuilder:
        """The metadata frame carrying the run id (sets ``stream.run_id``)."""
        return self.event({"type": "metadata", "payload": {"run_id": run_id, **extra}})

    def text(self, text: str) -> StreamBuilder:
        """A complete assistant text block: text-start, one delta, text-end."""
        block_id = self._next_id("txt")
        self.event({"type": "text-start", "id": block_id})
        self.event({"type": "text-delta", "id": block_id, "delta": text})
        return self.event({"type": "text-end", "id": block_id})

    def tool_call(
        self,
        name: str,
        *,
        arguments: dict[str, Any] | None = None,
        result: Any = None,
        tool_call_id: str | None = None,
    ) -> StreamBuilder:
        """A complete tool call: start, arguments delta, end, and its result."""
        call_id = tool_call_id or self._next_id("toolu")
        self.event({"type": "tool-call-start", "toolCallId": call_id, "toolName": name})
        self.event(
            {
                "type": "tool-call-delta",
                "toolCallId": call_id,
                "delta": _json.dumps(arguments or {}),
            }
        )
        self.event({"type": "tool-call-end", "toolCallId": call_id})
        return self.event({"type": "tool-result-end", "toolCallId": call_id, "result": result})

    def error(self, message: str, *, error_code: str | None = None) -> StreamBuilder:
        """A run-level error frame. Sets ``stream.has_errors`` and, with
        ``raise_on_error=True``, makes iteration raise RunFailedError."""
        frame: dict[str, Any] = {"type": "error", "error": message}
        if error_code is not None:
            frame["error_code"] = error_code
        return self.event(frame)

    def done(self) -> StreamBuilder:
        """The terminal [DONE] marker every stream ends with."""
        self._frames.append("[DONE]")
        return self

    def to_bytes(self) -> bytes:
        """Render as SSE wire bytes (``data: <json>\\n\\n`` per frame)."""
        return b"".join(f"data: {frame}\n\n".encode() for frame in self._frames)


# ── Mock transport ───────────────────────────────────────────────────────────────


@dataclass
class RecordedCall:
    """One request the SDK sent through the mock transport."""

    method: str
    path: str  # relative to the API base, query stripped, no trailing slash
    json: Any = None  # parsed JSON body, when the request carried one
    headers: dict[str, str] = field(default_factory=dict)
    params: dict[str, str] = field(default_factory=dict)  # parsed query string


# install() mounts on a client that may hold a REAL key, and recorded headers flow
# into assertions, snapshots, and CI logs — so credential-bearing headers are
# recorded redacted, never verbatim.
_SENSITIVE_HEADERS = frozenset({"authorization", "x-api-key", "cookie", "proxy-authorization"})


def _redact_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {k: ("<redacted>" if k.lower() in _SENSITIVE_HEADERS else v) for k, v in headers.items()}


@dataclass
class _Registration:
    method: str
    path: str
    status: int
    body: bytes
    headers: dict[str, str]
    params: dict[str, str] | None = None  # None = match any query; dict = require subset
    consumed: bool = False


def _normalize(path: str) -> str:
    path = path.split("?", 1)[0]
    return path.rstrip("/") or "/"


def _parse_params(path_or_url: str) -> dict[str, str]:
    return dict(parse_qsl(urlparse(path_or_url).query))


class MockTransport(BaseAdapter):
    """A requests adapter that answers the SDK from registered fixtures.

    Mounted on the client's real session, so retries, idempotency keys, error
    mapping, and SSE parsing are the production code paths. Unmatched requests
    raise AssertionError (nothing ever reaches the network).
    """

    def __init__(self, base_path: str = "/api/v2") -> None:
        super().__init__()
        self._base_path = base_path.rstrip("/")
        self._registrations: list[_Registration] = []
        self.calls: list[RecordedCall] = []

    def install(self, client: M8tes) -> MockTransport:
        """Mount onto an existing M8tes client so every request answers from here."""
        self._base_path = urlparse(client.base_url).path.rstrip("/")
        client._http._session.mount("https://", self)
        client._http._session.mount("http://", self)
        return self

    def add(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        stream: StreamBuilder | bytes | None = None,
        status: int = 200,
        headers: dict[str, str] | None = None,
    ) -> MockTransport:
        """Register a response for ``method`` + ``path`` (as the SDK passes it,
        e.g. ``"/runs/"``). Pass ``json=`` for a JSON body or ``stream=`` (a
        StreamBuilder or raw SSE bytes) for a streaming run response.

        A query string in ``path`` makes the fixture query-aware: the request must
        carry every named parameter with the same value (extra request params are
        fine). Without one, the fixture matches any query — so a fixture written
        ``"/agents/?user_id=tenant-a"`` REQUIRES the scope, and a test whose code
        drops ``user_id`` fails instead of silently matching."""
        if stream is not None:
            body = stream.to_bytes() if isinstance(stream, StreamBuilder) else stream
            content_type = "text/event-stream"
        else:
            body = _json.dumps(json if json is not None else {}).encode()
            content_type = "application/json"
        merged_headers = {"Content-Type": content_type, **(headers or {})}
        params = _parse_params(path) or None
        self._registrations.append(
            _Registration(method.upper(), _normalize(path), status, body, merged_headers, params)
        )
        return self

    # -- adapter interface ---------------------------------------------------------

    def send(
        self,
        request: requests.PreparedRequest,
        stream: bool = False,
        timeout: Any = None,
        verify: Any = True,
        cert: Any = None,
        proxies: Any = None,
    ) -> requests.Response:
        method = (request.method or "GET").upper()
        full_path = urlparse(request.url or "").path
        rel = full_path.removeprefix(self._base_path) if self._base_path else full_path
        path = _normalize(rel)
        params = _parse_params(request.url or "")
        self.calls.append(
            RecordedCall(
                method=method,
                path=path,
                json=self._parse_body(request),
                headers=_redact_headers(request.headers),
                params=params,
            )
        )
        reg = self._match(method, path, params)
        return self._build_response(request, reg)

    def close(self) -> None:  # pragma: no cover - nothing to release
        pass

    # -- internals -----------------------------------------------------------------

    def _match(self, method: str, path: str, params: dict[str, str]) -> _Registration:
        # A query-aware fixture requires its named params on the request (subset
        # match: extra request params are fine). A path-only fixture matches any
        # query — the strictness is opt-in per fixture.
        matches = [
            r
            for r in self._registrations
            if r.method == method
            and r.path == path
            and (r.params is None or all(params.get(k) == v for k, v in r.params.items()))
        ]
        if not matches:
            routes = (
                ", ".join(
                    f"{r.method} {r.path}"
                    + ("?" + "&".join(f"{k}={v}" for k, v in r.params.items()) if r.params else "")
                    for r in self._registrations
                )
                or "none"
            )
            sent = "?" + "&".join(f"{k}={v}" for k, v in params.items()) if params else ""
            raise AssertionError(
                f"m8tes.testing: no mock response registered for {method} {path}{sent}. "
                f"Registered routes: {routes}. Register one with "
                f'mock.add("{method}", "{path}", json=...).'
            )
        for reg in matches:
            if not reg.consumed:
                reg.consumed = True
                return reg
        return matches[-1]  # exhausted: repeat the last (polling-friendly)

    @staticmethod
    def _parse_body(request: requests.PreparedRequest) -> Any:
        body = request.body
        if not body:
            return None
        if isinstance(body, bytes):
            try:
                body = body.decode("utf-8")
            except UnicodeDecodeError:
                return None  # multipart or binary — recorded as None
        try:
            return _json.loads(body)
        except (ValueError, TypeError):
            return None  # form data / file-like body — recorded as None

    @staticmethod
    def _build_response(request: requests.PreparedRequest, reg: _Registration) -> requests.Response:
        resp = requests.Response()
        resp.status_code = reg.status
        resp.headers = CaseInsensitiveDict(reg.headers)
        resp.url = request.url or ""
        resp.request = request
        resp.raw = io.BytesIO(reg.body)
        resp.encoding = "utf-8"
        return resp


class MockM8tes(M8tes):
    """An M8tes client wired to a MockTransport — the one-line way to test.

    Behaves exactly like ``M8tes`` (same resources, same typed returns, same
    exceptions); its ``mock`` attribute is the transport you register fixtures on
    and read ``.calls`` from. Construction needs no credentials and the base URL
    is unroutable, so nothing can ever hit the real API.
    """

    def __init__(self) -> None:
        super().__init__(api_key="m8_test_key", base_url=MOCK_BASE_URL)
        self.mock = MockTransport().install(self)
