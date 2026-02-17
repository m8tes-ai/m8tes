"""Thin HTTP client wrapping requests.Session with auth and error mapping."""

import logging

import requests

from ._exceptions import STATUS_MAP, APIError

logger = logging.getLogger(__name__)


def _raise_for_status(resp: requests.Response) -> None:
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
    except Exception:
        message = resp.text or message

    exc_cls = STATUS_MAP.get(resp.status_code, APIError)
    raise exc_cls(message, status_code=resp.status_code, request_id=request_id)


class HTTPClient:
    """Minimal HTTP client with Bearer auth and error mapping."""

    def __init__(self, api_key: str, base_url: str, timeout: int = 300):
        self._session = requests.Session()
        self._session.headers["Authorization"] = f"Bearer {api_key}"
        self._session.headers["Content-Type"] = "application/json"
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        """Send request and raise typed exception on error."""
        resp = self._session.request(
            method, f"{self._base_url}{path}", timeout=self._timeout, **kwargs
        )
        if not resp.ok:
            _raise_for_status(resp)
        return resp

    def stream(self, method: str, path: str, **kwargs) -> requests.Response:
        """Send request with stream=True for SSE parsing."""
        resp = self._session.request(
            method, f"{self._base_url}{path}", timeout=self._timeout, stream=True, **kwargs
        )
        if not resp.ok:
            _raise_for_status(resp)
        return resp
