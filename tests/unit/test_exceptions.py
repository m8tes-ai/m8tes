"""Unit tests for exception classes."""

import pytest

from m8tes.exceptions import (
    AgentError,
    AuthenticationError,
    DeploymentError,
    IntegrationError,
    M8tesError,
    NetworkError,
    OAuthError,
    RateLimitError,
    TimeoutError,
    ValidationError,
)


@pytest.mark.unit
class TestM8tesError:
    """Test cases for base M8tesError class."""

    def test_basic_error_creation(self):
        """Test creating basic error with message."""
        error = M8tesError("Test error message")

        assert str(error) == "Test error message"
        assert error.message == "Test error message"
        assert error.code is None
        assert error.details == {}

    def test_error_with_code(self):
        """Test creating error with code."""
        error = M8tesError("Test error", code="TEST_ERROR")

        assert error.message == "Test error"
        assert error.code == "TEST_ERROR"

    def test_error_with_details(self):
        """Test creating error with details."""
        details = {"field": "value", "extra_info": 123}
        error = M8tesError("Test error", details=details)

        assert error.details == details

    def test_error_with_all_params(self):
        """Test creating error with all parameters."""
        details = {"field": "value"}
        error = M8tesError("Test message", code="TEST_CODE", details=details)

        assert error.message == "Test message"
        assert error.code == "TEST_CODE"
        assert error.details == details


@pytest.mark.unit
class TestAuthenticationError:
    """Test cases for AuthenticationError."""

    def test_authentication_error_inheritance(self):
        """Test that AuthenticationError inherits from M8tesError."""
        error = AuthenticationError("Auth failed")

        assert isinstance(error, M8tesError)
        assert isinstance(error, AuthenticationError)

    def test_authentication_error_with_code(self):
        """Test AuthenticationError with error code."""
        error = AuthenticationError("Invalid API key", code="INVALID_KEY")

        assert error.message == "Invalid API key"
        assert error.code == "INVALID_KEY"


@pytest.mark.unit
class TestRateLimitError:
    """Test cases for RateLimitError."""

    def test_rate_limit_error_basic(self):
        """Test basic RateLimitError creation."""
        error = RateLimitError("Rate limit exceeded")

        assert error.message == "Rate limit exceeded"
        assert error.retry_after is None

    def test_rate_limit_error_with_retry_after(self):
        """Test RateLimitError with retry_after parameter."""
        error = RateLimitError("Rate limited", retry_after=60)

        assert error.message == "Rate limited"
        assert error.retry_after == 60

    def test_rate_limit_error_with_all_params(self):
        """Test RateLimitError with all parameters."""
        error = RateLimitError(
            "Rate limit exceeded",
            code="RATE_LIMITED",
            retry_after=120,
            details={"limit": 100, "remaining": 0},
        )

        assert error.message == "Rate limit exceeded"
        assert error.code == "RATE_LIMITED"
        assert error.retry_after == 120
        assert error.details["limit"] == 100


@pytest.mark.unit
class TestOAuthError:
    """Test cases for OAuthError."""

    def test_oauth_error_basic(self):
        """Test basic OAuthError creation."""
        error = OAuthError("OAuth failed")

        assert error.message == "OAuth failed"
        assert error.state is None
        assert error.error_uri is None

    def test_oauth_error_with_state(self):
        """Test OAuthError with state parameter."""
        error = OAuthError("OAuth error", state="abc123")

        assert error.message == "OAuth error"
        assert error.state == "abc123"

    def test_oauth_error_with_error_uri(self):
        """Test OAuthError with error_uri parameter."""
        error = OAuthError("OAuth failed", error_uri="https://example.com/error")

        assert error.error_uri == "https://example.com/error"

    def test_oauth_error_with_all_params(self):
        """Test OAuthError with all parameters."""
        error = OAuthError(
            "Access denied",
            code="ACCESS_DENIED",
            state="state123",
            error_uri="https://example.com/error",
        )

        assert error.message == "Access denied"
        assert error.code == "ACCESS_DENIED"
        assert error.state == "state123"
        assert error.error_uri == "https://example.com/error"


@pytest.mark.unit
class TestSpecificErrors:
    """Test cases for specific error types."""

    def test_agent_error(self):
        """Test AgentError creation."""
        error = AgentError("Agent operation failed")

        assert isinstance(error, M8tesError)
        assert error.message == "Agent operation failed"

    def test_deployment_error(self):
        """Test DeploymentError creation."""
        error = DeploymentError("Deployment failed")

        assert isinstance(error, M8tesError)
        assert error.message == "Deployment failed"

    def test_integration_error(self):
        """Test IntegrationError creation."""
        error = IntegrationError("Integration failed")

        assert isinstance(error, M8tesError)
        assert error.message == "Integration failed"

    def test_network_error(self):
        """Test NetworkError creation."""
        error = NetworkError("Network timeout")

        assert isinstance(error, M8tesError)
        assert error.message == "Network timeout"

    def test_validation_error(self):
        """Test ValidationError creation."""
        error = ValidationError("Invalid input")

        assert isinstance(error, M8tesError)
        assert error.message == "Invalid input"

    def test_timeout_error(self):
        """Test TimeoutError creation."""
        error = TimeoutError("Request timed out")

        assert isinstance(error, M8tesError)
        assert error.message == "Request timed out"


@pytest.mark.unit
class TestErrorRaising:
    """Test cases for raising and catching errors."""

    def test_raise_and_catch_m8tes_error(self):
        """Test raising and catching M8tesError."""
        with pytest.raises(M8tesError, match="Test error"):
            raise M8tesError("Test error")

    def test_raise_and_catch_authentication_error(self):
        """Test raising and catching AuthenticationError."""
        with pytest.raises(AuthenticationError, match="Auth failed"):
            raise AuthenticationError("Auth failed")

    def test_catch_specific_error_as_base(self):
        """Test catching specific error as base M8tesError."""
        with pytest.raises(M8tesError):
            raise AgentError("Agent error")

    def test_error_attributes_after_raising(self):
        """Test that error attributes are preserved after raising."""
        try:
            raise RateLimitError("Rate limited", retry_after=30, code="RATE_LIMIT")
        except RateLimitError as e:
            assert e.message == "Rate limited"
            assert e.retry_after == 30
            assert e.code == "RATE_LIMIT"

    def test_oauth_error_attributes_after_raising(self):
        """Test OAuth error attributes after raising."""
        try:
            raise OAuthError(
                "OAuth failed",
                code="INVALID_CLIENT",
                state="test_state",
                error_uri="https://example.com",
            )
        except OAuthError as e:
            assert e.message == "OAuth failed"
            assert e.code == "INVALID_CLIENT"
            assert e.state == "test_state"
            assert e.error_uri == "https://example.com"
