"""Tests for new DX helper functions: runs.wait(), apps.is_connected(),
apps.connect() api_key support, tasks.run_and_wait(), PermissionRequest properties,
RunStream helpers (run_id, iter_text), and App.needs_oauth."""

import io
import json

import pytest
import responses

from m8tes._http import HTTPClient
from m8tes._resources.apps import Apps
from m8tes._resources.runs import Runs
from m8tes._resources.tasks import Tasks
from m8tes._streaming import RunStream
from m8tes._types import App, AppConnectionResult, PermissionRequest, Run

BASE = "https://api.test/v2"

RUN_RUNNING = {"id": 1, "status": "running"}
RUN_APPROVAL = {"id": 1, "status": "awaiting_approval"}
RUN_DONE = {"id": 1, "status": "completed", "output": "Done"}

PERMISSION_TOOL = {
    "request_id": "req_1",
    "tool_name": "gmail",
    "tool_input": {"query": "inbox"},
    "status": "pending",
    "created_at": "",
    "resolved_at": None,
}

PERMISSION_QUESTION = {
    "request_id": "req_2",
    "tool_name": "AskUserQuestion",
    "tool_input": {
        "questions": [
            {
                "question": "Which segment?",
                "header": "Segment",
                "multiSelect": False,
                "options": [{"label": "enterprise"}, {"label": "smb"}],
            }
        ]
    },
    "status": "pending",
    "created_at": "",
    "resolved_at": None,
}

PERMISSION_PLAN = {
    "request_id": "req_3",
    "tool_name": "AskUserQuestion",
    "tool_input": {
        "questions": [
            {
                "question": "1. Check Stripe\n2. Post to Slack\n3. Update spreadsheet",
                "header": "Plan Approval",
                "multiSelect": False,
                "options": [{"label": "Approve"}, {"label": "Revise"}],
            }
        ]
    },
    "status": "pending",
    "created_at": "",
    "resolved_at": None,
}


@pytest.fixture
def http():
    return HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)


# ── PermissionRequest properties ─────────────────────────────────────────────


class TestPermissionRequestProperties:
    def test_is_plan_approval_true(self):
        req = PermissionRequest.from_dict(PERMISSION_PLAN)
        assert req.is_plan_approval is True

    def test_is_plan_approval_false_for_tool(self):
        req = PermissionRequest.from_dict(PERMISSION_TOOL)
        assert req.is_plan_approval is False

    def test_is_plan_approval_false_for_question(self):
        """Regular AskUserQuestion is not a plan approval."""
        req = PermissionRequest.from_dict(PERMISSION_QUESTION)
        assert req.is_plan_approval is False

    def test_plan_text_returns_question_text(self):
        req = PermissionRequest.from_dict(PERMISSION_PLAN)
        assert req.plan_text == "1. Check Stripe\n2. Post to Slack\n3. Update spreadsheet"

    def test_plan_text_none_for_non_plan(self):
        req = PermissionRequest.from_dict(PERMISSION_TOOL)
        assert req.plan_text is None

    def test_plan_text_none_for_regular_question(self):
        req = PermissionRequest.from_dict(PERMISSION_QUESTION)
        assert req.plan_text is None

    def test_is_plan_approval_no_tool_input(self):
        req = PermissionRequest(
            request_id="r",
            tool_name="AskUserQuestion",
            tool_input=None,
            status="pending",
            created_at="",
            resolved_at=None,
        )
        assert req.is_plan_approval is False
        assert req.plan_text is None


# ── runs.wait() ───────────────────────────────────────────────────────────────


