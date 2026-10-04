"""
Utility functions for CLI graceful handling.

Provides helpers for handling keyboard interrupts and signals gracefully,
plus argparse helpers that surface "did you mean?" for invalid choices.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Generator
import contextlib
import difflib
import re
import shlex
import signal
import sys
from typing import TYPE_CHECKING, Any, TextIO, TypedDict

from .._exceptions import M8tesError

if TYPE_CHECKING:
    from .._client import M8tes
    from .._exceptions import StreamInterruptedError
    from .._types import PermissionRequest, Run

CANCELLED_EXIT = 130  # POSIX: 128 + SIGINT (2)

# How long the CLI waits for a run whose stream dropped. Runs of ten minutes and more
# are ordinary. Ctrl+C stops the wait, never the run.
DROPPED_RUN_WAIT_SECONDS = 1800.0


def _cli_on_approval(req: Any) -> str:
    """Prompt for a tool-approval gate reached while waiting out a dropped stream."""
    from .prompt import confirm_prompt

    print(f"\n🔐 Approval needed for tool: {req.tool_name}")
    return "allow" if confirm_prompt("Allow this tool?", default=False) else "deny"


def _cli_on_question(req: Any) -> dict[str, str]:
    """Prompt for an AskUserQuestion / plan gate reached while waiting out a drop."""
    from .prompt import prompt

    answers: dict[str, str] = {}
    questions = (req.tool_input or {}).get("questions") or []
    if not questions:
        return answers
    for q in questions:
        question = q.get("question") or q.get("header") or "Answer"
        options = [o.get("label") for o in (q.get("options") or []) if o.get("label")]
        hint = f" [{'/'.join(options)}]" if options else ""
        answers[question] = prompt(f"{question}{hint}: ", allow_empty=True)
    return answers


class _GateReachedError(Exception):
    """Raised from a gate callback to end the wait without answering the gate."""


class RunPausedError(M8tesError):
    """A run that was waited for after a dropped stream is parked on a person.

    The run did not fail, and it did not finish either. It is raised, not returned
    as a run to read: a command that streams a task must exit non-zero on it, or a
    script takes the pause for completed work. And the run cannot be read again
    here for an answer, because once the gate is resolved a read returns whichever
    turn finished last, which for a queued reply is the turn in front of it.
    """

    def __init__(self, run_id: int, needs: str):
        super().__init__(
            f"Run {run_id} is paused and has not finished: it needs {needs}. "
            "Answer it in the m8tes app and the run carries on.",
            code="run_paused",
            error_code="run_paused",
            details={"run_id": run_id, "needs": needs},
        )
        self.run_id = run_id


def _stop_at_approval(req: PermissionRequest) -> str:
    """Decide nothing: with nobody at the terminal, an answer would be the CLI's own."""
    raise _GateReachedError(f"your approval to use {req.tool_name}")


def _stop_at_question(req: PermissionRequest) -> dict[str, str]:
    raise _GateReachedError("your answer to a question")


def can_ask(output_format: str = "verbose") -> bool:
    """Is there a person at this terminal to put a gate to?

    Not in json mode, where stdout is the event stream and stdin carries the chat
    messages, and not when stdin is a pipe. A prompt there prints into the JSON and
    reads the next chat message, or nothing, as the person's answer: an empty line
    denies the tool.
    """
    return output_format != "json" and sys.stdin.isatty()


#: Run statuses that mean the waited-out drop was not a successful outcome.
DROPPED_RUN_FAILURE_STATUSES = frozenset({"failed", "cancelled", "closed"})


def dropped_run_problem(run: Run) -> str | None:
    """Why a run that was waited for did not finish its work, or None when it did.

    A run that was stopped reports the reason the server kept, never its partial
    output, which would print half an answer as the error.
    """
    if run.status not in DROPPED_RUN_FAILURE_STATUSES:
        return None
    if run.status == "failed":
        return run.error or run.output or "the run failed"
    return run.error or f"the run was {run.status}"


