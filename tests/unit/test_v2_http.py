"""Tests for v2 SDK HTTP client."""

import pytest
import responses

from m8tes._exceptions import (
    APIError,
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ValidationError,
)
from m8tes._http import HTTPClient


@pytest.fixture
def http():
    return HTTPClient(api_key="m8_test123", base_url="https://api.m8tes.ai/v2", timeout=10)


class TestHTTPClient:
    @responses.activate
    def test_auth_header(self, http):
        responses.add(responses.GET, "https://api.m8tes.ai/v2/teammates", json=[], status=200)
        http.request("GET", "/teammates")
        assert responses.calls[0].request.headers["Authorization"] == "Bearer m8_test123"

    @responses.activate
    def test_base_url_joined(self, http):
        responses.add(responses.GET, "https://api.m8tes.ai/v2/teammates", json=[], status=200)
        http.request("GET", "/teammates")
        assert responses.calls[0].request.url == "https://api.m8tes.ai/v2/teammates"

    @responses.activate
    def test_trailing_slash_stripped(self):
        client = HTTPClient(api_key="k", base_url="https://api.m8tes.ai/v2/", timeout=5)
        responses.add(responses.GET, "https://api.m8tes.ai/v2/apps", json=[], status=200)
        client.request("GET", "/apps")
        assert responses.calls[0].request.url == "https://api.m8tes.ai/v2/apps"


class TestErrorMapping:
    @responses.activate
    def test_401_raises_auth_error(self, http):
        responses.add(
            responses.GET, "https://api.m8tes.ai/v2/x", json={"detail": "Bad key"}, status=401
        )
        with pytest.raises(AuthenticationError) as exc_info:
            http.request("GET", "/x")
        assert exc_info.value.status_code == 401
        assert "Bad key" in exc_info.value.message

    @responses.activate
    def test_403_raises_permission_denied(self, http):
        responses.add(
            responses.GET, "https://api.m8tes.ai/v2/x", json={"detail": "Forbidden"}, status=403
        )
        with pytest.raises(PermissionDeniedError) as exc_info:
            http.request("GET", "/x")
        assert exc_info.value.status_code == 403

    @responses.activate
    def test_409_raises_conflict(self, http):
        responses.add(
            responses.POST,
            "https://api.m8tes.ai/v2/memories",
            json={"error": {"message": "Duplicate memory", "code": "conflict"}},
            status=409,
        )
        with pytest.raises(ConflictError) as exc_info:
            http.request("POST", "/memories")
        assert exc_info.value.status_code == 409
        assert "Duplicate" in exc_info.value.message

    @responses.activate
    def test_404_raises_not_found(self, http):
        responses.add(
            responses.GET, "https://api.m8tes.ai/v2/x", json={"detail": "Not found"}, status=404
        )
        with pytest.raises(NotFoundError):
            http.request("GET", "/x")

    @responses.activate
    def test_422_raises_validation(self, http):
        responses.add(
            responses.POST, "https://api.m8tes.ai/v2/x", json={"detail": "Bad input"}, status=422
        )
        with pytest.raises(ValidationError):
            http.request("POST", "/x")

    @responses.activate
    def test_429_raises_rate_limit(self, http):
        responses.add(
            responses.GET, "https://api.m8tes.ai/v2/x", json={"detail": "Slow down"}, status=429
        )
        with pytest.raises(RateLimitError):
            http.request("GET", "/x")

    @responses.activate
    def test_500_raises_api_error(self, http):
        responses.add(
            responses.GET, "https://api.m8tes.ai/v2/x", json={"detail": "Boom"}, status=500
        )
        with pytest.raises(APIError) as exc_info:
            http.request("GET", "/x")
        assert exc_info.value.status_code == 500

    @responses.activate
    def test_request_id_parsed(self, http):
        responses.add(
            responses.GET,
            "https://api.m8tes.ai/v2/x",
            json={"detail": "err", "request_id": "req_abc"},
            status=500,
        )
        with pytest.raises(APIError) as exc_info:
            http.request("GET", "/x")
        assert exc_info.value.request_id == "req_abc"

    @responses.activate
    def test_error_includes_method_and_path(self, http):
        responses.add(
            responses.POST, "https://api.m8tes.ai/v2/runs", json={"detail": "err"}, status=422
        )
        with pytest.raises(ValidationError) as exc_info:
            http.request("POST", "/runs")
        assert exc_info.value.method == "POST"
        assert "runs" in exc_info.value.path

    @responses.activate
    def test_non_json_error_body(self, http):
        responses.add(responses.GET, "https://api.m8tes.ai/v2/x", body="Server Error", status=500)
        with pytest.raises(APIError) as exc_info:
            http.request("GET", "/x")
        assert "Server Error" in exc_info.value.message

    @responses.activate
    def test_string_error_body(self, http):
        """API/proxy returning {"error": "string"} instead of {"error": {...}} must not crash."""
        responses.add(
            responses.POST,
            "https://api.m8tes.ai/v2/runs",
            json={"error": "something went wrong"},
            status=400,
        )
        with pytest.raises(ValidationError) as exc_info:
            http.request("POST", "/runs")
        assert "something went wrong" in exc_info.value.message


