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
        doc_url: str | None = None,
        error_code: str | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.request_id = request_id
        self.method = method
        self.path = path
        # Docs deep link for this error type, from the envelope's error.doc_url
        # (e.g. https://m8tes.ai/docs/api-introduction#authentication on a 401).
        self.doc_url = doc_url
        # App-level machine error code from the v2 envelope's error.details.error_code
        # (e.g. "RUN_LIMIT_REACHED", "OVERAGE_CAP_REACHED", "TRIAL_EXPIRED"). Falls
        # back to a top-level string code when no nested code is present.
        self.code = code
        # The semantic error code from the envelope's top-level error.error_code
        # (newer backends), falling back to error.details.error_code (current prod).
        # Branch on this rather than parsing the message; None when the server sent
        # neither. Never the int HTTP status — that stays on `status_code`.
        self.error_code = error_code
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
    """400 or 422 — invalid request (check .status_code to tell them apart)."""


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


class StreamInterruptedError(M8tesError):
    """The STREAM stopped before the run did: a dropped connection, a proxy that cut
    a long response, a read timeout.

    It says nothing about the run. The API detaches a run from the response that
    started it, so the run was not stopped by this and is very likely still working.
    `.run_id` is the run to go back to: wait for the result with
    `client.runs.wait(run_id)`, or rejoin the stream with `client.runs.stream(run_id)`.
    Never send the request again; that starts a second run.

    `.run_id` is None only when the connection died before the server named a run.
    `.reason` is the plain cause, and `__cause__` is the underlying error when there
    was one. Mirrors `StreamInterruptedError` in `@m8tes/sdk`.
    """

    def __init__(self, run_id: int | None, reason: str):
        if run_id is None:
            message = (
                f"The stream was interrupted before the server named the run: {reason}. "
                "A run may have started. Check client.runs.list() before sending the "
                "request again, or you may start a second one."
            )
        else:
            message = (
                f"The stream for run {run_id} was interrupted: {reason}. The run was not "
                f"stopped and may still be working. Wait for the result with "
                f"client.runs.wait({run_id}), or rejoin it with client.runs.stream({run_id}). "
                "Do not send the request again: that starts a second run."
            )
        super().__init__(
            message,
            code="stream_interrupted",
            error_code="stream_interrupted",
            details={"run_id": run_id, "reason": reason},
        )
        self.run_id = run_id
        self.reason = reason


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
