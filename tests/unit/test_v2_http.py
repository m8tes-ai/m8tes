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