def wait_for_dropped_run(
    client: M8tes,
    exc: StreamInterruptedError,
    *,
    out: TextIO,
    user_id: str | None = None,
    await_queued_message_id: int | None = None,
    ask: bool = False,
) -> Run:
    """The stream dropped; the run did not. Wait for it, and return how it ended.

    The API detaches a run from the connection that started it, so a dropped stream
    used to end a command as if the run were done: a summary of half the work and
    exit 0. Every command that streams a run comes through here instead.

    With no run id there is nothing to go back to, so the interruption propagates
    and the command exits non-zero.

    Pass ``await_queued_message_id`` when the dropped stream was a queued reply's
    join of the prior turn — otherwise wait returns that turn's result as if it
    answered the new message.

    ``runs.wait`` raises at an approval or a question unless it is given callbacks.
    With ``ask`` (a person is at the terminal, see ``can_ask``) the CLI prompts so
    the run can finish. Without it nothing is decided: the wait ends at the gate
    and ``RunPausedError`` is raised. Read a run that is returned with
    ``dropped_run_problem``.
    """
    if exc.run_id is None:
        raise exc
    print(
        f"\n⚠️  Connection lost. Run {exc.run_id} is still going; waiting for it to finish.",
        file=out,
    )
    print("   Ctrl+C stops waiting, not the run.", file=out)
    try:
        return client.runs.wait(
            exc.run_id,
            timeout=DROPPED_RUN_WAIT_SECONDS,
            user_id=user_id,
            on_approval=_cli_on_approval if ask else _stop_at_approval,
            on_question=_cli_on_question if ask else _stop_at_question,
            await_queued_message_id=await_queued_message_id,
        )
    except _GateReachedError as gate:
        raise RunPausedError(exc.run_id, str(gate)) from None


# argparse: invalid choice: 'show' (choose from 'create', 'c', 'list', ...)
_INVALID_CHOICE_RE = re.compile(
    r"invalid choice:\s*'([^']+)'\s*\(choose from\s+(.+)\)",
    re.IGNORECASE,
)


def parse_id(value: str, label: str) -> int:
    """Parse a numeric CLI ID, raising a typed error the command layer maps to exit 1."""
    from ..exceptions import ValidationError

    try:
        return int(value)
    except ValueError as e:
        raise ValidationError(f"{label} must be a number, got {value!r}") from e


# Common CLI mistakes → preferred primary names (only applied when that name is a choice).
_COMMAND_SYNONYMS: dict[str, tuple[str, ...]] = {
    "show": ("get", "list"),
    "view": ("get", "list"),
    "info": ("get", "status"),
    "describe": ("get",),
    "rm": ("archive", "disable", "delete"),
    "remove": ("archive", "disable", "delete"),
    "delete": ("archive", "disable"),
    "start": ("enable", "execute", "task", "chat"),
    "stop": ("disable", "archive"),
    "run": ("task", "execute", "chat"),
    "exec": ("execute", "task"),
    "ls": ("list",),
}


def suggest_commands(
    unknown: str, choices: list[str], *, n: int = 3, cutoff: float = 0.6
) -> list[str]:
    """Return close matches for an unknown command name (deduped, primary names preferred)."""
    # cutoff 0.6: at 0.4, `m8tes frobnicate` suggested `mate`. Real typos (agnet, tsak) score 0.75+.
    choice_set = set(choices)
    ordered: list[str] = []

    for synonym in _COMMAND_SYNONYMS.get(unknown.lower(), ()):
        if synonym in choice_set:
            ordered.append(synonym)

    # Prefer longer primary-looking names: drop single-char aliases when a longer match exists.
    matches = difflib.get_close_matches(unknown, choices, n=n * 2, cutoff=cutoff)
    primaries = [m for m in matches if len(m) > 1]
    ordered.extend(primaries)
    ordered.extend(m for m in matches if m not in primaries)

    # Preserve order, unique
    seen: set[str] = set()
    out: list[str] = []
    for m in ordered:
        if m not in seen and m in choice_set:
            seen.add(m)
            out.append(m)
        if len(out) >= n:
            break
    return out


