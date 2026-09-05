"""Tests for `m8tes.testing` — the consumer-facing offline test toolkit.

These play whole developer scenarios THROUGH the public SDK surface (client →
resource method → real HTTPClient → mock transport), because that is exactly how
a developer's own tests will use the module. If these pass, a developer's test
built the same way exercises the SDK's real request building, error mapping, and
SSE parsing — with no network, no spend, no side effects.
"""

import ast
from pathlib import Path

import pytest

from m8tes import BillingError, M8tes, RunFailedError
from m8tes._types import Run, Task, Teammate
from m8tes.streaming import DoneEvent, TextDeltaEvent
from m8tes.testing import (
    MockM8tes,
    MockTransport,
    StreamBuilder,
    agent_payload,
    error_envelope,
    page_payload,
    run_payload,
    task_payload,
)


class TestFullScenario:
    """The acceptance scenario: create an agent, stream a run, assert events."""

    def test_agent_create_then_streaming_run_success(self):
        client = MockM8tes()
        client.mock.add("POST", "/agents/", json=agent_payload(id=7, name="Ops Mate"))
        client.mock.add(
            "POST",
            "/runs/",
            stream=StreamBuilder().metadata(run_id=42).text("Hello world").done(),
        )

        agent = client.agents.create(name="Ops Mate", tools=["gmail"])
        assert isinstance(agent, Teammate)
        assert agent.id == 7

        with client.runs.create(agent_id=agent.id, message="Do X") as stream:
            events = list(stream)

        assert any(isinstance(e, TextDeltaEvent) for e in events)
        assert isinstance(events[-1], DoneEvent)
        assert stream.text == "Hello world"
        assert stream.run_id == 42
        assert not stream.has_errors

        # The transport records every call with its parsed JSON body.
        create_call, run_call = client.mock.calls
        assert (create_call.method, create_call.path) == ("POST", "/agents")
        assert create_call.json["name"] == "Ops Mate"
        assert (run_call.method, run_call.path) == ("POST", "/runs")
        assert run_call.json["message"] == "Do X"
        assert run_call.json["teammate_id"] == 7

    def test_failure_stream_raises_run_failed(self):
        client = MockM8tes()
        client.mock.add(
            "POST",
            "/runs/",
            stream=StreamBuilder()
            .metadata(run_id=9)
            .error("Sandbox quota exhausted", error_code="SANDBOX_QUOTA_EXHAUSTED")
            .done(),
        )
        with pytest.raises(RunFailedError) as exc_info:
            list(client.runs.create(agent_id=1, message="Do X", raise_on_error=True))
        assert "Sandbox quota exhausted" in str(exc_info.value)
        assert exc_info.value.details["errors"] == ["Sandbox quota exhausted"]

    def test_failure_stream_without_raise_surfaces_errors(self):
        client = MockM8tes()
        client.mock.add(
            "POST",
            "/runs/",
            stream=StreamBuilder().error("boom", error_code="RUN_FAILED").done(),
        )
        stream = client.runs.create(agent_id=1, message="Do X")
        events = list(stream)
        assert stream.has_errors
        assert stream.errors == ["boom"]
        # The semantic code rides on the raw error frame for callers that want it.
        error_frames = [e for e in events if e.raw.get("error_code")]
        assert error_frames[0].raw["error_code"] == "RUN_FAILED"

    def test_error_envelope_maps_to_typed_exception(self):
        client = MockM8tes()
        client.mock.add(
            "POST",
            "/runs/",
            status=402,
            json=error_envelope(
                "Balance depleted. Top up to run.",
                status=402,
                error_code="TOKEN_BALANCE_DEPLETED",
                details={"topup_url": "https://m8tes.ai/developer"},
            ),
        )
        with pytest.raises(BillingError) as exc_info:
            client.runs.create(agent_id=1, message="Do X", stream=False)
        exc = exc_info.value
        assert exc.status_code == 402
        assert exc.error_code == "TOKEN_BALANCE_DEPLETED"
        assert exc.details["topup_url"] == "https://m8tes.ai/developer"
        assert exc.request_id is not None

    def test_non_streaming_run_and_list(self):
        client = MockM8tes()
        client.mock.add("POST", "/runs/", json=run_payload(id=3, status="running", output=None))
        client.mock.add("GET", "/runs/", json=page_payload(run_payload(id=3)))
        run = client.runs.create(agent_id=1, message="Do X", stream=False)
        assert isinstance(run, Run)
        assert run.status == "running"
        listed = client.runs.list()
        assert [r.id for r in listed.data] == [3]
        assert listed.has_more is False


class TestTransport:
    def test_installs_on_a_plain_client(self):
        """A dev whose code builds its own M8tes can inject via install()."""
        transport = MockTransport()
        client = M8tes(api_key="m8_test", base_url="https://api.example.test/api/v2")
        transport.install(client)
        transport.add("GET", "/agents/", json=page_payload(agent_payload()))
        assert client.agents.list().data[0].name == agent_payload()["name"]

    def test_unmatched_request_raises_with_registered_routes(self):
        client = MockM8tes()
        client.mock.add("GET", "/agents/", json=page_payload())
        with pytest.raises(AssertionError, match=r"GET /agents"):
            client.tasks.list()

    def test_responses_are_consumed_in_order_then_last_repeats(self):
        client = MockM8tes()
        client.mock.add("GET", "/runs/1", json=run_payload(id=1, status="running"))
        client.mock.add("GET", "/runs/1", json=run_payload(id=1, status="completed"))
        assert client.runs.get(1).status == "running"
        assert client.runs.get(1).status == "completed"
        # Exhausted registrations repeat the last match (polling-friendly).
        assert client.runs.get(1).status == "completed"


