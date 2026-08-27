"""Runs resource — execute agents and stream results."""

from __future__ import annotations

from collections.abc import Callable, Generator
import json
import logging
from typing import TYPE_CHECKING, Any, cast
import uuid

from .._http import IDEMPOTENCY_HEADER, REPLAY_HEADER, seg
from .._streaming import RunStream
from .._types import (
    PermissionMode,
    PermissionModeResponse,
    PermissionRequest,
    Run,
    RunCheck,
    RunFile,
    RunMessage,
    RunOutcome,
    RunShare,
    SyncPage,
)
from ._utils import _build_params, _resolve_agent_id

logger = logging.getLogger(__name__)

_list = list  # preserve builtin; shadowed by .list() method

# Gate refusals wait() may ride out. Mirrors the codes POST /runs/{id}/approve puts in
# `error.details.error_code` (fastapi/app/routers/v2/runs.py::approve_permission).
#
# Membership is the SAFETY boundary, so it is an allowlist, not a denylist: anything
# unrecognised — including an OLD server that sends no code at all — propagates. A
# refusal wait() cannot positively identify as harmless is treated as harmful, because
# the one it must never swallow (`gate_resolved_otherwise`: another approver decided the
# OPPOSITE way) is indistinguishable from the benign ones without this code.
#
# `run_not_active` is benign ONLY because the server raises it exclusively for a gate
# that is still OPEN on a finished run. If a contradicted decision could ever report
# `run_not_active`, a lost denial would be silently swallowed here — so that split is a
# contract, pinned server-side by
# `test_a_contradicted_decision_on_a_terminal_run_is_not_reported_as_benign`.
_BENIGN_GATE_REFUSALS = frozenset({"gate_cancelled", "run_not_active"})

# Mirrors TERMINAL_RUN_STATUSES in fastapi/app/models/run.py — the source of truth.
#
# "closed" was missing here for as long as poll()/wait() existed, and the set was
# duplicated inside each of them, so a closed run never satisfied the exit
# condition and the caller waited out the entire timeout on a run the server had
# already finished. Comparing against the TypeScript SDK could not find it: that
# one shipped the same three-element set. Only the server settles it, which is
# what test_v2_poll.py::TestTerminalStatuses::test_matches_the_server_exactly now
# does on every run. One constant, so the two helpers cannot drift apart again.
TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled", "closed"})


def idempotency_headers(key: str | None) -> dict[str, str]:
    """Headers for a run-creating POST — minting a key when the caller gave none.

    A key is ALWAYS sent. Runs are billable, so a POST that times out is otherwise
    unanswerable: retry and you may pay twice, don't and you may drop the request.
    With a key the server binds it to the run it created and replays that same run
    for every repeat, which is what lets `_http` retry these POSTs at all.

    Auto-minting costs the caller nothing: two deliberate identical runs are two
    calls, and each mints its own key. Pass `idempotency_key=` to reuse one across
    process restarts (a job runner re-driving the same unit of work).
    """
    return {IDEMPOTENCY_HEADER: key or str(uuid.uuid4())}


def _raise_if_failed(run: Run) -> None:
    """Raise RunFailedError for a run that finished `failed`.

    Shared by poll/wait/create_and_wait so the three agree. The message prefers
    the server's `error` (populated from the run's classified failure) and falls
    back to `output`, because a failed run's `output` is where the platform's
    generic "an error occurred" sentence lands. `.details` carries `error_code`
    so callers can branch on the machine token instead of parsing prose.
    """
    if run.status != "failed":
        return
    from .._exceptions import RunFailedError

    detail = getattr(run, "error", None) or getattr(run, "output", None) or "no detail provided"
    code = getattr(run, "error_code", None)
    raise RunFailedError(
        f"Run {run.id} failed: {detail}",
        details={"run_id": run.id, "error_code": code, "error": getattr(run, "error", None)},
    )


if TYPE_CHECKING:
    from .._http import HTTPClient


def _to_file_part(f: Any) -> tuple[str, bytes, str]:
    """Normalize a files= item (path str, (name, bytes) tuple, or file object)
    into the (filename, content, content_type) triple the multipart request
    expects.

    The content type is REQUIRED: without it the part goes up untyped and the
    API rejects the upload with "Invalid type: None" — a customer following the
    files= docs verbatim hit exactly that (2026-08-16 executable-docs gate; the
    curl example passed because curl supplies a default part type).

    File objects are materialized with .read() so the automatic 429/5xx retry
    re-sends the same bytes instead of an exhausted stream (empty upload).
    """
    import mimetypes

    def typed(name: str, content: bytes) -> tuple[str, bytes, str]:
        return (name, content, mimetypes.guess_type(name)[0] or "application/octet-stream")

    if isinstance(f, str):
        from pathlib import Path

        p = Path(f)
        return typed(p.name, p.read_bytes())
    if isinstance(f, tuple):
        # >= 3: caller already supplied a content type (requests also accepts a
        # 4-tuple with part headers) — pass through untouched.
        return f if len(f) >= 3 else typed(f[0], f[1])
    return typed(getattr(f, "name", "upload.bin").rsplit("/", 1)[-1], f.read())


