"""Guard: no runtime event type may reach a developer as an "upgrade your SDK" warning.

Measured on 2026-08-11 against prod, on m8tes 3.0.1 (the CURRENT release), the very first
run of the documented quickstart printed this three times before any agent output:

    Unrecognized stream event type 'RUNNER_DIAG' — exposed as 'unknown'; the full
    payload is on event.raw. Upgrading the m8tes SDK may add support.

...and again for 'system_message' and 'message_snapshot'. The advice is impossible to
follow — there is no newer SDK — and it is the first thing a new developer sees, so it
reads as a broken integration before they have read a single line of their agent's reply.

All three are infrastructure frames: `RUNNER_DIAG` is agent_runner.py startup
diagnostics, `message_snapshot` is the persistence payload the backend consumes, and
`system_message` is a generic runtime notice. None of them is something a developer acts
on, so warning about them is pure noise. They are classified in
`m8tes.streaming._INTERNAL_EVENT_TYPES` and pass through as UNKNOWN events (payload still
on `event.raw`) without a warning.

WHY A PARITY GUARD AND NOT JUST A THREE-ITEM ALLOWLIST. The three were not a one-off; they
are what happens when the runtime gains an event type and the SDK is never told. The
frontend already has this guard (`agent-runtime/tests/test_event_type_ts_parity.py`) and
Python had nothing, so every future runtime event type would have arrived the same way —
as a warning telling the user to do something that cannot help. This test therefore
requires every runtime `EventType` value to be CLASSIFIED: either the SDK names it in
`StreamEventType`, or it is explicitly internal. Adding an unclassified one fails here.

Deliberately NOT "the two enums must be equal": they are different vocabularies on
purpose. The SDK speaks the AI-SDK wire protocol (`text-delta`), the runtime speaks its own
(`text`). Demanding equality would force dozens of meaningless members and would be
deleted by the first person it inconvenienced.
"""

from __future__ import annotations

from pathlib import Path
import re

import pytest

from m8tes.streaming import _INTERNAL_EVENT_TYPES, StreamEvent, StreamEventType

# Platform/backend frames silenced in the SDK but never emitted by agent_runtime.
_BACKEND_ONLY_INTERNAL_EVENT_TYPES = frozenset({"error_cleared"})

# tests/unit/ -> tests/ -> the SDK package root. This anchor holds in BOTH layouts (the
# monorepo's `sdk/py/` and the standalone m8tes-ai/m8tes root), which is what makes it
# checkable — see test_path_arithmetic_is_correct below. Everything else is derived from
# it, so there is exactly one place the arithmetic can be wrong.
_SDK_ROOT = Path(__file__).resolve().parents[2]
# Only meaningful in the monorepo: sdk/py -> sdk -> repo root.
_REPO_ROOT = _SDK_ROOT.parents[1]
_RUNTIME_EVENT_TYPES = _REPO_ROOT / "agent-runtime" / "agent_runtime" / "event_types.py"


def _runtime_event_values() -> set[str]:
    """String values declared in agent-runtime's `EventType`, read from source.

    Read by PATH rather than imported: `m8tes` is a standalone published package and must
    never depend on `agent_runtime`. `sdk/py/` also syncs to the public m8tes-ai/m8tes
    repo, where agent-runtime does not exist at all — hence the skip below.
    """
    text = _RUNTIME_EVENT_TYPES.read_text()
    match = re.search(r"class EventType[^:]*:(.*?)(?=\nclass |\Z)", text, re.DOTALL)
    assert match, f"could not find `class EventType` in {_RUNTIME_EVENT_TYPES}"
    return set(re.findall(r'^\s{4}[A-Z_0-9]+\s*(?::\s*\w+\s*)?=\s*"([^"]+)"', match.group(1), re.M))


def _in_monorepo() -> bool:
    """True in this repo, False in the synced standalone SDK repo.

    Derived from `_SDK_ROOT`, whose position is independently asserted below, so a wrong
    path cannot masquerade as "standalone" and skip everything.
    """
    return _SDK_ROOT.name == "py" and _SDK_ROOT.parent.name == "sdk"


requires_runtime = pytest.mark.skipif(
    not _in_monorepo(), reason="standalone SDK repo — agent-runtime does not exist here"
)


def test_path_arithmetic_is_correct():
    """Pin `_SDK_ROOT`, unskipped, in BOTH layouts. This is the load-bearing test.

    Everything else here is skipped outside the monorepo, so if the `parents[N]` count is
    wrong the skip engages and the whole file reports green while guarding nothing. The
    first attempt at preventing that keyed the layout check on `agent-runtime` being
    absent — which an off-by-one ALSO satisfies, so it passed under mutation and was pure
    decoration. Caught only by mutating `parents[2]`.

    The fix is to anchor on something true in both layouts: this file always sits at
    `<sdk root>/tests/unit/`, and the SDK root always contains `m8tes/` and
    `pyproject.toml`. Any arithmetic error breaks that, in either repo, unskipped.
    """
    assert (_SDK_ROOT / "m8tes").is_dir(), f"{_SDK_ROOT} is not the SDK package root"
    assert (_SDK_ROOT / "pyproject.toml").is_file(), f"{_SDK_ROOT} has no pyproject.toml"


