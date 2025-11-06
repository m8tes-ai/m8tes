"""
Safe prompt utilities for CLI input.

Provides input functions that handle keyboard interrupts gracefully.
"""

from __future__ import annotations

from getpass import getpass

from .util import CANCELLED_EXIT, _print_cancelled


def prompt(label: str, *, allow_empty: bool = False) -> str:
    """
    Safe input prompt that handles Ctrl-C gracefully.

    Args:
        label: Prompt message to display
        allow_empty: Whether to allow empty input

    Returns:
        User input as string

    Exits:
        With code 130 if user cancels with Ctrl-C
    """
    try:
        value = input(label).strip()
        if not value and not allow_empty:
            return prompt(label, allow_empty=allow_empty)  # Re-prompt for empty input
        return value
    except (KeyboardInterrupt, EOFError):
        _print_cancelled()
        raise SystemExit(CANCELLED_EXIT) from None


def secure_prompt(label: str) -> str:
    """
    Safe password prompt that handles Ctrl-C gracefully.

    Args:
        label: Prompt message to display

    Returns:
        User input as string (hidden), preserving whitespace as entered

    Exits:
        With code 130 if user cancels with Ctrl-C
    """
    try:
        return getpass(label)
    except (KeyboardInterrupt, EOFError):
        _print_cancelled()
        raise SystemExit(CANCELLED_EXIT) from None


def confirm_prompt(message: str, default: bool = False) -> bool:
    """
    Safe confirmation prompt that handles Ctrl-C gracefully.

    Args:
        message: Confirmation message to display
        default: Default value if user just presses Enter (False = "No", True = "Yes")

    Returns:
        True if user confirms, False otherwise

    Exits:
        With code 130 if user cancels with Ctrl-C
    """
    suffix = " (Y/n): " if default else " (y/N): "
    full_prompt = message + suffix

    try:
        response = input(full_prompt).strip().lower()

        if not response:  # User pressed Enter without input
            return default

        if response in ["y", "yes"]:
            return True
        elif response in ["n", "no"]:
            return False
        else:
            print("Please answer 'y' or 'n'")
            return confirm_prompt(message, default)  # Re-prompt for invalid input

    except (KeyboardInterrupt, EOFError):
        _print_cancelled()
        raise SystemExit(CANCELLED_EXIT) from None