class TestRunsWait:
    @responses.activate
    def test_already_completed(self, http):
        responses.add(responses.GET, f"{BASE}/runs/1", json=RUN_DONE)
        run = Runs(http).wait(1, interval=0.01)
        assert run.status == "completed"

    @responses.activate
    def test_waits_through_running(self, http):
        responses.add(responses.GET, f"{BASE}/runs/1", json=RUN_RUNNING)
        responses.add(responses.GET, f"{BASE}/runs/1", json=RUN_DONE)
        run = Runs(http).wait(1, interval=0.01)
        assert run.status == "completed"
        assert len(responses.calls) == 2

    @responses.activate
    def test_handles_tool_approval_via_callback(self, http):
        responses.add(responses.GET, f"{BASE}/runs/1", json=RUN_APPROVAL)
        responses.add(responses.GET, f"{BASE}/runs/1/permissions", json=[PERMISSION_TOOL])
        responses.add(
            responses.POST, f"{BASE}/runs/1/approve", json={**PERMISSION_TOOL, "status": "approved"}
        )
        responses.add(responses.GET, f"{BASE}/runs/1", json=RUN_DONE)

        decisions = []

        def on_approval(req: PermissionRequest) -> str:
            decisions.append(req.tool_name)
            return "allow"

        run = Runs(http).wait(1, on_approval=on_approval, interval=0.01)
        assert run.status == "completed"
        assert decisions == ["gmail"]
        body = json.loads(responses.calls[2].request.body)
        assert body == {"request_id": "req_1", "decision": "allow", "remember": False}

    @responses.activate
    def test_handles_ask_user_question_via_callback(self, http):
        responses.add(responses.GET, f"{BASE}/runs/1", json=RUN_APPROVAL)
        responses.add(responses.GET, f"{BASE}/runs/1/permissions", json=[PERMISSION_QUESTION])
        responses.add(responses.POST, f"{BASE}/runs/1/answer", json={"status": "ok"})
        responses.add(responses.GET, f"{BASE}/runs/1", json=RUN_DONE)

        def on_question(req: PermissionRequest) -> dict:
            return {"Which segment?": "enterprise"}

        run = Runs(http).wait(1, on_question=on_question, interval=0.01)
        assert run.status == "completed"
        body = json.loads(responses.calls[2].request.body)
        assert body == {"answers": {"Which segment?": "enterprise"}}

    @responses.activate
    def test_raises_without_on_approval_callback(self, http):
        responses.add(responses.GET, f"{BASE}/runs/1", json=RUN_APPROVAL)
        responses.add(responses.GET, f"{BASE}/runs/1/permissions", json=[PERMISSION_TOOL])

        with pytest.raises(RuntimeError, match="on_approval="):
            Runs(http).wait(1, interval=0.01)

    @responses.activate
    def test_raises_without_on_question_callback(self, http):
        responses.add(responses.GET, f"{BASE}/runs/1", json=RUN_APPROVAL)
        responses.add(responses.GET, f"{BASE}/runs/1/permissions", json=[PERMISSION_QUESTION])

        with pytest.raises(RuntimeError, match="on_question="):
            Runs(http).wait(1, interval=0.01)

    @responses.activate
    def test_timeout(self, http):
        responses.add(responses.GET, f"{BASE}/runs/1", json=RUN_RUNNING)
        with pytest.raises(TimeoutError):
            Runs(http).wait(1, interval=0.01, timeout=0.05)

    @staticmethod
    def _gate_refusal(status, error_code, message):
        details = {"error_code": error_code} if error_code else {}
        return {
            "status": status,
            "json": {"error": {"message": message, "code": status, "details": details}},
        }

    @pytest.mark.parametrize(
        ("status", "error_code"),
        [(404, "gate_cancelled"), (409, "run_not_active")],
    )
    @responses.activate
    def test_gate_that_dies_mid_wait_does_not_abort_the_wait(
        self, http, caplog, status, error_code
    ):
        """A gate that dies HARMLESSLY between the list and the approve must not sink wait().

        Nothing the caller asked for was contradicted: the gate was cancelled, or the
        run finished under it. wait() owes the caller the RUN's outcome, not the gate's,
        so it keeps polling and returns the real result — logged, never silent.
        """
        responses.add(responses.GET, f"{BASE}/runs/1", json=RUN_APPROVAL)
        responses.add(responses.GET, f"{BASE}/runs/1/permissions", json=[PERMISSION_TOOL])
        responses.add(
            responses.POST,
            f"{BASE}/runs/1/approve",
            **self._gate_refusal(status, error_code, f"Permission request req_1 is {error_code}"),
        )
        responses.add(responses.GET, f"{BASE}/runs/1", json=RUN_DONE)

        run = Runs(http).wait(1, on_approval=lambda req: "allow", interval=0.01)

        assert run.status == "completed"
        assert "req_1" in caplog.text and error_code in caplog.text

    @responses.activate
    def test_wait_propagates_a_decision_another_approver_contradicted(self, http):
        """THE regression this whole PR exists to prevent, one layer up.

        wait() lists a pending gate, the callback says "deny", and another approver
        ALLOWS it concurrently. The tool then runs and the run completes. If wait()
        swallowed that 404 it would hand back a completed run to a caller who believes
        they blocked the tool that just executed — a false confirmation identical in
        kind to the 200 this PR removed from the endpoint, and strictly worse because
        it is silent. An opposite decision must reach the caller.
        """
        from m8tes._exceptions import NotFoundError

        responses.add(responses.GET, f"{BASE}/runs/1", json=RUN_APPROVAL)
        responses.add(responses.GET, f"{BASE}/runs/1/permissions", json=[PERMISSION_TOOL])
        responses.add(
            responses.POST,
            f"{BASE}/runs/1/approve",
            **self._gate_refusal(
                404,
                "gate_resolved_otherwise",
                "Permission request req_1 is allowed and cannot be denied",
            ),
        )
        responses.add(responses.GET, f"{BASE}/runs/1", json=RUN_DONE)

        with pytest.raises(NotFoundError, match="cannot be denied") as exc:
            Runs(http).wait(1, on_approval=lambda req: "deny", interval=0.01)
        assert exc.value.code == "gate_resolved_otherwise"

    @responses.activate
    def test_wait_propagates_an_uncoded_refusal(self, http):
        """Fail closed: an unidentifiable refusal is treated as harmful.

        An older server (or a new refusal reason nobody taught this client about) sends
        a 404 with no `error_code`. It cannot be told apart from a contradiction, so it
        must NOT be swallowed — the allowlist is the safety boundary and silence is the
        failure mode that costs the most.
        """
        from m8tes._exceptions import NotFoundError

        responses.add(responses.GET, f"{BASE}/runs/1", json=RUN_APPROVAL)
        responses.add(responses.GET, f"{BASE}/runs/1/permissions", json=[PERMISSION_TOOL])
        responses.add(
            responses.POST,
            f"{BASE}/runs/1/approve",
            **self._gate_refusal(404, None, "Permission request not found or already resolved"),
        )
        responses.add(responses.GET, f"{BASE}/runs/1", json=RUN_DONE)

        with pytest.raises(NotFoundError):
            Runs(http).wait(1, on_approval=lambda req: "allow", interval=0.01)

    @responses.activate
    def test_deny_reason_rides_the_request_body(self, http):
        """The optional steering must reach the wire — and stay OFF it when not given,
        so an older backend never sees an unknown field."""
        responses.add(
            responses.POST,
            f"{BASE}/runs/1/approve",
            json={**PERMISSION_TOOL, "status": "denied"},
        )
        Runs(http).approve(
            1, request_id="req_1", decision="deny", reason="use the staging board instead"
        )
        body = json.loads(responses.calls[0].request.body)
        assert body["reason"] == "use the staging board instead"

        responses.add(
            responses.POST,
            f"{BASE}/runs/1/approve",
            json={**PERMISSION_TOOL, "status": "denied"},
        )
        Runs(http).approve(1, request_id="req_1", decision="deny")
        assert "reason" not in json.loads(responses.calls[1].request.body)

    @responses.activate
    def test_approve_surfaces_resumed_false(self, http):
        """'allowed' is not 'running again' — the SDK must carry the resume signal."""
        responses.add(
            responses.POST,
            f"{BASE}/runs/1/approve",
            json={**PERMISSION_TOOL, "status": "allowed", "resumed": False},
        )
        req = Runs(http).approve(1, request_id="req_1", decision="allow")
        assert req.status == "allowed"
        assert req.resumed is False

    @responses.activate
    def test_approve_surfaces_a_refused_remember(self, http):
        """'allowed' is not 'always allowed' — the SDK must carry the persist signal.

        The backend refuses to store an always-allow policy for a force-gated or
        comma-carrying tool and reports remembered=false; dropping the field here
        would make the SDK confirm a preapproval that was never stored.
        """
        responses.add(
            responses.POST,
            f"{BASE}/runs/1/approve",
            json={**PERMISSION_TOOL, "status": "allowed", "remembered": False},
        )
        req = Runs(http).approve(1, request_id="req_1", decision="allow", remember=True)
        assert req.status == "allowed"
        assert req.remembered is False
        # And an older server that sends no field parses as None, never False.
        responses.add(
            responses.POST,
            f"{BASE}/runs/1/approve",
            json={**PERMISSION_TOOL, "status": "allowed"},
        )
        assert Runs(http).approve(1, request_id="req_1", decision="allow").remembered is None

    @responses.activate
    def test_approve_surfaces_a_dead_gate_to_a_direct_caller(self, http):
        """approve() itself must still raise — only wait()'s poll loop tolerates it."""
        from m8tes._exceptions import NotFoundError

        responses.add(
            responses.POST,
            f"{BASE}/runs/1/approve",
            status=404,
            json={
                "error": {
                    "message": "Permission request req_1 is cancelled and cannot be approved",
                    "code": 404,
                }
            },
        )
        with pytest.raises(NotFoundError, match="cannot be approved"):
            Runs(http).approve(1, request_id="req_1", decision="allow")

    @responses.activate
    def test_skips_non_pending_permissions(self, http):
        """Already-resolved permission requests are skipped."""
        resolved = {**PERMISSION_TOOL, "status": "approved"}
        responses.add(responses.GET, f"{BASE}/runs/1", json=RUN_APPROVAL)
        responses.add(responses.GET, f"{BASE}/runs/1/permissions", json=[resolved])
        responses.add(responses.GET, f"{BASE}/runs/1", json=RUN_DONE)

        run = Runs(http).wait(1, interval=0.01)  # no callback needed — nothing pending
        assert run.status == "completed"


