"""
Exception classes for m8tes SDK.
"""

from typing import Any


class M8tesError(Exception):
    """Base exception for all m8tes errors."""

    def __init__(self, message: str, code: str | None = None, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


class AuthenticationError(M8tesError):
    """Raised when authentication fails."""

    @classmethod
    def no_api_key(cls) -> "AuthenticationError":
        """Create error for missing API key with helpful guidance."""
        message = (
            "No API key provided. Choose one of:\n"
            "  • Register: m8tes auth register\n"
            "  • Login: m8tes auth login\n"
            '  • Set environment variable: export M8TES_API_KEY="your-key"\n'
        )
        return cls(message, code="no_api_key")

    @classmethod
    def invalid_api_key(cls) -> "AuthenticationError":
        """Create error for invalid API key with helpful guidance."""
        message = (
            "Invalid API key. Try:\n"
            "  • Login with fresh credentials: m8tes auth login\n"
            "  • Register new account: m8tes auth register\n"
            "  • Check your API key is correct"
        )
        return cls(message, code="invalid_api_key")

    @classmethod
    def access_forbidden(cls) -> "AuthenticationError":
        """Create error for access forbidden with helpful guidance."""
        message = (
            "Unexpected error occurred. Please try again.\n"
            "If the problem persists:\n"
            "  • Use: m8tes --help\n"
            "  • Contact support if needed"
        )
        return cls(message, code="access_forbidden")


class AgentError(M8tesError):
    """Raised when agent operations fail."""


class DeploymentError(M8tesError):
    """Raised when deployment operations fail."""


class IntegrationError(M8tesError):
    """Raised when integration operations fail."""


class NetworkError(M8tesError):
    """Raised when network requests fail."""


class RateLimitError(M8tesError):
    """Raised when rate limits are exceeded."""

    def __init__(self, message: str, retry_after: int | None = None, **kwargs: Any) -> None:
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class ValidationError(M8tesError):
    """Raised when input validation fails."""


class TimeoutError(M8tesError):
    """Raised when operations timeout."""


class OAuthError(M8tesError):
    """Raised when OAuth operations fail."""

    def __init__(
        self,
        message: str,
        code: str | None = None,
        state: str | None = None,
        error_uri: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, code, **kwargs)
        self.state = state
        self.error_uri = error_uri
