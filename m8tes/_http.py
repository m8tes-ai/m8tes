"""Thin HTTP client wrapping requests.Session with auth, error mapping, and retry."""

import logging
import time
from typing import Any

import requests

from ._exceptions import STATUS_MAP, APIError

logger = logging.getLogger(__name__)

# Retry config
_MAX_RETRIES = 3
_INITIAL_BACKOFF = 0.5  # seconds
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def _raise_for_status(resp: requests.Response, *, method: str = "", path: str = "") -> None:
    """Map HTTP error responses to typed SDK exceptions."""
    # Try to parse structured error from v2 API
    message = f"HTTP {resp.status_code}"
    request_id = None
    try:
        body = resp.json()
        # v2 API returns {"error": {"code", "message", "request_id"}}
        error_obj = body.get("error", {})
        message = error_obj.get("message", body.get("detail", message))
        request_id = error_obj.get("request_id", body.get("request_id"))
    except (ValueError, KeyError):
        logger.debug("Failed to parse error body: %s", resp.text[:200] if resp.text else "empty")
        message = resp.text or message

    resp.close()
    exc_cls = STATUS_MAP.get(resp.status_code, APIError)
    raise exc_cls(
        message, status_code=resp.status_code, request_id=request_id, method=method, path=path
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
        self, method: str, url: str, *, is_stream: bool = False, **kwargs: Any
    ) -> requests.Response:
        """Send request with retry on 429/5xx. Respects Retry-After header."""
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                resp = self._session.request(
                    method, url, timeout=self._timeout, stream=is_stream, **kwargs
                )
            except (requests.Timeout, requests.ConnectionError) as e:
                last_exc = e
                logger.warning("Request failed (attempt %d/%d): %s", attempt + 1, _MAX_RETRIES, e)
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(_INITIAL_BACKOFF * (2**attempt))
                    continue
                raise APIError(str(e), status_code=None) from e

            if resp.ok:
                return resp

            if resp.status_code not in _RETRYABLE_STATUS or attempt == _MAX_RETRIES - 1:
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
        return self._request_with_retry(method, f"{self._base_url}{path}", **kwargs)

    def stream(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        """Send request with stream=True for SSE parsing."""
        return self._request_with_retry(method, f"{self._base_url}{path}", is_stream=True, **kwargs)
