"""
Utility functions for CLI graceful handling.

Provides helpers for handling keyboard interrupts and signals gracefully.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
import contextlib
import signal
import sys
from typing import Any

CANCELLED_EXIT = 130  # POSIX: 128 + SIGINT (2)


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