class TestFactories:
    """Factory payloads must stay parseable by the real dataclasses."""

    def test_agent_payload_parses(self):
        agent = Teammate.from_dict(agent_payload())
        assert agent.id and agent.name and agent.status == "enabled"

    def test_run_payload_parses(self):
        run = Run.from_dict(run_payload())
        assert run.status == "completed"
        assert run.output

    def test_every_scalar_the_run_double_declares_survives_parsing(self):
        """A field the double carries must not be masked by a parser default.

        `billing_surface` was absent from the double AND unread by `from_dict`, so a
        developer testing the documented "show me my API traffic" filter offline got
        `"platform"` for every run — the same wrong answer production gave. Adding it
        to the double is only half the fix; this is the half that keeps it true as
        both sides grow.
        """
        payload = run_payload()
        run = Run.from_dict(payload)
        dropped = [
            f"{k}: double says {v!r}, parsed as {getattr(run, k, '<missing>')!r}"
            for k, v in payload.items()
            if not isinstance(v, dict | list) and getattr(run, k, object()) != v
        ]
        assert not dropped, "Run.from_dict did not read these off the double: " + "; ".join(dropped)

    def test_the_run_double_carries_the_fields_stamped_on_every_run(self):
        """Both are always present on a real response, so an offline test must see them."""
        payload = run_payload()
        assert payload["billing_surface"] and payload["channel"]

    def test_run_payload_failure_shape(self):
        run = Run.from_dict(run_payload(status="failed", error_code="TOKEN_BALANCE_DEPLETED"))
        assert run.status == "failed"
        assert run.error_code == "TOKEN_BALANCE_DEPLETED"

    def test_task_payload_parses(self):
        task = Task.from_dict(task_payload())
        assert task.id and task.instructions

    def test_overrides_apply(self):
        assert agent_payload(name="Custom")["name"] == "Custom"
        assert run_payload(id=99)["id"] == 99
        assert task_payload(name="Weekly recap")["name"] == "Weekly recap"


class TestStreamBuilder:
    def test_builds_valid_sse_bytes(self):
        body = StreamBuilder().text("Hi").done().to_bytes()
        assert body.startswith(b"data: ")
        assert b'"text-delta"' in body
        assert b"data: [DONE]" in body
        # SSE frames are separated by a blank line.
        assert b"\n\n" in body

    def test_tool_call_events(self):
        client = MockM8tes()
        client.mock.add(
            "POST",
            "/runs/",
            stream=StreamBuilder()
            .tool_call("gmail_send", arguments={"to": "a@b.c"}, result="sent")
            .done(),
        )
        stream = client.runs.create(agent_id=1, message="Send it")
        list(stream)


class TestZeroExtraDeps:
    def test_testing_module_imports_only_stdlib_requests_and_m8tes(self):
        """`m8tes.testing` ships inside the package: it must never import a
        test-only dependency (`responses`, `pytest`, ...). Parsed via ast so a
        comment can't satisfy or break it."""
        import m8tes.testing as testing_module

        source = Path(testing_module.__file__).read_text()
        allowed_roots = {"requests", "m8tes"}
        stdlib = {
            "io",
            "json",
            "uuid",
            "collections",
            "dataclasses",
            "typing",
            "urllib",
            "__future__",
        }
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                roots = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                roots = [(node.module or "m8tes").split(".")[0]] if node.level == 0 else ["m8tes"]
            else:
                continue
            for root in roots:
                assert root in allowed_roots | stdlib, f"unexpected dependency: {root}"


class TestCredentialRedaction:
    """mock.calls must never retain usable credentials (adversarial review 2026-08-16).

    MockTransport.install() mounts on a client that may hold a REAL key; recorded
    headers flow into assertions, snapshots, and CI logs.
    """

    def test_authorization_header_is_redacted_in_calls(self):
        # The documented install() path: a client built by the app under test,
        # holding what would be a REAL key in the developer's environment.
        client = M8tes(api_key="m8_live_secret_key_123", base_url="https://api.m8tes.ai/api/v2")
        mock = MockTransport().install(client)
        mock.add("GET", "/agents/7", json=agent_payload(id=7))
        client.agents.get(7)
        (call,) = mock.calls
        joined = " ".join(f"{k}={v}" for k, v in call.headers.items())
        assert "m8_live_secret_key_123" not in joined
        auth = {k.lower(): v for k, v in call.headers.items()}.get("authorization")
        assert auth == "<redacted>"


class TestQueryParamMatching:
    """Fixtures and recordings are query-aware (adversarial review 2026-08-16).

    The exploit shape: a fixture registered for /agents/7?user_id=tenant-a matched a
    request that sent NO user_id, so tenant-isolation tests could pass against code
    that dropped the scope. A fixture that names params now requires them, and
    RecordedCall carries the parsed query for assertions.
    """

    def test_scoped_fixture_rejects_unscoped_request(self):
        client = MockM8tes()
        client.mock.add("GET", "/agents/7?user_id=tenant-a", json=agent_payload(id=7))
        with pytest.raises(AssertionError, match="user_id"):
            client.agents.get(7)

    def test_scoped_fixture_matches_scoped_request_and_records_params(self):
        client = MockM8tes()
        client.mock.add("GET", "/agents/?user_id=tenant-a", json=page_payload(agent_payload(id=7)))
        client.agents.list(user_id="tenant-a")
        (call,) = client.mock.calls
        assert call.params.get("user_id") == "tenant-a"

    def test_unscoped_fixture_still_matches_any_query(self):
        client = MockM8tes()
        client.mock.add("GET", "/agents/", json=page_payload(agent_payload(id=7)))
        client.agents.list(user_id="tenant-b")
        (call,) = client.mock.calls
        assert call.params.get("user_id") == "tenant-b"
