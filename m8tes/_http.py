"""Thin HTTP client wrapping requests.Session with auth, error mapping, and retry."""

import logging
import re
import time
from typing import Any

import requests

from ._exceptions import STATUS_MAP, APIError

logger = logging.getLogger(__name__)

# Retry config
_MAX_RETRIES = 3
_INITIAL_BACKOFF = 0.5  # seconds
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_SAFE_RETRY_METHODS = {"GET", "HEAD", "PUT", "DELETE", "OPTIONS"}

# Header that makes a POST safe to repeat. The server binds the key to the run the
# first request produced and replays that run for every repeat, so re-sending
# cannot start (or bill) a second one.
IDEMPOTENCY_HEADER = "Idempotency-Key"
# Set by the API when the response is a replay rather than a fresh result.
REPLAY_HEADER = "Idempotent-Replay"


# The ONLY routes whose POST the server makes idempotent. Retry eligibility is
# checked against this list as well as the header, because the header alone is not
# evidence the server will honour it: a caller who sets `Idempotency-Key` at client
# level (or passes it to an unrelated POST) would otherwise make EVERY POST
# retryable — including `tasks.create`, which has no server-side idempotency, so a
# timed-out create would be re-sent and duplicate the task. Found in review.
#
# Matched against the path RELATIVE to base_url, and fully anchored. An earlier
# version matched suffixes, which also accepted `/foo/reply` and `/foo/runs` — the
# low-level transport is public (`client.request(...)`), so an unsupported path
# could have been retried on a route that ignores the key. Anchoring is the whole
# point of the check, so it must not be approximate.
_IDEMPOTENT_POST_PATHS = (
    re.compile(r"^/runs/?$"),
    re.compile(r"^/runs/with-files/?$"),
    re.compile(r"^/runs/\d+/reply/?$"),
    re.compile(r"^/runs/\d+/reply/with-files/?$"),
    re.compile(r"^/tasks/\d+/runs/?$"),
)


def _is_idempotent_route(path: str) -> bool:
    """True when the server implements Idempotency-Key for this POST path.

    `path` is relative to base_url (what the resource methods pass), never the full
    URL — matching a full URL cannot be anchored, which is how the suffix version
    let `/foo/reply` through.
    """
    clean = path.split("?", 1)[0]
    return any(p.match(clean) for p in _IDEMPOTENT_POST_PATHS)


def _is_retryable(method: str, path: str, kwargs: dict) -> bool:
    """Whether this request may be re-sent after a timeout or 5xx.

    GET/HEAD/PUT/DELETE/OPTIONS always are. A POST is retryable ONLY when it both
    carries an `Idempotency-Key` AND targets a route the server makes idempotent.
    Without a key, a POST that timed out may already have started a billable run and
    re-sending it would charge twice; with a key on a route that ignores it, the
    retry is just a duplicate side effect wearing a safety label.
    """
    if method.upper() in _SAFE_RETRY_METHODS:
        return True
    headers = kwargs.get("headers") or {}
    has_key = any(k.lower() == IDEMPOTENCY_HEADER.lower() for k in headers)
    return has_key and _is_idempotent_route(path)


# Canonical hosted API. Shared by the v2 client, the module-level auth helpers,
# and error hints so a host change is a one-line edit.
DEFAULT_BASE_URL = "https://api.m8tes.ai/api/v2"


def _looks_like_html(resp: requests.Response) -> bool:
    """Detect HTML error responses (a web server answering instead of the API)."""
    if "text/html" in resp.headers.get("Content-Type", ""):
        return True
    head = (resp.text or "").lstrip()[:9].lower()
    return head.startswith("<!doctype") or head.startswith("<html")