# ── apps.is_connected() ───────────────────────────────────────────────────────


class TestAppsIsConnected:
    @responses.activate
    def test_connected(self, http):
        responses.add(
            responses.GET,
            f"{BASE}/apps/",
            json={
                "data": [
                    {
                        "name": "gmail",
                        "connected": True,
                        "category": "email",
                        "display_name": "Gmail",
                    }
                ],
                "has_more": False,
            },
        )
        assert Apps(http).is_connected("gmail") is True

    @responses.activate
    def test_not_connected(self, http):
        responses.add(
            responses.GET,
            f"{BASE}/apps/",
            json={
                "data": [
                    {
                        "name": "gmail",
                        "connected": False,
                        "category": "email",
                        "display_name": "Gmail",
                    }
                ],
                "has_more": False,
            },
        )
        assert Apps(http).is_connected("gmail") is False

    @responses.activate
    def test_not_in_list(self, http):
        responses.add(
            responses.GET,
            f"{BASE}/apps/",
            json={"data": [], "has_more": False},
        )
        assert Apps(http).is_connected("gmail") is False

    @responses.activate
    def test_passes_user_id(self, http):
        responses.add(
            responses.GET,
            f"{BASE}/apps/",
            json={"data": [], "has_more": False},
        )
        Apps(http).is_connected("gmail", user_id="cust_1")
        assert "user_id=cust_1" in responses.calls[0].request.url


