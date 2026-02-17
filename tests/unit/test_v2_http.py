"""Tests for v2 SDK HTTP client."""

import pytest
import responses

from m8tes._exceptions import (
    APIError,
    AuthenticationError,
    NotFoundError,
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
    def test_non_json_error_body(self, http):
        responses.add(responses.GET, "https://api.m8tes.ai/v2/x", body="Server Error", status=500)
        with pytest.raises(APIError) as exc_info:
            http.request("GET", "/x")
        assert "Server Error" in exc_info.value.message


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