def _raise_for_status(resp: requests.Response, *, method: str = "", path: str = "") -> None:
    """Map HTTP error responses to typed SDK exceptions."""
    # Try to parse structured error from v2 API
    message = f"HTTP {resp.status_code}"
    request_id = None
    code = None
    details: dict | None = None
    doc_url = None
    try:
        body = resp.json()
        # v2 API returns {"error": {"type", "message", "code", "request_id",
        # "details": {"error_code", ...extra}}}. The machine-readable app code
        # lives in error.details.error_code (see fastapi/app/exceptions.py) — the
        # top-level error.code is the int HTTP status. Surfacing the nested code
        # is what makes exc.code == "RUN_LIMIT_REACHED" instead of None.
        error_obj = body.get("error", {})
        if resp.status_code == 404 and "error" not in body and body.get("detail") == "Not Found":
            # FastAPI's bare route-level 404 (no v2 error envelope): the host serves
            # the m8tes backend but the PATH didn't match any route — almost always a
            # base_url missing its /api/v2 prefix. A real v2 "resource not found"
            # arrives enveloped and never takes this branch.
            message = (
                f"HTTP 404 from {resp.url} with no API error envelope — the path matched "
                f"no route. Check your base_url includes the /api/v2 prefix "
                f"(the hosted API is {DEFAULT_BASE_URL})."
            )
        elif isinstance(error_obj, str):
            # Proxy/gateway may return {"error": "plain string"} instead of dict
            message = error_obj
        else:
            message = error_obj.get("message", body.get("detail", message))
            request_id = error_obj.get("request_id", body.get("request_id"))
            raw_doc_url = error_obj.get("doc_url")
            doc_url = raw_doc_url if isinstance(raw_doc_url, str) else None
            raw_details = error_obj.get("details")
            details = raw_details if isinstance(raw_details, dict) else None
            # Prefer the nested machine code (RUN_LIMIT_REACHED, OVERAGE_CAP_REACHED,
            # TRIAL_EXPIRED, ...). Fall back to a top-level string code for codes
            # that aren't nested. Ints are HTTP statuses — not useful to callers.
            nested_code = details.get("error_code") if details else None
            raw_code = error_obj.get("code")
            if isinstance(nested_code, str):
                code = nested_code
            elif isinstance(raw_code, str):
                code = raw_code
    except (ValueError, KeyError, AttributeError):
        logger.debug("Failed to parse error body: %s", resp.text[:200] if resp.text else "empty")
        if _looks_like_html(resp):
            # A web server answered, not the API (e.g. base_url pointing at the
            # marketing site). Dumping the HTML document into the exception buries
            # the actual problem; say what is wrong instead.
            message = (
                f"Received an HTML page instead of an API response (HTTP {resp.status_code}) "
                f"from {resp.url}. This usually means the host does not serve the m8tes API; "
                f"check your base_url (the hosted API is {DEFAULT_BASE_URL})."
            )
        else:
            message = resp.text or message

    # Expose Retry-After (delta-seconds form) so callers can back off; the API
    # sends it on 429s. A non-numeric value (e.g. an HTTP-date) maps to None.
    retry_after: float | None = None
    raw_retry = resp.headers.get("Retry-After")
    if raw_retry:
        try:
            retry_after = float(raw_retry)
        except ValueError:
            retry_after = None

    resp.close()
    exc_cls = STATUS_MAP.get(resp.status_code, APIError)
    raise exc_cls(
        message,
        status_code=resp.status_code,
        request_id=request_id,
        method=method,
        path=path,
        code=code,
        retry_after=retry_after,
        details=details,
        doc_url=doc_url,
    )


class HTTPClient:
    """Minimal HTTP client with Bearer auth, error mapping, and automatic retry."""

    def __init__(self, api_key: str, base_url: str, timeout: int = 300):
        self._session = requests.Session()
        self._session.headers["Authorization"] = f"Bearer {api_key}"
        self._session.headers["Content-Type"] = "application/json"
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def _request_with_retry(
        self, method: str, url: str, *, path: str = "", is_stream: bool = False, **kwargs: Any
    ) -> requests.Response:
        """Send request with retry on 429/5xx. Respects Retry-After header."""
        if "files" in kwargs:
            # Multipart upload: drop the session-level JSON Content-Type so
            # requests sets multipart/form-data with its boundary instead.
            headers = dict(kwargs.get("headers") or {})
            headers.setdefault("Content-Type", None)
            kwargs["headers"] = headers
        retryable = _is_retryable(method, path, kwargs)
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                resp = self._session.request(
                    method, url, timeout=self._timeout, stream=is_stream, **kwargs
                )
            except (requests.Timeout, requests.ConnectionError) as e:
                last_exc = e
                logger.warning("Request failed (attempt %d/%d): %s", attempt + 1, _MAX_RETRIES, e)
                # This is the case idempotency keys exist for: the request may have
                # reached the server and started a billable run, and we cannot tell.
                # With a key, re-sending returns that same run; without one, fail
                # immediately and let the caller decide. Mirrors the status guard below.
                if not retryable or attempt >= _MAX_RETRIES - 1:
                    raise APIError(str(e), status_code=None) from e
                time.sleep(_INITIAL_BACKOFF * (2**attempt))
                continue

            if resp.ok:
                return resp

            if (
                resp.status_code not in _RETRYABLE_STATUS
                or not retryable
                or attempt == _MAX_RETRIES - 1
            ):
                _raise_for_status(resp, method=method, path=url)

            # Retry after delay
            retry_after = resp.headers.get("Retry-After")
            if retry_after and resp.status_code == 429:
                try:
                    delay = float(retry_after)
                except ValueError:
                    logger.debug("Unparseable Retry-After header: %s", retry_after)
                    delay = _INITIAL_BACKOFF * (2**attempt)
            else:
                delay = _INITIAL_BACKOFF * (2**attempt)
            logger.debug(
                "Retrying %s %s (attempt %d, delay %.1fs)", method, url, attempt + 1, delay
            )
            time.sleep(delay)

        # Should not reach here, but just in case
        if last_exc:
            raise APIError(str(last_exc), status_code=None) from last_exc
        raise APIError("Max retries exceeded", status_code=None)

    def request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        """Send request and raise typed exception on error."""
        return self._request_with_retry(method, f"{self._base_url}{path}", path=path, **kwargs)

    def stream(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        """Send request with stream=True for SSE parsing."""
        return self._request_with_retry(
            method, f"{self._base_url}{path}", path=path, is_stream=True, **kwargs
        )