# ── apps.connect() with api_key ───────────────────────────────────────────────


class TestAppsConnect:
    @responses.activate
    def test_connect_api_key(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/apps/gemini/connect/api-key",
            json={"status": "connected", "app": "gemini"},
            status=201,
        )
        result = Apps(http).connect("gemini", api_key="AIzaSy...")
        assert isinstance(result, AppConnectionResult)
        assert result.status == "connected"
        body = json.loads(responses.calls[0].request.body)
        assert body == {"api_key": "AIzaSy..."}

    @responses.activate
    def test_connect_api_key_with_user_id(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/apps/gemini/connect/api-key",
            json={"status": "connected", "app": "gemini"},
            status=201,
        )
        Apps(http).connect("gemini", api_key="key", user_id="cust_1")
        body = json.loads(responses.calls[0].request.body)
        assert body["user_id"] == "cust_1"

    @responses.activate
    def test_connect_oauth(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/apps/gmail/connect",
            json={
                "authorization_url": "https://accounts.google.com/o/oauth2/auth",
                "connection_id": "conn_abc",
            },
            status=201,
        )
        result = Apps(http).connect("gmail", "https://myapp.com/callback")
        assert result.authorization_url.startswith("https://")
        assert result.connection_id == "conn_abc"

    def test_connect_no_args_raises(self, http):
        with pytest.raises(ValueError, match="redirect_uri="):
            Apps(http).connect("gmail")