def enhance_argparse_error(message: str) -> str:
    """Append a 'Did you mean?' line when argparse reports an invalid choice.

    For missing required args, append a short example under the usage dump so the
    developer sees what a successful invocation looks like (DX Slice B1).
    """
    match = _INVALID_CHOICE_RE.search(message)
    if match:
        bad = match.group(1)
        raw = match.group(2)
        choices = [c.strip().strip("'\"") for c in raw.split(",") if c.strip().strip("'\"")]
        suggestions = suggest_commands(bad, choices)
        if suggestions:
            return f"{message}\n💡 Did you mean: {', '.join(suggestions)}?"
        return message
    if "the following arguments are required:" in message.lower():
        return (
            f"{message}\n"
            "💡 Example: m8tes auth login\n"
            '💡 Example: m8tes agent task "say hello"\n'
            "💡 Example: m8tes run get 12345"
        )
    return message


class SuggestingArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that suggests close command names on invalid choice."""

    def error(self, message: str) -> None:  # type: ignore[override]
        message = enhance_argparse_error(message)
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: error: {message}\n")


def _print_cancelled(msg: str = "✖ Cancelled by user") -> None:
    """Print cancellation message to stderr."""
    sys.stderr.write("\n" + msg + "\n")
    sys.stderr.flush()


@contextlib.contextmanager
def _suppress_tracebacks() -> Generator[None, None, None]:
    """Context manager that suppresses KeyboardInterrupt tracebacks."""
    old_hook = sys.excepthook

    def _quiet_excepthook(exc_type: type, exc: BaseException, tb: Any) -> Any:
        if exc_type is KeyboardInterrupt:
            _print_cancelled()
            sys.exit(CANCELLED_EXIT)
        return old_hook(exc_type, exc, tb)

    sys.excepthook = _quiet_excepthook
    try:
        yield
    finally:
        sys.excepthook = old_hook


def show_auth_guidance() -> None:
    """Show helpful authentication guidance when user is not authenticated."""
    print("\n💡 Authentication Required")
    print("=" * 50)
    print("\n📝 To get started, you need to authenticate:")
    print("\n  Register a new account:")
    print("    m8tes auth register")
    print("\n  Or login with existing account:")
    print("    m8tes auth login")
    print("\n  Check authentication status:")
    print("    m8tes auth status")
    print()


def graceful_main(fn: Callable[[list[str]], int], argv: list[str]) -> int:
    """
    Run fn(argv) and handle Ctrl-C/SIGTERM nicely.

    Args:
        fn: Function to run that takes argv and returns exit code
        argv: Command line arguments

    Returns:
        Exit code (130 for cancelled, or fn's return value)
    """

    # Handle SIGTERM like Ctrl-C
    def _term(_signum: int, _frame: Any) -> None:
        raise KeyboardInterrupt()

    old_term = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGTERM, _term)

    try:
        with _suppress_tracebacks():
            return int(fn(argv) or 0)
    except KeyboardInterrupt:
        _print_cancelled()
        return CANCELLED_EXIT
    finally:
        signal.signal(signal.SIGTERM, old_term)


def add_user_id_argument(parser: argparse.ArgumentParser) -> None:
    """Expose the end-user scope required by strict API accounts."""
    parser.add_argument("--user-id", help="End-user scope (required for strict API accounts)")


class UserScope(TypedDict, total=False):
    user_id: str


def user_scope(args: argparse.Namespace) -> UserScope:
    """Only forward an explicitly supplied tenant scope."""
    user_id = getattr(args, "user_id", None)
    return {"user_id": user_id} if user_id is not None else {}


def scope_cli_suffix(scope: UserScope) -> str:
    """Keep copyable follow-up commands in the same tenant, including opaque IDs."""
    return f" --user-id {shlex.quote(scope['user_id'])}" if "user_id" in scope else ""
