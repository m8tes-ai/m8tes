"""Validated prompt functions for CLI input with automatic retry on invalid input."""

from ..utils.validation import validate_email, validate_password
from .prompt import prompt, secure_prompt


def prompt_email(label: str = "📧 Email: ") -> str:
    """
    Prompt for email with validation and automatic retry.

    Args:
        label: Prompt message to display

    Returns:
        Valid email address
    """
    while True:
        email = prompt(label)
        error = validate_email(email)
        if not error:
            return email
        print(f"❌ {error}")


def prompt_password(label: str = "🔐 Password: ") -> str:
    """
    Prompt for password with validation and automatic retry.

    Args:
        label: Prompt message to display

    Returns:
        Valid password
    """
    while True:
        password = secure_prompt(label)
        error = validate_password(password)
        if not error:
            return password
        print(f"❌ {error}")


def prompt_password_confirm(
    password_label: str = "🔐 Password: ", confirm_label: str = "🔐 Confirm password: "
) -> str:
    """
    Prompt for password with confirmation and validation.

    Args:
        password_label: Label for password prompt
        confirm_label: Label for confirmation prompt

    Returns:
        Valid, confirmed password
    """
    while True:
        password = prompt_password(password_label)
        confirm = secure_prompt(confirm_label)

        if password == confirm:
            return password
        print("❌ Passwords do not match")