def test_monorepo_detection_is_not_silently_wrong():
    """In the monorepo, a missing runtime file is a FAILURE, never a skip."""
    if _in_monorepo():
        assert _RUNTIME_EVENT_TYPES.is_file(), (
            f"Detected the monorepo layout ({_REPO_ROOT}) but {_RUNTIME_EVENT_TYPES} is "
            "missing. Either agent-runtime moved or the path arithmetic is wrong — do NOT "
            "'fix' this by widening the skip, which disables the parity guard silently."
        )
    else:
        # Standalone: prove it really is standalone rather than a misresolved path.
        assert not (_SDK_ROOT / "sdk" / "py").exists(), (
            f"{_SDK_ROOT} looks like a repo root, not the SDK package root — the layout "
            "detection above cannot be trusted."
        )


@requires_runtime
def test_the_guard_can_actually_see_the_runtime_enum():
    """A parity guard that silently reads nothing passes forever and protects nothing.

    This is the failure mode the repo has hit before (a watchdog querying a table
    production does not have). If `agent-runtime/` exists, the file must exist and parse
    to a non-trivial set — otherwise the parity assertion below is vacuous.
    """
    assert _RUNTIME_EVENT_TYPES.is_file(), f"{_RUNTIME_EVENT_TYPES} is missing"
    values = _runtime_event_values()
    assert len(values) > 20, f"parsed only {len(values)} EventType values — regex likely broke"
    # Spot-check members of EventType specifically, including the odd SCREAMING_CASE one.
    assert {"message_snapshot", "RUNNER_DIAG", "permission_request"} <= values
    # And prove the class boundary holds: `text` is ContentBlockType, NOT EventType. If
    # the regex ever ran past `class EventType` into its neighbours, this catches it —
    # a parity guard reading the wrong class would demand classification for names that
    # never appear on the wire as event types.
    assert "text" not in values


@requires_runtime
def test_every_runtime_event_type_is_classified():
    """Each runtime event is either named by the SDK or explicitly internal."""
    sdk_names = {e.value for e in StreamEventType}
    unclassified = sorted(_runtime_event_values() - sdk_names - _INTERNAL_EVENT_TYPES)
    assert not unclassified, (
        "These agent-runtime EventType values are unknown to the SDK, so each one reaches "
        "developers as a spurious 'Upgrading the m8tes SDK may add support' warning: "
        f"{unclassified}. "
        "Fix by either adding a member to m8tes.streaming.StreamEventType (if a developer "
        "should be able to match on it) or listing it in _INTERNAL_EVENT_TYPES (if it is "
        "infrastructure). Do not delete this test."
    )


@pytest.mark.parametrize("event_type", ["RUNNER_DIAG", "system_message", "message_snapshot"])
def test_the_three_measured_frames_do_not_warn(event_type, caplog):
    """The exact frames seen on the quickstart's first run, pinned by name.

    Kept independent of the parity guard above: that one proves nothing NEW slips through,
    this one proves the ones that actually shipped are fixed. A regression in either the
    classification set or the warning branch has to break one of them.
    """
    StreamEvent._warned_unknown_types.clear()
    try:
        with caplog.at_level("WARNING", logger="m8tes.streaming"):
            events = StreamEvent.from_dict({"type": event_type})
        assert not caplog.records, (
            f"{event_type} warned: {[r.getMessage() for r in caplog.records]}"
        )
        # Suppressing the warning must not suppress the EVENT — the payload stays
        # reachable on `event.raw` for anyone who wants it.
        assert [e.type for e in events] == [StreamEventType.UNKNOWN]
        assert events[0].raw == {"type": event_type}
    finally:
        StreamEvent._warned_unknown_types.clear()


def test_a_genuinely_unknown_type_still_warns(caplog):
    """The warning is still doing its job for types nobody has classified.

    Without this, "fix the noise" could be satisfied by deleting the warning outright,
    which would hide real runtime/SDK drift — the thing the parity guard exists to catch.
    """
    StreamEvent._warned_unknown_types.clear()
    try:
        with caplog.at_level("WARNING", logger="m8tes.streaming"):
            StreamEvent.from_dict({"type": "totally_made_up_frame"})
        assert any("totally_made_up_frame" in r.getMessage() for r in caplog.records)
    finally:
        StreamEvent._warned_unknown_types.clear()


