"""Unit tests for UserService class."""

from unittest.mock import Mock

import pytest

from m8tes.exceptions import AuthenticationError, NetworkError
from m8tes.http.client import HTTPClient
from m8tes.services.users import UserService


@pytest.mark.unit
class TestUserService:
    """Test cases for UserService methods."""

    @pytest.fixture
    def mock_http_client(self):
        """Create a mock HTTP client."""
        return Mock(spec=HTTPClient)

    @pytest.fixture
    def user_service(self, mock_http_client):
        """Create UserService instance with mock HTTP client."""
        return UserService(mock_http_client)

    def test_refresh_token_success(self, user_service, mock_http_client):
        """Test successful token refresh."""
        # Mock successful response
        mock_response = {
            "success": True,
            "api_key": "new_access_token_123",
            "expires_at": "2024-01-01T01:00:00Z",
            "message": "Token refreshed successfully",
        }
        mock_http_client.post.return_value = mock_response

        # Call refresh_token
        result = user_service.refresh_token("refresh_token_123")

        # Verify response
        assert result == mock_response
        assert result["api_key"] == "new_access_token_123"
        assert result["success"] is True

        # Verify HTTP client was called correctly
        mock_http_client.post.assert_called_once_with(
            "/api/v1/auth/refresh",
            json_data={"refresh_token": "refresh_token_123"},
            auth_required=False,
        )

    def test_refresh_token_updates_http_client_api_key(self, user_service, mock_http_client):
        """Test that refresh_token updates HTTP client's API key."""
        # Mock successful response
        mock_response = {
            "success": True,
            "api_key": "new_access_token_123",
            "expires_at": "2024-01-01T01:00:00Z",
        }
        mock_http_client.post.return_value = mock_response

        # Call refresh_token
        user_service.refresh_token("refresh_token_123")

        # Verify HTTP client's API key was updated
        mock_http_client.set_api_key.assert_called_once_with("new_access_token_123")

    def test_refresh_token_no_api_key_in_response(self, user_service, mock_http_client):
        """Test refresh_token handles response without api_key."""
        # Mock response without api_key
        mock_response = {"success": False, "message": "Refresh failed"}
        mock_http_client.post.return_value = mock_response

        # Call refresh_token
        result = user_service.refresh_token("refresh_token_123")

        # Verify response returned as-is
        assert result == mock_response

        # Verify HTTP client's API key was NOT updated
        mock_http_client.set_api_key.assert_not_called()

    def test_refresh_token_authentication_error(self, user_service, mock_http_client):
        """Test refresh_token handles authentication errors."""
        # Mock HTTP client raising AuthenticationError
        mock_http_client.post.side_effect = AuthenticationError("Invalid refresh token")

        # Verify exception is propagated
        with pytest.raises(AuthenticationError, match="Invalid refresh token"):
            user_service.refresh_token("invalid_refresh_token")

    def test_refresh_token_network_error(self, user_service, mock_http_client):
        """Test refresh_token handles network errors."""
        # Mock HTTP client raising NetworkError
        mock_http_client.post.side_effect = NetworkError("Connection failed")

        # Verify exception is propagated
        with pytest.raises(NetworkError, match="Connection failed"):
            user_service.refresh_token("refresh_token_123")

    def test_login_success(self, user_service, mock_http_client):
        """Test successful login."""
        # Mock successful login response
        mock_response = {
            "success": True,
            "api_key": "access_token_123",
            "refresh_token": "refresh_token_123",
            "access_expires_at": "2024-01-01T01:00:00Z",
            "refresh_expires_at": "2024-01-31T00:00:00Z",
        }
        mock_http_client.post.return_value = mock_response

        # Call login
        result = user_service.login("test@example.com", "password123")

        # Verify response
        assert result == mock_response
        assert result["api_key"] == "access_token_123"

        # Verify HTTP client was called correctly
        mock_http_client.post.assert_called_once_with(
            "/api/v1/auth/login",
            json_data={"email": "test@example.com", "password": "password123"},
            auth_required=False,
        )

        # Verify HTTP client's API key was updated
        mock_http_client.set_api_key.assert_called_once_with("access_token_123")

    def test_register_user_success(self, user_service, mock_http_client):
        """Test successful user registration."""
        # Mock successful registration response
        mock_response = {
            "success": True,
            "user": {
                "id": 123,
                "email": "test@example.com",
                "first_name": "Test",
                "last_name": "User",
            },
            "api_key": "new_api_key_123",
        }
        mock_http_client.post.return_value = mock_response

        # Call register_user
        result = user_service.register_user(
            email="test@example.com", password="password123", first_name="Test"
        )

        # Verify response
        assert result == mock_response
        assert result["user"]["email"] == "test@example.com"

        # Verify HTTP client was called correctly
        expected_data = {
            "email": "test@example.com",
            "password": "password123",
            "first_name": "Test",
        }
        mock_http_client.post.assert_called_once_with(
            "/api/v1/auth/register", json_data=expected_data, auth_required=False
        )

        # Verify HTTP client's API key was updated
        mock_http_client.set_api_key.assert_called_once_with("new_api_key_123")

    def test_register_user_minimal_params(self, user_service, mock_http_client):
        """Test user registration with minimal parameters."""
        # Mock successful registration response
        mock_response = {
            "success": True,
            "user": {"id": 123, "email": "test@example.com"},
            "api_key": "new_api_key_123",
        }
        mock_http_client.post.return_value = mock_response

        # Call register_user with only required params
        result = user_service.register_user(
            email="test@example.com", password="password123", first_name="Test"
        )

        # Verify response
        assert result == mock_response

        # Verify HTTP client was called with only required fields
        expected_data = {
            "email": "test@example.com",
            "password": "password123",
            "first_name": "Test",
        }
        mock_http_client.post.assert_called_once_with(
            "/api/v1/auth/register", json_data=expected_data, auth_required=False
        )

    def test_get_current_user_success(self, user_service, mock_http_client):
        """Test successful get current user."""
        # Mock successful response
        mock_response = {
            "user": {
                "id": 123,
                "email": "test@example.com",
                "first_name": "Test",
                "last_name": "User",
                "is_verified": True,
            }
        }
        mock_http_client.get.return_value = mock_response

        # Call get_current_user
        result = user_service.get_current_user()

        # Verify response - should return just the user object
        expected_user = mock_response["user"]
        assert result == expected_user
        assert result["email"] == "test@example.com"

        # Verify HTTP client was called correctly
        mock_http_client.get.assert_called_once_with("/api/v1/auth/me")

    def test_get_current_user_no_user_field(self, user_service, mock_http_client):
        """Test get current user when response has no user field (FastAPI format)."""
        # Mock FastAPI-style response (user data directly, no wrapper)
        mock_response = {
            "id": 123,
            "email": "test@example.com",
            "first_name": "Test",
            "is_verified": True,
        }
        mock_http_client.get.return_value = mock_response

        # Call get_current_user
        result = user_service.get_current_user()

        # Should return the whole response (FastAPI format)
        assert result == mock_response
        assert result["email"] == "test@example.com"

    def test_logout_success(self, user_service, mock_http_client):
        """Test successful logout."""
        # Mock successful logout response
        mock_response = {"success": True}
        mock_http_client.post.return_value = mock_response

        # Call logout
        result = user_service.logout()

        # Should return True
        assert result is True

        # Verify HTTP client was called correctly
        mock_http_client.post.assert_called_once_with("/api/v1/auth/logout")

    def test_logout_failed_response(self, user_service, mock_http_client):
        """Test logout with failed response."""
        # Mock failed logout response
        mock_response = {"success": False}
        mock_http_client.post.return_value = mock_response

        # Call logout
        result = user_service.logout()

        # Should return False
        assert result is False

    def test_logout_exception_handling(self, user_service, mock_http_client):
        """Test logout handles exceptions gracefully."""
        # Mock HTTP client raising exception
        mock_http_client.post.side_effect = Exception("Network error")

        # Call logout
        result = user_service.logout()

        # Should return False, not raise exception
        assert result is False
