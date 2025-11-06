"""Simple validation utilities for user inputs."""

import re


def validate_email(email: str) -> str | None:
    """
    Validate email format.

    Args:
        email: Email address to validate

    Returns:
        Error message if invalid, None if valid
    """
    if not email:
        return "Email is required"

    # Simple but effective email regex - prevents leading/trailing dots
    pattern = (
        r"^[a-zA-Z0-9]([a-zA-Z0-9._%+-]*[a-zA-Z0-9])?"
        r"@[a-zA-Z0-9]([a-zA-Z0-9.-]*[a-zA-Z0-9])?\.[a-zA-Z]{2,}$"
    )
    if not re.match(pattern, email):
        return "Please enter a valid email address"

    return None


def validate_password(password: str) -> str | None:
    """
    Validate password requirements.

    Args:
        password: Password to validate

    Returns:
        Error message if invalid, None if valid
    """
    if not password:
        return "Password is required"

    if password.strip() == "":
        return "Password cannot be only whitespace"

    if len(password) < 8:
        return "Password must be at least 8 characters"

    return None
