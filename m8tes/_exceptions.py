"""Typed error hierarchy mapping HTTP status codes from the v2 API."""


class M8tesError(Exception):
    """Base exception for all m8tes SDK errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        request_id: str | None = None,
        method: str | None = None,
        path: str | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.request_id = request_id
        self.method = method
        self.path = path


class AuthenticationError(M8tesError):
    """401 — invalid or missing API key."""


class PermissionDeniedError(M8tesError):
    """403 — insufficient permissions."""


class NotFoundError(M8tesError):
    """404 — resource does not exist."""


class ConflictError(M8tesError):
    """409 — resource already exists or conflicts."""


class ValidationError(M8tesError):
    """422 — invalid request parameters."""


class RateLimitError(M8tesError):
    """429 — too many requests."""


class APIError(M8tesError):
    """500+ — server-side error."""


# Map HTTP status codes to exception classes.
STATUS_MAP: dict[int, type[M8tesError]] = {
    400: ValidationError,
    401: AuthenticationError,
    403: PermissionDeniedError,
    404: NotFoundError,
    409: ConflictError,
    422: ValidationError,
    429: RateLimitError,
}
