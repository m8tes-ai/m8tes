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
        code: str | None = None,
        retry_after: float | None = None,
        details: dict | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.request_id = request_id
        self.method = method
        self.path = path
        # App-level machine error code from the v2 envelope's error.details.error_code
        # (e.g. "RUN_LIMIT_REACHED", "OVERAGE_CAP_REACHED", "TRIAL_EXPIRED"). Falls
        # back to a top-level string code when no nested code is present.
        self.code = code
        # Seconds to wait before retrying, from the Retry-After header. Set on
        # RateLimitError (429); None when the response carried no such header.
        self.retry_after = retry_after
        # The full error.details object — actionable context for billing errors
        # (e.g. runs_used, runs_limit, overage_cap_cents, period_end, trial_ends_at).
        self.details = details or {}


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


class BillingError(M8tesError):
    """402 — billing limit reached or subscription issue."""


class RateLimitError(M8tesError):
    """429 — too many requests."""


class APIError(M8tesError):
    """500+ — server-side error."""


class RunFailedError(M8tesError):
    """A streaming run emitted one or more error events (e.g. expired credential,
    model rate limit, quota exhaustion). Raised by RunStream when raise_on_error=True
    so a failed run is never silently treated as an empty success. `.details["errors"]`
    holds the raw error messages from the stream."""


# Map HTTP status codes to exception classes.
STATUS_MAP: dict[int, type[M8tesError]] = {
    400: ValidationError,
    401: AuthenticationError,
    402: BillingError,
    403: PermissionDeniedError,
    404: NotFoundError,
    409: ConflictError,
    422: ValidationError,
    429: RateLimitError,
}
