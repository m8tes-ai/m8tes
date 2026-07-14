"""Tests for v2 SDK HTTP client."""

import pytest
import responses

from m8tes._exceptions import (
    APIError,
    AuthenticationError,
    BillingError,
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
    def test_rate_limit_exposes_retry_after(self, http):
        """RateLimitError.retry_after carries the Retry-After header (seconds) for backoff."""
        responses.add(
            responses.POST,
            "https://api.m8tes.ai/v2/runs",
            json={"error": {"message": "slow down"}},
            status=429,
            headers={"Retry-After": "30"},
        )
        with pytest.raises(RateLimitError) as exc_info:
            http.request("POST", "/runs")
        assert exc_info.value.retry_after == 30.0

    @responses.activate
    def test_retry_after_absent_is_none(self, http):
        """Errors without a Retry-After header expose retry_after=None, not a crash."""
        responses.add(
            responses.POST,
            "https://api.m8tes.ai/v2/runs",
            json={"error": {"message": "bad"}},
            status=400,
        )
        with pytest.raises(ValidationError) as exc_info:
            http.request("POST", "/runs")
        assert exc_info.value.retry_after is None

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
    def test_html_error_body_hints_base_url(self, http):
        """An HTML error page (wrong host / SPA fallback) must produce a base_url hint,
        not dump the raw HTML document into the exception message."""
        responses.add(
            responses.GET,
            "https://api.m8tes.ai/v2/teammates",
            body="<!DOCTYPE html><html><head><title>m8tes</title></head></html>",
            status=404,
            content_type="text/html",
        )
        with pytest.raises(NotFoundError) as exc_info:
            http.request("GET", "/teammates")
        assert "base_url" in exc_info.value.message
        assert "https://api.m8tes.ai/api/v2" in exc_info.value.message
        assert "<!DOCTYPE" not in exc_info.value.message

    @responses.activate
    def test_html_body_without_content_type_hints_base_url(self, http):
        """HTML detection must also work when the server omits the text/html content type."""
        responses.add(
            responses.GET,
            "https://api.m8tes.ai/v2/teammates",
            body="  <html><body>Not Found</body></html>",
            status=404,
            content_type="text/plain",
        )
        with pytest.raises(NotFoundError) as exc_info:
            http.request("GET", "/teammates")
        assert "base_url" in exc_info.value.message
        assert "<html>" not in exc_info.value.message

    @responses.activate
    def test_plain_json_404_hints_base_url(self, http):
        """A bare FastAPI 404 ({"detail": "Not Found"}, no v2 error envelope) means the
        HOST is right but the path prefix is wrong (e.g. base_url missing /api/v2) —
        the exception must say so instead of an unactionable 'Not Found'."""
        responses.add(
            responses.GET,
            "https://api.m8tes.ai/v2/runs",
            json={"detail": "Not Found"},
            status=404,
        )
        with pytest.raises(NotFoundError) as exc_info:
            http.request("GET", "/runs")
        assert "base_url" in exc_info.value.message
        assert "https://api.m8tes.ai/api/v2" in exc_info.value.message

    @responses.activate
    def test_enveloped_404_keeps_api_message(self, http):
        """A REAL v2 404 (resource not found, proper error envelope) must keep the
        API's message untouched — no base_url noise on legitimate lookups."""
        responses.add(
            responses.GET,
            "https://api.m8tes.ai/v2/runs/999",
            json={
                "error": {
                    "type": "not_found",
                    "message": "Run not found",
                    "code": 404,
                    "request_id": "req_x",
                }
            },
            status=404,
        )
        with pytest.raises(NotFoundError) as exc_info:
            http.request("GET", "/runs/999")
        assert exc_info.value.message == "Run not found"
        assert "base_url" not in exc_info.value.message

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


class TestNestedBillingCode:
    """The machine code lives in error.details.error_code, not error.code.

    Regression for the bug where BillingError.code was always None because the
    SDK read the top-level int HTTP status as the code.
    """

    @responses.activate
    def test_402_run_limit_reached_surfaces_code(self, http):
        responses.add(
            responses.POST,
            "https://api.m8tes.ai/v2/runs",
            json={
                "error": {
                    "type": "billing_error",
                    "message": "Run limit reached (100/month).",
                    "code": 402,  # int HTTP status — must NOT become exc.code
                    "request_id": "req_x",
                    "details": {
                        "error_code": "RUN_LIMIT_REACHED",
                        "plan": "pro",
                        "runs_used": 100,
                        "runs_limit": 100,
                        "overage_available": True,
                    },
                }
            },
            status=402,
        )
        with pytest.raises(BillingError) as exc_info:
            http.request("POST", "/runs")
        exc = exc_info.value
        assert exc.code == "RUN_LIMIT_REACHED"  # not None, not 402
        assert exc.details["runs_limit"] == 100
        assert exc.details["overage_available"] is True

    @responses.activate
    def test_402_overage_cap_reached_surfaces_code(self, http):
        responses.add(
            responses.POST,
            "https://api.m8tes.ai/v2/runs",
            json={
                "error": {
                    "type": "billing_error",
                    "message": "Overage cap reached ($50).",
                    "code": 402,
                    "details": {
                        "error_code": "OVERAGE_CAP_REACHED",
                        "overage_used_cents": 5000,
                        "overage_cap_cents": 5000,
                    },
                }
            },
            status=402,
        )
        with pytest.raises(BillingError) as exc_info:
            http.request("POST", "/runs")
        assert exc_info.value.code == "OVERAGE_CAP_REACHED"
        assert exc_info.value.details["overage_cap_cents"] == 5000

    @responses.activate
    def test_falls_back_to_top_level_string_code(self, http):
        """Codes not nested in details still surface from a top-level string code."""
        responses.add(
            responses.POST,
            "https://api.m8tes.ai/v2/runs/1/retry",
            json={"error": {"message": "Confirm retry", "code": "retry_needs_confirmation"}},
            status=409,
        )
        with pytest.raises(ConflictError) as exc_info:
            http.request("POST", "/runs/1/retry")
        assert exc_info.value.code == "retry_needs_confirmation"

    @responses.activate
    def test_no_code_is_none_with_empty_details(self, http):
        responses.add(
            responses.GET, "https://api.m8tes.ai/v2/x", json={"detail": "boom"}, status=404
        )
        with pytest.raises(NotFoundError) as exc_info:
            http.request("GET", "/x")
        assert exc_info.value.code is None
        assert exc_info.value.details == {}


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

    def test_post_not_retried_on_timeout(self, http):
        """POST timeout must not be retried — the run may have already started server-side,
        so re-sending risks a duplicate billable run."""
        from unittest.mock import MagicMock

        import requests as req_lib

        http._session.request = MagicMock(side_effect=req_lib.Timeout("read timed out"))
        with pytest.raises(APIError):
            http.request("POST", "/runs")
        assert http._session.request.call_count == 1

    def test_post_not_retried_on_connection_error(self, http):
        """POST connection error must not be retried — risk of duplicate billable run."""
        from unittest.mock import MagicMock

        import requests as req_lib

        http._session.request = MagicMock(side_effect=req_lib.ConnectionError("reset"))
        with pytest.raises(APIError):
            http.request("POST", "/runs")
        assert http._session.request.call_count == 1

    def test_get_retried_on_timeout(self, http):
        """GET is idempotent — a timeout should still be retried up to the max."""
        from unittest.mock import MagicMock

        import requests as req_lib

        http._session.request = MagicMock(side_effect=req_lib.Timeout("read timed out"))
        with pytest.raises(APIError):
            http.request("GET", "/x")
        assert http._session.request.call_count > 1

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