# ── system_message subtypes ──────────────────────────────────────────────────────────
# `system_message` is classified internal, which is right for the WARNING (a system frame
# is not an SDK-version problem) but leaves a hole an independent review caught: the
# runtime demotes a pile of genuinely actionable CLI signals to
# `{"type": "system_message", "subtype": ...}`, so `api_error`, `model_fallback` and
# `permission_denied` all arrive as UNKNOWN with no typed discriminator, and the top-level
# parity guard above cannot see any of it because it only reads `EventType`.
#
# Surfacing these as first-class events is real work and is filed in TODOS.md ("Every
# actionable CLI subtype reaches the SDK wrapped in `system_message`"). What this guard
# does is stop the set growing SILENTLY: a subtype added upstream fails here until someone
# looks at it and decides. That is the same "classify it or the build breaks" shape as the
# EventType guard, applied one level down.
_ACKNOWLEDGED_SYSTEM_SUBTYPES = frozenset(
    {
        # Task lifecycle.
        "task_started",
        "task_stopped",
        "task_progress",
        "task_notification",
        "task_updated",
        "task_summary",
        # Turn / progress telemetry — inert for an API consumer.
        "status",
        "thinking_tokens",
        "turn_starting",
        "turn_duration",
        "post_turn_summary",
        "away_summary",
        "informational",
        "notification",
        # Retry / error / model-fallback. THESE ARE THE ACTIONABLE ONES. `model_fallback`
        # carries a money angle: a run silently downgraded to the fallback model bills
        # differently than the caller asked for.
        "api_retry",
        "api_error",
        "mirror_error",
        "model_fallback",
        "model_consent_fallback",
        "model_refusal_fallback",
        "model_refusal_no_fallback",
        "agents_killed",
        "worker_shutting_down",
        # Permission engine — actionable.
        "permission_denied",
        "permission_retry",
        "elicitation_complete",
        # Hook lifecycle.
        "hook_started",
        "hook_progress",
        "hook_response",
        "stop_hook_summary",
        # Session / environment state. These describe the CLI's own workspace, not the
        # caller's run, and an API consumer has nothing to do with any of them.
        "session_state_changed",
        "background_tasks_changed",
        "commands_changed",
        "vcs_state_changed",
        "code_change_published",
        "file_snapshot",
        "local_command",
        "plugin_install",
        "scheduled_task_fire",
        "control_request_progress",
        "memory_recall",
        "memory_saved",
        "bridge_state",
        "bridge_status",
        # Claude Agent SDK 0.2.152+ — CLI cloud-session / tool-host telemetry. Inert for
        # an API consumer (describes the host CLI's own session, not the caller's run).
        "cloud_session_status",
        "tool_host_result",
        # Informational only — a queued feedback draft, not a failure signal.
        "feedback_draft_queued",
    }
)


def _runtime_system_subtypes() -> set[str]:
    text = _RUNTIME_EVENT_TYPES.parent.joinpath("utils.py").read_text()
    match = re.search(r"_KNOWN_SYSTEM_SUBTYPES\s*=\s*frozenset\(\s*\{(.*?)\}\s*\)", text, re.DOTALL)
    assert match, "could not find _KNOWN_SYSTEM_SUBTYPES in agent_runtime/utils.py"
    return set(re.findall(r'"([^"]+)"', match.group(1)))


@requires_runtime
def test_the_subtype_guard_can_actually_see_the_runtime_set():
    """Same anti-vacuity check as the EventType one: prove the regex found something."""
    subtypes = _runtime_system_subtypes()
    assert len(subtypes) > 15, f"parsed only {len(subtypes)} subtypes — regex likely broke"
    assert {"api_error", "model_fallback", "permission_denied"} <= subtypes


@requires_runtime
def test_every_system_message_subtype_is_acknowledged():
    unacknowledged = sorted(_runtime_system_subtypes() - _ACKNOWLEDGED_SYSTEM_SUBTYPES)
    assert not unacknowledged, (
        f"New `system_message` subtypes upstream: {unacknowledged}. These reach SDK "
        "consumers as an UNKNOWN event with no typed discriminator and no warning, so "
        "nothing else in the test suite will tell you they exist. Decide whether each is "
        "actionable for a developer (if so it needs surfacing — see the TODOS entry) or "
        "inert, then add it above. Do not delete this test to get green."
    )


@requires_runtime
def test_internal_list_does_not_rot_against_the_runtime():
    """Every internal name must still exist in the runtime.

    A stale entry is not harmless: it is a name the SDK promises to stay quiet about,
    so if the runtime later reuses it for something developer-facing, the SDK swallows
    it silently instead of surfacing the drift.
    """
    stale = sorted(
        (_INTERNAL_EVENT_TYPES - _BACKEND_ONLY_INTERNAL_EVENT_TYPES) - _runtime_event_values()
    )
    assert not stale, f"_INTERNAL_EVENT_TYPES names no longer emitted by the runtime: {stale}"