# ── tasks.run_and_wait() ──────────────────────────────────────────────────────


class TestTasksRunAndWait:
    @responses.activate
    def test_run_and_wait_basic(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/tasks/5/runs",
            json={"id": 10, "status": "running"},
            status=201,
        )
        responses.add(
            responses.GET,
            f"{BASE}/runs/10",
            json={"id": 10, "status": "completed", "output": "Done"},
        )
        run = Tasks(http).run_and_wait(5, poll_interval=0.01)
        assert isinstance(run, Run)
        assert run.status == "completed"

    @responses.activate
    def test_run_and_wait_with_hitl(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/tasks/5/runs",
            json={"id": 10, "status": "running"},
            status=201,
        )
        responses.add(
            responses.GET, f"{BASE}/runs/10", json={"id": 10, "status": "awaiting_approval"}
        )
        responses.add(responses.GET, f"{BASE}/runs/10/permissions", json=[PERMISSION_TOOL])
        responses.add(
            responses.POST,
            f"{BASE}/runs/10/approve",
            json={**PERMISSION_TOOL, "status": "approved"},
        )
        responses.add(
            responses.GET,
            f"{BASE}/runs/10",
            json={"id": 10, "status": "completed", "output": "Done"},
        )

        run = Tasks(http).run_and_wait(
            5,
            human_in_the_loop=True,
            permission_mode="approval",
            on_approval=lambda req: "allow",
            poll_interval=0.01,
        )
        assert run.status == "completed"


# ── runs.reply_and_wait() ─────────────────────────────────────────────────────


class TestReplyAndWait:
    @responses.activate
    def test_basic(self, http):
        responses.add(
            responses.POST,
            f"{BASE}/runs/1/reply",
            json={"id": 2, "status": "running"},
            status=200,
        )
        responses.add(
            responses.GET,
            f"{BASE}/runs/2",
            json={"id": 2, "status": "completed", "output": "Done"},
        )
        run = Runs(http).reply_and_wait(1, message="follow up", poll_interval=0.01)
        assert isinstance(run, Run)
        assert run.status == "completed"

    @responses.activate
    def test_with_hitl(self, http):
        """reply → awaiting_approval → approve → completed."""
        responses.add(
            responses.POST,
            f"{BASE}/runs/1/reply",
            json={"id": 2, "status": "running"},
            status=200,
        )
        responses.add(
            responses.GET, f"{BASE}/runs/2", json={"id": 2, "status": "awaiting_approval"}
        )
        responses.add(responses.GET, f"{BASE}/runs/2/permissions", json=[PERMISSION_TOOL])
        responses.add(
            responses.POST,
            f"{BASE}/runs/2/approve",
            json={**PERMISSION_TOOL, "status": "approved"},
        )
        responses.add(
            responses.GET,
            f"{BASE}/runs/2",
            json={"id": 2, "status": "completed", "output": "Done"},
        )

        approved = []
        run = Runs(http).reply_and_wait(
            1,
            message="follow up",
            on_approval=lambda req: approved.append(req.tool_name) or "allow",  # type: ignore[func-returns-value]
            poll_interval=0.01,
        )
        assert run.status == "completed"
        assert approved == ["gmail"]


# ── runs.wait() with multiple pending permissions ─────────────────────────────