class TestRetryLogic:
    """Retry behaviour: 429/5xx retried up to 3 times, network errors retried."""

    @responses.activate
    def test_retries_429_then_succeeds(self, http):
        """429 followed by 200 should succeed without raising."""
        responses.add(responses.GET, "https://api.m8tes.ai/v2/x", json={}, status=429)
        responses.add(responses.GET, "https://api.m8tes.ai/v2/x", json={"ok": True}, status=200)
        resp = http.request("GET", "/x")
        assert resp.status_code == 200
        assert len(responses.calls) == 2

    @responses.activate
    def test_retries_500_then_succeeds(self, http):
        """500 followed by 200 should succeed."""
        responses.add(responses.GET, "https://api.m8tes.ai/v2/x", json={}, status=500)
        responses.add(responses.GET, "https://api.m8tes.ai/v2/x", json={"ok": True}, status=200)
        resp = http.request("GET", "/x")
        assert resp.status_code == 200
        assert len(responses.calls) == 2

    @responses.activate
    def test_retries_502_503_504(self, http):
        """All 5xx retryable codes should be retried."""
        for status in (502, 503, 504):
            responses.reset()
            responses.add(responses.GET, "https://api.m8tes.ai/v2/x", json={}, status=status)
            responses.add(responses.GET, "https://api.m8tes.ai/v2/x", json={}, status=200)
            resp = http.request("GET", "/x")
            assert resp.status_code == 200

    @responses.activate
    def test_max_retries_exhausted_raises(self, http):
        """3x 500 should exhaust retries and raise APIError."""
        for _ in range(3):
            responses.add(
                responses.GET, "https://api.m8tes.ai/v2/x", json={"detail": "down"}, status=500
            )
        with pytest.raises(APIError) as exc_info:
            http.request("GET", "/x")
        assert exc_info.value.status_code == 500
        assert len(responses.calls) == 3

    @responses.activate
    def test_429_respects_retry_after_header(self, http):
        """429 with Retry-After header should use it (we just verify the request is retried)."""
        responses.add(
            responses.GET,
            "https://api.m8tes.ai/v2/x",
            json={},
            status=429,
            headers={"Retry-After": "0"},
        )
        responses.add(responses.GET, "https://api.m8tes.ai/v2/x", json={}, status=200)
        resp = http.request("GET", "/x")
        assert resp.status_code == 200

    @responses.activate
    def test_non_retryable_status_not_retried(self, http):
        """400 is not retryable — should fail immediately."""
        responses.add(
            responses.GET, "https://api.m8tes.ai/v2/x", json={"detail": "bad"}, status=400
        )
        with pytest.raises(ValidationError):
            http.request("GET", "/x")
        assert len(responses.calls) == 1

    def test_connection_error_retried_then_raises(self, http):
        """ConnectionError retried up to max, then raises APIError."""
        import requests as req_lib

        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET, "https://api.m8tes.ai/v2/x", body=req_lib.ConnectionError("refused")
            )
            rsps.add(
                responses.GET, "https://api.m8tes.ai/v2/x", body=req_lib.ConnectionError("refused")
            )
            rsps.add(
                responses.GET, "https://api.m8tes.ai/v2/x", body=req_lib.ConnectionError("refused")
            )
            with pytest.raises(APIError) as exc_info:
                http.request("GET", "/x")
            assert exc_info.value.status_code is None
            assert "refused" in exc_info.value.message


