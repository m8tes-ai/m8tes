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
import signal
import sys
from typing import Any

CANCELLED_EXIT = 130  # POSIX: 128 + SIGINT (2)

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
    unknown: str, choices: list[str], *, n: int = 3, cutoff: float = 0.4
) -> list[str]:
    """Return close matches for an unknown command name (deduped, primary names preferred)."""
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
    """Append a 'Did you mean?' line when argparse reports an invalid choice."""
    match = _INVALID_CHOICE_RE.search(message)
    if not match:
        return message
    bad = match.group(1)
    # Choices are quoted tokens separated by commas
    raw = match.group(2)
    choices = [c.strip().strip("'\"") for c in raw.split(",") if c.strip().strip("'\"")]
    suggestions = suggest_commands(bad, choices)
    if not suggestions:
        return message
    return f"{message}\n💡 Did you mean: {', '.join(suggestions)}?"


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