class TestRunsWaitMultiplePending:
    @responses.activate
    def test_handles_tool_and_question_in_same_pause(self, http):
        """awaiting_approval with both a tool request and a question — both resolved."""
        responses.add(responses.GET, f"{BASE}/runs/1", json=RUN_APPROVAL)
        responses.add(
            responses.GET,
            f"{BASE}/runs/1/permissions",
            json=[PERMISSION_TOOL, PERMISSION_QUESTION],
        )
        responses.add(
            responses.POST,
            f"{BASE}/runs/1/approve",
            json={**PERMISSION_TOOL, "status": "approved"},
        )
        responses.add(responses.POST, f"{BASE}/runs/1/answer", json={"status": "ok"})
        responses.add(responses.GET, f"{BASE}/runs/1", json=RUN_DONE)

        approved = []
        answered = []

        run = Runs(http).wait(
            1,
            on_approval=lambda req: approved.append(req.tool_name) or "allow",  # type: ignore[func-returns-value]
            on_question=lambda req: (
                answered.append(req.tool_name) or {"Which segment?": "enterprise"}
            ),  # type: ignore[func-returns-value]
            interval=0.01,
        )
        assert run.status == "completed"
        assert approved == ["gmail"]
        assert answered == ["AskUserQuestion"]


# ── RunStream helpers (run_id, iter_text) ─────────────────────────────────────


def _make_sse(*payloads: dict) -> io.BytesIO:
    """Build a fake SSE byte stream from a list of event dicts."""
    lines = b""
    for p in payloads:
        lines += f"data: {json.dumps(p)}\n\n".encode()
    return io.BytesIO(lines)


class _FakeResponse:
    """Minimal requests.Response stub for RunStream."""

    def __init__(self, payloads: list[dict]):
        self._buf = _make_sse(*payloads)

    def iter_lines(self, decode_unicode: bool = True):
        yield from self._buf.read().decode().splitlines()
        yield ""  # trailing blank line to flush last frame

    def close(self) -> None:
        pass


class TestRunStreamHelpers:
    def test_iter_text_yields_only_text_chunks(self):
        events = [
            {"type": "text-delta", "delta": "hello "},
            {"type": "tool-call-start", "toolName": "gmail", "toolCallId": "tc1"},
            {"type": "text-delta", "delta": "world"},
            {"type": "done"},
        ]
        stream = RunStream(_FakeResponse(events))  # type: ignore[arg-type]
        chunks = list(stream.iter_text())
        assert chunks == ["hello ", "world"]

    def test_run_id_property_set_from_metadata(self):
        events = [
            {"type": "metadata", "payload": {"run_id": 42}},
            {"type": "done"},
        ]
        stream = RunStream(_FakeResponse(events))  # type: ignore[arg-type]
        list(stream)  # consume
        assert stream.run_id == 42

    def test_run_id_none_before_metadata(self):
        stream = RunStream(_FakeResponse([]))  # type: ignore[arg-type]
        assert stream.run_id is None


# ── App.needs_oauth ───────────────────────────────────────────────────────────


class TestAppNeedsOAuth:
    def test_composio_app_needs_oauth(self):
        app = App(
            name="gmail",
            display_name="Gmail",
            category="email",
            connected=False,
            auth_type="composio",
        )
        assert app.needs_oauth is True

    def test_api_key_app_no_oauth(self):
        app = App(
            name="gemini",
            display_name="Gemini",
            category="ai",
            connected=False,
            auth_type="api_key",
        )
        assert app.needs_oauth is False


def test_permission_request_auto_resolved_parsing():
    """auto_resolved parses when present and defaults False for older backends."""
    auto = PermissionRequest.from_dict(
        {
            "request_id": "req_2",
            "tool_name": "AskUserQuestion",
            "tool_input": {"answers": {"Q?": "A (Recommended) [auto-selected]"}},
            "status": "allowed",
            "auto_resolved": True,
        }
    )
    assert auto.auto_resolved is True
    legacy = PermissionRequest.from_dict(
        {"request_id": "req_3", "tool_name": "gmail", "tool_input": None, "status": "pending"}
    )
    assert legacy.auto_resolved is False