class TestRetrySemantics:
    """Only idempotent methods (GET, HEAD, PUT, DELETE, OPTIONS) should be retried on 429/5xx.
    POST/PATCH are non-idempotent and must fail immediately to avoid duplicate side effects."""

    def test_post_not_retried_on_500(self, http):
        """POST 500 must not be retried — could duplicate a create."""
        from unittest.mock import MagicMock

        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 500
        mock_resp.json.return_value = {"detail": "down"}
        mock_resp.text = "down"
        mock_resp.headers = {}
        http._session.request = MagicMock(return_value=mock_resp)
        with pytest.raises(APIError):
            http.request("POST", "/runs")
        assert http._session.request.call_count == 1

    def test_patch_not_retried_on_500(self, http):
        """PATCH 500 must not be retried — could apply partial update twice."""
        from unittest.mock import MagicMock

        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 500
        mock_resp.json.return_value = {"detail": "down"}
        mock_resp.text = "down"
        mock_resp.headers = {}
        http._session.request = MagicMock(return_value=mock_resp)
        with pytest.raises(APIError):
            http.request("PATCH", "/teammates/123")
        assert http._session.request.call_count == 1

    def test_post_not_retried_on_429(self, http):
        """POST 429 must not be retried — retrying could create duplicates."""
        from unittest.mock import MagicMock

        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 429
        mock_resp.json.return_value = {"detail": "rate limited"}
        mock_resp.text = "rate limited"
        mock_resp.headers = {}
        http._session.request = MagicMock(return_value=mock_resp)
        with pytest.raises(RateLimitError):
            http.request("POST", "/runs")
        assert http._session.request.call_count == 1

    def test_get_retried_on_500(self, http):
        """GET is idempotent — 500 should be retried."""
        from unittest.mock import MagicMock

        fail_resp = MagicMock()
        fail_resp.ok = False
        fail_resp.status_code = 500
        fail_resp.headers = {}

        ok_resp = MagicMock()
        ok_resp.ok = True
        ok_resp.status_code = 200

        http._session.request = MagicMock(side_effect=[fail_resp, ok_resp])
        resp = http.request("GET", "/teammates")
        assert resp.status_code == 200
        assert http._session.request.call_count == 2

    def test_delete_retried_on_429(self, http):
        """DELETE is idempotent — 429 should be retried."""
        from unittest.mock import MagicMock

        fail_resp = MagicMock()
        fail_resp.ok = False
        fail_resp.status_code = 429
        fail_resp.headers = {"Retry-After": "0"}

        ok_resp = MagicMock()
        ok_resp.ok = True
        ok_resp.status_code = 200

        http._session.request = MagicMock(side_effect=[fail_resp, ok_resp])
        resp = http.request("DELETE", "/teammates/123")
        assert resp.status_code == 200
        assert http._session.request.call_count == 2


class TestVersionConsistency:
    """Ensure version strings stay in sync across the codebase."""

    def test_no_hardcoded_version_in_legacy_client(self):
        """Legacy http/client.py must use __version__, not a hardcoded string."""
        import inspect

        from m8tes import __version__
        from m8tes.http.client import HTTPClient as LegacyHTTPClient

        source = inspect.getsource(LegacyHTTPClient)
        # Should reference __version__ dynamically, not contain a hardcoded "0.1.0"
        assert "0.1.0" not in source
        assert __version__ not in {"", None}
