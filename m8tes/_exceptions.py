"""Typed error hierarchy mapping HTTP status codes from the v2 API."""


class M8tesError(Exception):
    """Base exception for all m8tes SDK errors."""

    def __init__(self, message: str, status_code: int | None = None, request_id: str | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.request_id = request_id


class AuthenticationError(M8tesError):
    """401 — invalid or missing API key."""


class NotFoundError(M8tesError):
    """404 — resource does not exist."""


class ValidationError(M8tesError):
    """422 — invalid request parameters."""


class RateLimitError(M8tesError):
    """429 — too many requests."""


class APIError(M8tesError):
    """500+ — server-side error."""


# Map HTTP status codes to exception classes.
STATUS_MAP: dict[int, type[M8tesError]] = {
    401: AuthenticationError,
    403: AuthenticationError,
    404: NotFoundError,
    422: ValidationError,
    429: RateLimitError,
}