class Runs:
    """client.runs — execute agents, stream events, manage runs."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def create(
        self,
        *,
        message: str,
        teammate_id: int | None = None,
        agent_id: int | None = None,
        tools: list[str] | None = None,
        stream: bool = True,
        name: str | None = None,
        instructions: str | None = None,
        user_id: str | None = None,
        metadata: dict | None = None,
        memory: bool | None = None,
        history: bool | None = None,
        task_setup_tools: bool | None = None,
        feedback: bool | None = None,
        human_in_the_loop: bool | None = None,
        permission_mode: str | None = None,
        model: str | None = None,
        effort: str | None = None,
        email_inbox: bool = False,
        output_schema: dict | None = None,
        files: _list | None = None,
        raise_on_error: bool = False,
        idempotency_key: str | None = None,
    ) -> RunStream | Run:
        """Create and execute a run.

        With stream=True (default): returns iterable RunStream of events.
        With stream=False: returns Run immediately (status="running").
            Poll GET /runs/{id} until status is terminal to get output.

        Pass files= to attach files the agent can read (a CSV to analyze, a PDF
        to summarize). Each item is a path string, a (filename, bytes) tuple, or
        an open binary file object. Uploads use the multipart /runs/with-files
        endpoint; every other argument works exactly the same.

        Set human_in_the_loop=True to enable interactive features
        (clarifying questions, tool approval, plan mode).

        The four built-in tool toggles (memory, history, task_setup_tools,
        feedback) are run-level overrides. Leave them None to inherit the
        agent default (then the platform default, enabled); pass True/False
        to force one on/off for this run. See client.built_in_tools.list().

        If teammate_id points at an end-user-scoped agent, omitting user_id
        inherits that scope. Passing a different user_id is rejected.

        Pass output_schema= (a JSON Schema, "type": "object") to get a typed result back on
        run.output_data instead of parsing prose. Inline your definitions — $ref/$defs are not
        supported. output_data is None when the model produced no structured result, so always
        None-check it. The schema sticks to the run: replies and retries stay structured.

        Every call sends an ``Idempotency-Key``, minted per call unless you pass
        ``idempotency_key=``. That is what makes this POST safe to retry: a request
        that times out may already have started a billable run, and re-sending the
        same key returns THAT run instead of starting (and charging for) a second.
        Supply your own key to make a retry safe across process restarts — a job
        runner re-driving the same unit of work should pass its job id.
        """
        teammate_id = _resolve_agent_id(teammate_id, agent_id)
        body: dict = {"message": message, "stream": stream}
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
        if memory is not None:
            body["memory"] = memory
        if history is not None:
            body["history"] = history
        if task_setup_tools is not None:
            body["task_setup_tools"] = task_setup_tools
        if feedback is not None:
            body["feedback"] = feedback
        if human_in_the_loop is not None:
            body["human_in_the_loop"] = human_in_the_loop
        if permission_mode is not None:
            body["permission_mode"] = permission_mode
        if model is not None:
            body["model"] = model
        if effort is not None:
            body["effort"] = effort
        if email_inbox:
            body["email_inbox"] = True
        if output_schema is not None:
            body["output_schema"] = output_schema

        headers = idempotency_headers(idempotency_key)

        if files:
            file_parts = [("files", _to_file_part(f)) for f in files]
            form = {"payload": json.dumps(body)}
            if stream:
                resp = self._http.stream(
                    "POST", "/runs/with-files", data=form, files=file_parts, headers=headers
                )
                return self._stream_or_replay(resp, raise_on_error=raise_on_error)
            resp = self._http.request(
                "POST", "/runs/with-files", data=form, files=file_parts, headers=headers
            )
            return Run.from_dict(resp.json())

        if stream:
            resp = self._http.stream("POST", "/runs/", json=body, headers=headers)
            return self._stream_or_replay(resp, raise_on_error=raise_on_error)

        resp = self._http.request("POST", "/runs/", json=body, headers=headers)
        return Run.from_dict(resp.json())

    def start_first_session(
        self,
        *,
        teammate_id: int | None = None,
        agent_id: int | None = None,
        stream: bool = True,
        human_in_the_loop: bool | None = None,
        permission_mode: str | None = None,
        raise_on_error: bool = False,
        idempotency_key: str | None = None,
    ) -> RunStream | Run:
        """Start an agent-first onboarding conversation for an existing teammate.

        This dedicated operation gives the server provenance for the synthetic
        opening turn. Sending the reserved marker through ``runs.create`` remains
        ordinary caller text and is never rewritten or hidden.
        """
        resolved_id = _resolve_agent_id(teammate_id, agent_id)
        if resolved_id is None:
            raise ValueError("teammate_id or agent_id is required")
        body: dict[str, Any] = {"teammate_id": resolved_id, "stream": stream}
        if human_in_the_loop is not None:
            body["human_in_the_loop"] = human_in_the_loop
        if permission_mode is not None:
            body["permission_mode"] = permission_mode
        headers = idempotency_headers(idempotency_key)
        if stream:
            resp = self._http.stream("POST", "/runs/first-session", json=body, headers=headers)
            return self._stream_or_replay(resp, raise_on_error=raise_on_error)
        resp = self._http.request("POST", "/runs/first-session", json=body, headers=headers)
        return Run.from_dict(resp.json())

    def _stream_or_replay(self, resp: Any, *, raise_on_error: bool) -> RunStream:
        """Turn a streaming POST's response into a stream, following a replay.

        A replayed create/reply answers with JSON (the run), not SSE — a run that
        already finished has no live stream to hand back, and the server will not
        pretend otherwise. So when the retry was answered from an existing run, join
        that run's stream instead, which is the same reconnect path ``stream()``
        uses. The caller sees an ordinary RunStream and never learns a retry happened.

        A run that has ALREADY finished by the time the retry lands has nothing to
        join, so this raises rather than yielding an empty stream that would read as
        "the agent said nothing". The window is the retry backoff (sub-second), and
        the error names the run so the caller can fetch its result — which is still
        strictly better than the pre-idempotency outcome, where a timed-out create
        left them unable to learn the run existed at all.
        """
        if not resp.headers.get(REPLAY_HEADER):
            return RunStream(resp, raise_on_error=raise_on_error)
        run = Run.from_dict(resp.json())
        resp.close()
        logger.debug("Idempotent replay of run %s; joining its stream", run.id)
        if run.status in TERMINAL_STATUSES:
            from .._exceptions import ConflictError

            raise ConflictError(
                f"Run {run.id} was already created by an earlier attempt with this "
                f"idempotency key and has finished (status={run.status}), so there is "
                f"no stream to join. You were charged once. Fetch the result with "
                f"client.runs.get({run.id}).",
                status_code=409,
                code="idempotent_replay_terminal",
                details={"run_id": run.id, "status": run.status},
            )
        return self.stream(run.id, raise_on_error=raise_on_error)

    def stream(self, run_id: int, *, raise_on_error: bool = False) -> RunStream:
        """Join an in-progress run's live SSE stream (reconnect / resume).

        Use this to re-attach after a dropped connection: capture ``run_id`` from a
        ``create(...)`` stream's metadata event, then call ``stream(run_id)`` to rejoin.
        It replays the run's full history (metadata, prior text/tool events) and then
        streams live deltas, so reset any local accumulation when you reconnect.

        Raises NotFoundError (404) if the run isn't yours, or a 409 if it is no longer
        executing — fetch the final result with ``get(run_id)`` instead. GET is safe to
        retry, so transient network errors are retried automatically.
        """
        resp = self._http.stream("GET", f"/runs/{seg(run_id)}/stream")
        return RunStream(resp, raise_on_error=raise_on_error)

    def poll(
        self,
        run_id: int,
        *,
        user_id: str | None = None,
        interval: float = 2.0,
        timeout: float = 300.0,
        raise_on_error: bool = False,
    ) -> Run:
        """Poll until the run reaches a terminal status. Returns the completed Run.

        For runs with human_in_the_loop=True, use wait() instead — it handles
        awaiting_approval pauses via callbacks so the run can continue.

        Pass ``user_id`` when the account has strict multi-tenant mode on —
        otherwise every poll GET 422s.

        `raise_on_error=True` turns a `failed` run into RunFailedError instead of
        a returned Run, matching `runs.create(..., raise_on_error=True)` on the
        streaming path. Off by default so this stays non-breaking.
        """
        import time as _time

        from .._exceptions import APIError

        deadline = _time.monotonic() + timeout
        while True:
            try:
                run = self.get(run_id, user_id=user_id)
            except APIError:
                if _time.monotonic() >= deadline:
                    raise TimeoutError(f"Run {run_id} did not complete within {timeout}s") from None
                _time.sleep(interval)
                continue
            if run.status in TERMINAL_STATUSES:
                if raise_on_error:
                    _raise_if_failed(run)
                return run
            if _time.monotonic() >= deadline:
                raise TimeoutError(f"Run {run_id} did not complete within {timeout}s")
            _time.sleep(interval)

    def wait(
        self,
        run_id: int,
        *,
        user_id: str | None = None,
        on_approval: Callable[[PermissionRequest], str] | None = None,
        on_question: Callable[[PermissionRequest], dict[str, str]] | None = None,
        interval: float = 2.0,
        timeout: float = 300.0,
        raise_on_error: bool = False,
    ) -> Run:
        """Wait for a run to complete, handling human-in-the-loop pauses via callbacks.

        Like poll(), but also handles awaiting_approval status:
        - Tool approvals: calls on_approval(req) → "allow" or "deny"
        - AskUserQuestion: calls on_question(req) → {question_text: answer} dict

        Pass ``user_id`` when the account has strict multi-tenant mode on —
        otherwise every poll GET 422s.

        Without callbacks, raises RuntimeError if the run pauses for input.

        Usage:
            run = client.runs.wait(
                run.id,
                user_id="alice",
                on_question=lambda req: {"Which segment?": "enterprise"},
                on_approval=lambda req: "allow",
            )

        For plan mode, check req.is_plan_approval and req.plan_text:
            def handle_question(req):
                if req.is_plan_approval:
                    print(req.plan_text)
                    return {"Plan Approval": "Approve"}
                return {}  # shouldn't happen

            run = client.runs.wait(run.id, on_question=handle_question)
        """
        import time as _time

        from .._exceptions import APIError, ConflictError, NotFoundError

        deadline = _time.monotonic() + timeout

        while True:
            try:
                run = self.get(run_id, user_id=user_id)
            except APIError:
                if _time.monotonic() >= deadline:
                    raise TimeoutError(f"Run {run_id} did not complete within {timeout}s") from None
                _time.sleep(interval)
                continue

            if run.status in TERMINAL_STATUSES:
                if raise_on_error:
                    _raise_if_failed(run)
                return run

            if run.status == "awaiting_approval":
                pending = [r for r in self.permissions(run_id) if r.status == "pending"]
                for req in pending:
                    if req.tool_name == "AskUserQuestion":
                        if on_question is None:
                            raise RuntimeError(
                                f"Run {run_id} is waiting for a question response "
                                f"(tool: AskUserQuestion). Pass on_question= to handle it, "
                                "or use runs.answer() manually."
                            )
                        answers = on_question(req)
                        self.answer(run_id, answers=answers)
                    else:
                        if on_approval is None:
                            raise RuntimeError(
                                f"Run {run_id} is waiting for tool approval "
                                f"({req.tool_name!r}). Pass on_approval= to handle it, "
                                "or use runs.approve() manually."
                            )
                        decision = on_approval(req)
                        # The gate can die between the list and this call. Two very
                        # different things look alike here, so branch on the server's
                        # machine-readable code, never on the message:
                        #
                        #   benign — the gate was cancelled, or the run went terminal
                        #   under us. Nothing was contradicted, and wait() owes the
                        #   caller the RUN's outcome, not the gate's. Log and keep
                        #   polling; the next get() returns the real result.
                        #
                        #   CONTRADICTED — another approver decided the OTHER way, so
                        #   this caller's decision did NOT happen and the opposite one
                        #   is what runs. Swallowing that would re-create, one layer up,
                        #   exactly the false confirmation the 404 exists to prevent:
                        #   wait() would return a completed run to a caller who believes
                        #   they denied the tool that just executed. It must propagate.
                        try:
                            self.approve(run_id, request_id=req.request_id, decision=decision)
                        except (NotFoundError, ConflictError) as exc:
                            if exc.code not in _BENIGN_GATE_REFUSALS:
                                raise
                            logger.warning(
                                "Run %s: '%s' on permission gate %s was refused (%s) — %s",
                                run_id,
                                decision,
                                req.request_id,
                                exc.code,
                                exc,
                            )

            if _time.monotonic() >= deadline:
                raise TimeoutError(f"Run {run_id} did not complete within {timeout}s")
            _time.sleep(interval)

    def create_and_wait(
        self,
        *,
        message: str,
        teammate_id: int | None = None,
        agent_id: int | None = None,
        tools: list[str] | None = None,
        name: str | None = None,
        instructions: str | None = None,
        user_id: str | None = None,
        metadata: dict | None = None,
        memory: bool = True,
        history: bool = True,
        task_setup_tools: bool = True,
        feedback: bool = True,
        human_in_the_loop: bool | None = None,
        permission_mode: str | None = None,
        model: str | None = None,
        effort: str | None = None,
        email_inbox: bool = False,
        output_schema: dict | None = None,
        on_approval: Callable[[PermissionRequest], str] | None = None,
        on_question: Callable[[PermissionRequest], dict[str, str]] | None = None,
        poll_interval: float = 2.0,
        poll_timeout: float = 300.0,
        raise_on_error: bool = False,
    ) -> Run:
        """Create a run and wait until it completes. Returns the finished Run.

        Pass on_approval= and on_question= to handle human-in-the-loop pauses inline.
        Without callbacks, HITL runs will raise RuntimeError when they pause for input.

        `raise_on_error=True` raises RunFailedError instead of returning a run
        whose status is `failed`. Worth setting: the default returns normally, so
        `print(result.output)` prints the platform's failure sentence in exactly
        the place the agent's answer belongs. Mirrors
        `runs.create(..., raise_on_error=True)` on the streaming path; off by
        default so this stays non-breaking.
        """
        teammate_id = _resolve_agent_id(teammate_id, agent_id)
        initial = cast(
            Run,
            self.create(
                message=message,
                teammate_id=teammate_id,
                tools=tools,
                stream=False,
                name=name,
                instructions=instructions,
                user_id=user_id,
                metadata=metadata,
                memory=memory,
                history=history,
                task_setup_tools=task_setup_tools,
                feedback=feedback,
                human_in_the_loop=human_in_the_loop,
                permission_mode=permission_mode,
                model=model,
                effort=effort,
                email_inbox=email_inbox,
                output_schema=output_schema,
            ),
        )
        # Preserve email_address from initial response — GET /runs/{id} doesn't return it
        # Prefer the API-stamped owner (truth after create), else the create kwarg.
        poll_user_id = initial.user_id or user_id
        final = self.wait(
            initial.id,
            user_id=poll_user_id,
            on_approval=on_approval,
            on_question=on_question,
            interval=poll_interval,
            timeout=poll_timeout,
            raise_on_error=raise_on_error,
        )
        if initial.email_address and not final.email_address:
            final.email_address = initial.email_address
        return final

    def reply_and_wait(
        self,
        run_id: int,
        *,
        message: str,
        user_id: str | None = None,
        tools: _list[str] | None = None,
        files: _list | None = None,
        permission_mode: str | None = None,
        task_setup_tools: bool | None = None,
        feedback: bool | None = None,
        human_in_the_loop: bool | None = None,
        on_approval: Callable[[PermissionRequest], str] | None = None,
        on_question: Callable[[PermissionRequest], dict[str, str]] | None = None,
        poll_interval: float = 2.0,
        poll_timeout: float = 300.0,
    ) -> Run:
        """Send a follow-up and wait until it completes. Returns the finished Run.

        Pass ``user_id`` when the account has strict multi-tenant mode on.
        """
        run = self.reply(
            run_id,
            message=message,
            stream=False,
            tools=tools,
            files=files,
            permission_mode=permission_mode,
            task_setup_tools=task_setup_tools,
            feedback=feedback,
            human_in_the_loop=human_in_the_loop,
        )
        return self.wait(
            cast(Run, run).id,
            user_id=cast(Run, run).user_id or user_id,
            on_approval=on_approval,
            on_question=on_question,
            interval=poll_interval,
            timeout=poll_timeout,
        )

    def stream_text(
        self,
        *,
        message: str,
        teammate_id: int | None = None,
        agent_id: int | None = None,
        tools: list[str] | None = None,
        name: str | None = None,
        instructions: str | None = None,
        user_id: str | None = None,
        metadata: dict | None = None,
        memory: bool = True,
        history: bool = True,
        task_setup_tools: bool = True,
        feedback: bool = True,
        human_in_the_loop: bool | None = None,
        permission_mode: str | None = None,
        model: str | None = None,
        effort: str | None = None,
        raise_on_error: bool = False,
    ) -> Generator[str, None, None]:
        """Create a streaming run and yield only text delta strings.

        Usage:
            for chunk in client.runs.stream_text(message="Summarize news"):
                print(chunk, end="", flush=True)

        `raise_on_error=True` raises `RunFailedError` when the run emitted error events,
        after the stream is exhausted. **Worth setting, and the docs' quickstart does.**
        This helper filters the stream down to text deltas, so without it an error frame
        is simply not one of the things yielded: a run that fails outright produces ZERO
        chunks and your `for` loop exits normally — indistinguishable from a successful
        empty answer — and a run that fails midway leaves a truncated reply that reads as
        complete. Off by default so this stays non-breaking; mirrors
        `runs.create(..., raise_on_error=True)` and `create_and_wait`.

        Terminal failures that are not `error` frames — a dead runner, an exhausted
        sandbox quota, a boot timeout — count too (`streaming.TERMINAL_FAILURE_TYPES`).
        On a hosted runtime those are the likely way a run dies, so a flag that only
        noticed `error` frames would have missed the common case.

        **The check runs after the stream is exhausted**, so `break`-ing out of the loop
        early skips it: you keep the chunks you consumed and get no exception even if the
        run went on to fail. Consume the whole stream when you need the guarantee.
        """
        from ..streaming import TextDeltaEvent

        teammate_id = _resolve_agent_id(teammate_id, agent_id)
        stream = self.create(
            message=message,
            teammate_id=teammate_id,
            tools=tools,
            stream=True,
            name=name,
            instructions=instructions,
            user_id=user_id,
            metadata=metadata,
            memory=memory,
            history=history,
            task_setup_tools=task_setup_tools,
            feedback=feedback,
            human_in_the_loop=human_in_the_loop,
            permission_mode=permission_mode,
            model=model,
            effort=effort,
            raise_on_error=raise_on_error,
        )
        run_stream = cast(RunStream, stream)
        with run_stream:
            for event in run_stream:
                if isinstance(event, TextDeltaEvent):
                    yield event.delta

    def list(
        self,
        *,
        teammate_id: int | None = None,
        agent_id: int | None = None,
        task_id: int | None = None,
        user_id: str | None = None,
        status: str | None = None,
        exclude_platform_runs: bool | None = None,
        limit: int = 20,
        starting_after: int | None = None,
    ) -> SyncPage[Run]:
        """List runs. task_id pulls one task's run history (e.g. a scheduled or
        webhook-triggered task's results); user_id scopes to one end-user.

        ``exclude_platform_runs=True`` hides the platform's own work (Company Agent
        Day-1 / pulse / context maintenance) so you can ask whether the *user*
        has run anything themselves yet. Only Platform accounts have a Company
        Agent, so on an API-only account the filter matches nothing.
        """
        teammate_id = _resolve_agent_id(teammate_id, agent_id)
        params = _build_params(
            teammate_id=teammate_id,
            task_id=task_id,
            user_id=user_id,
            status=status,
            exclude_platform_runs=(
                None if exclude_platform_runs is None else str(exclude_platform_runs).lower()
            ),
            limit=limit,
            starting_after=starting_after,
        )
        resp = self._http.request("GET", "/runs/", params=params)
        body = resp.json()

        def _fetch_next(**kw: object) -> SyncPage[Run]:
            return self.list(
                teammate_id=teammate_id,
                task_id=task_id,
                user_id=user_id,
                status=status,
                exclude_platform_runs=exclude_platform_runs,
                limit=limit,
                **kw,  # type: ignore[arg-type]
            )

        return SyncPage(
            data=[Run.from_dict(d) for d in body["data"]],
            has_more=body["has_more"],
            next_starting_after=body.get("next_starting_after"),
            _fetch_next=_fetch_next,
        )

    def get(self, run_id: int, *, user_id: str | None = None) -> Run:
        """Get a run by id. Pass ``user_id`` to scope to one end-user (required when
        the account has strict multi-tenant mode on)."""
        resp = self._http.request(
            "GET", f"/runs/{seg(run_id)}", params=_build_params(user_id=user_id)
        )
        return Run.from_dict(resp.json())

    def check(self, *, user_id: str | None = None) -> RunCheck:
        """Cheap "has anything changed?" probe — aggregate counts only, ~50 bytes.

        Poll this instead of re-listing runs when you only need to know whether
        something appeared (a schedule fired, a webhook came in). Scoped exactly
        like list(): ``user_id`` probes that end-user, omitting it probes the
        account-level scope.
        """
        resp = self._http.request("GET", "/runs/check", params=_build_params(user_id=user_id))
        return RunCheck.from_dict(resp.json())

    def outcome(self, run_id: int) -> RunOutcome:
        """Condensed run result: closing summary, structured output, and metered cost."""
        resp = self._http.request("GET", f"/runs/{seg(run_id)}/outcome")
        return RunOutcome.from_dict(resp.json())

    def messages(
        self,
        run_id: int,
        *,
        after_sequence: int | None = None,
        limit: int = 500,
    ) -> _list[RunMessage]:
        """Full run transcript ordered by sequence (UI reload / reconnect).

        Prefer :meth:`outcome` when you only need the closing summary. Use
        ``after_sequence`` to fetch only messages newer than a known sequence.
        """
        params = _build_params(after_sequence=after_sequence, limit=limit)
        resp = self._http.request("GET", f"/runs/{seg(run_id)}/messages", params=params or None)
        return [RunMessage.from_dict(m) for m in resp.json()]

    def reply(
        self,
        run_id: int,
        *,
        message: str,
        stream: bool = True,
        tools: _list[str] | None = None,
        files: _list | None = None,
        permission_mode: str | None = None,
        task_setup_tools: bool | None = None,
        feedback: bool | None = None,
        human_in_the_loop: bool | None = None,
        idempotency_key: str | None = None,
    ) -> RunStream | Run:
        """Follow-up message on an existing run.

        Continues the SAME run — it re-opens the run (reusing ``run_id``), keeps
        the prior context, and does not create a new run or consume a new
        run-count slot. It only burns tokens.

        Replies normally keep the run's concrete model. After an own-subscription
        auth, quota, rate-limit, or provider-availability failure, a reply instead
        follows the account's current connected/preferred provider. Switching the
        provider and calling ``reply`` again resends only this follow-up; it does
        not replay the whole run.

        Replies inherit the run's persisted settings: the permission mode keeps
        applying, and AskUserQuestion stays enabled on runs created with
        ``human_in_the_loop=True``. An unattended reply loop on such a run can
        pause on a question — pass ``human_in_the_loop=False`` here to pin the
        non-interactive behavior. When omitted, inherits the run's setting
        (runs created before this setting was persisted stay non-interactive).

        Pass ``tools`` (names from client.apps.list()) to change the app toolset
        for this and later replies; omitted or ``[]`` inherits the run's current
        set. Pass ``permission_mode`` ("autonomous" | "approval" | "plan") to
        override the mode for this and later replies; omitted inherits the mode
        the run last ran with. Pass ``files`` (paths, bytes, or file objects — same shapes as
        ``create``) to attach documents to the follow-up; earlier uploads keep
        their names (a same-named re-upload gets a collision suffix).

        With stream=True (default): returns iterable RunStream of events.
        With stream=False: returns Run immediately (status="running").
            Poll GET /runs/{id} until status is terminal to get output.

        Like ``create``, every call sends an ``Idempotency-Key`` (minted per call
        unless you pass ``idempotency_key=``), so a reply that times out can be
        re-sent without appending the follow-up — or billing its tokens — twice.
        """
        body: dict = {"message": message, "stream": stream}
        if tools is not None:
            body["tools"] = tools
        if permission_mode is not None:
            body["permission_mode"] = permission_mode
        if task_setup_tools is not None:
            body["task_setup_tools"] = task_setup_tools
        if feedback is not None:
            body["feedback"] = feedback
        if human_in_the_loop is not None:
            body["human_in_the_loop"] = human_in_the_loop
        headers = idempotency_headers(idempotency_key)
        if files:
            file_parts = [("files", _to_file_part(f)) for f in files]
            form = {"payload": json.dumps(body)}
            if stream:
                resp = self._http.stream(
                    "POST",
                    f"/runs/{seg(run_id)}/reply/with-files",
                    data=form,
                    files=file_parts,
                    headers=headers,
                )
                return self._stream_or_replay(resp, raise_on_error=False)
            resp = self._http.request(
                "POST",
                f"/runs/{seg(run_id)}/reply/with-files",
                data=form,
                files=file_parts,
                headers=headers,
            )
            return Run.from_dict(resp.json())
        if stream:
            resp = self._http.stream(
                "POST", f"/runs/{seg(run_id)}/reply", json=body, headers=headers
            )
            return self._stream_or_replay(resp, raise_on_error=False)
        resp = self._http.request("POST", f"/runs/{seg(run_id)}/reply", json=body, headers=headers)
        return Run.from_dict(resp.json())

    def cancel(self, run_id: int, *, user_id: str | None = None) -> Run:
        """Cancel an active run.

        Pass ``user_id`` when the account has strict multi-tenant mode on.
        """
        resp = self._http.request(
            "POST", f"/runs/{seg(run_id)}/cancel", params=_build_params(user_id=user_id)
        )
        return Run.from_dict(resp.json())

    def share(self, run_id: int) -> RunShare:
        """Create a public read-only link for the run.

        Idempotent — repeat calls return the same link. Revoke with :meth:`unshare`.
        """
        resp = self._http.request("POST", f"/runs/{seg(run_id)}/share")
        return RunShare.from_dict(resp.json())

    def unshare(self, run_id: int) -> None:
        """Revoke the run's public link. The old URL 404s immediately."""
        self._http.request("DELETE", f"/runs/{seg(run_id)}/share")

    def archive(self, run_id: int) -> Run:
        """Archive a run — a soft delete that hides it from the default list.

        Idempotent: archiving an already-archived run succeeds and changes nothing.
        """
        resp = self._http.request("POST", f"/runs/{seg(run_id)}/archive")
        return Run.from_dict(resp.json())

    def mark_viewed(self, run_id: int, *, user_id: str | None = None) -> Run:
        """Mark a run as viewed and return its refreshed acknowledgement state.

        Repeating the call updates ``last_viewed_at`` again.
        Pass ``user_id`` when the account has strict multi-tenant mode on.
        """
        resp = self._http.request(
            "POST", f"/runs/{seg(run_id)}/view", params=_build_params(user_id=user_id)
        )
        return Run.from_dict(resp.json())

    def retry(self, run_id: int, *, confirm: bool = False, use_credits: bool = False) -> Run:
        """Retry a failed or cancelled run.

        Creates and returns a NEW run that re-executes the original's task — poll
        the returned run's `.id`, NOT run_id (the original stays failed). Idempotent:
        if a retry of this run is already in flight, that run is returned.

        If the run already performed actions (sent a message, changed data),
        retrying may repeat them, so the API raises ConflictError with code
        'retry_needs_confirmation'. Pass confirm=True to proceed. Check
        run.retryable before calling to avoid a guaranteed ConflictError on a
        non-retryable run.

        Pass ``use_credits=True`` to pin the platform default model (m8tes credits)
        instead of replaying the original run's concrete / OAuth model.
        Without it, provider auth, quota, rate-limit, and availability failures
        follow the account's current connected/preferred provider; other failures
        replay the original concrete model.
        """
        params: dict[str, str] = {}
        if confirm:
            params["confirm"] = "true"
        if use_credits:
            params["use_credits"] = "true"
        resp = self._http.request("POST", f"/runs/{seg(run_id)}/retry", params=params or None)
        return Run.from_dict(resp.json())

    def update_permission_mode(
        self,
        run_id: int,
        *,
        permission_mode: PermissionMode | str,
    ) -> PermissionModeResponse:
        """Change permission mode mid-run.

        Switches between 'autonomous', 'approval', and 'plan'.
        Switching to 'autonomous' auto-approves pending tool approval requests and
        resumes paused tool approval runs. AskUserQuestion pauses still require
        runs.answer().
        """
        resp = self._http.request(
            "PATCH",
            f"/runs/{seg(run_id)}/permission-mode",
            json={"permission_mode": permission_mode},
        )
        return PermissionModeResponse.from_dict(resp.json())

    def permissions(self, run_id: int) -> _list[PermissionRequest]:
        """List tool permission requests for a run."""
        resp = self._http.request("GET", f"/runs/{seg(run_id)}/permissions")
        return [PermissionRequest.from_dict(d) for d in resp.json()]

    def answer(
        self,
        run_id: int,
        *,
        answers: dict[str, str],
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Submit an answer to an agent's AskUserQuestion.

        Use this when the run is paused waiting for user input (AskUserQuestion).
        The answers dict maps question text (q["question"]) to the selected option label.
        Pass ``request_id`` when multiple questions are pending so the answer targets
        the right gate; omit to answer the first unanswered ask.

        Returns {"status": "ok", "resumed": bool}. When resumed is True, the run
        has been queued to continue from the point it paused.

        Raises ConflictError (409) unless the run is awaiting_approval — a
        running run conflicts too, not only terminal ones.
        """
        body: dict[str, Any] = {"answers": answers}
        if request_id is not None:
            body["request_id"] = request_id
        resp = self._http.request("POST", f"/runs/{seg(run_id)}/answer", json=body)
        result: dict[str, Any] = resp.json()
        return result

    def approve(
        self,
        run_id: int,
        *,
        request_id: str,
        decision: str = "allow",
        remember: bool = False,
        reason: str | None = None,
    ) -> PermissionRequest:
        """Approve or deny a pending tool permission request.

        Re-sending the SAME decision is idempotent, and may be used to upgrade
        ``remember`` to True (it never downgrades an existing grant). An
        allow+remember decision also stores a cross-run always-allow policy for the
        tool; the response's ``remembered`` reports whether that actually persisted
        (False when the backend refused — e.g. a force-gated tool, whose policy the
        runtime would never consult).

        A refusal is never a hiccup — nothing ran, so never treat it as approved. Check
        ``exc.code`` to tell them apart:

        * ``ConflictError`` / ``run_not_active`` — the run finished; no decision applies.
        * ``NotFoundError`` / ``gate_cancelled`` — the gate was cancelled under you.
        * ``NotFoundError`` / ``gate_resolved_otherwise`` — **another approver decided
          the OPPOSITE way.** Yours did not happen and the other one is what runs.
        * ``NotFoundError`` / ``gate_not_found`` — no such gate on this run.

        ``reason`` is optional steering in your own words, mainly with
        ``decision="deny"`` — e.g. ``"use the staging board instead"``. The agent
        reads it and adapts rather than silently skipping the action.
        """
        body: dict[str, object] = {
            "request_id": request_id,
            "decision": decision,
            "remember": remember,
        }
        if reason is not None:
            body["reason"] = reason
        resp = self._http.request("POST", f"/runs/{seg(run_id)}/approve", json=body)
        return PermissionRequest.from_dict(resp.json())

    def list_files(self, run_id: int) -> _list[RunFile]:
        """List files generated by a run."""
        resp = self._http.request("GET", f"/runs/{seg(run_id)}/files")
        return [RunFile.from_dict(f) for f in resp.json()]

    def download_file(self, run_id: int, filename: str) -> bytes:
        """Download a file generated by a run. Returns raw file bytes.

        Run files are flat: pass a basename, not a path. The route reads
        `{filename:path}`, but the three handlers behind it all sanitize the
        filename to a basename (`sanitize_run_filename`) and reject anything
        else, so a nested name is refused here rather than sent to be rejected.
        """
        resp = self._http.request("GET", f"/runs/{seg(run_id)}/files/{seg(filename)}/download")
        return resp.content
