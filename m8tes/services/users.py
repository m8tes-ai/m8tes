"""User management service for m8tes SDK."""

from typing import Any

from ..http.client import HTTPClient


class UserService:
    """Service for handling user operations."""

    # mypy: disable-error-code="no-any-return"
    def __init__(self, http_client: HTTPClient):
        """
        Initialize user service.

        Args:
            http_client: HTTP client instance
        """
        self.http = http_client

    def register_user(self, email: str, password: str, first_name: str) -> dict[str, Any]:
        """
        Register a new user account.

        Args:
            email: User's email address
            password: Password (must be at least 8 characters)
            first_name: User's first name

        Returns:
            Dictionary containing user info, api_key, and success message

        Raises:
            ValidationError: If registration fails
            NetworkError: If request fails
        """
        data = {
            "email": email,
            "password": password,
            "first_name": first_name.strip(),
        }

        response = self.http.post("/api/v1/auth/register", json_data=data, auth_required=False)

        # Update the HTTP client's API key with the new token if provided
        if "api_key" in response:
            self.http.set_api_key(response["api_key"])

        return response

    def login(self, email: str, password: str) -> dict[str, Any]:
        """
        Login user and get API key.

        Args:
            email: User's email address
            password: User's password

        Returns:
            Dictionary containing login response with API key and token metadata

        Raises:
            AuthenticationError: If login fails
            NetworkError: If request fails
        """
        data = {
            "email": email,
            "password": password,
        }

        response = self.http.post("/api/v1/auth/login", json_data=data, auth_required=False)

        # Update the HTTP client's API key with the new token
        if "api_key" in response:
            self.http.set_api_key(response["api_key"])

        return response

    def get_current_user(self) -> dict[str, Any]:
        """
        Get current authenticated user information.

        Returns:
            Dictionary containing user information

        Raises:
            AuthenticationError: If not authenticated
            NetworkError: If request fails
        """
        response = self.http.get("/api/v1/auth/me")
        # Support both Flask format {"user": {...}} and FastAPI format {...}
        if "user" in response:
            return response["user"]  # type: ignore[no-any-return]
        return response  # type: ignore[no-any-return]

    def logout(self) -> bool:
        """
        Logout by invalidating current token.

        Returns:
            True if logout successful

        Raises:
            NetworkError: If request fails
        """
        try:
            response = self.http.post("/api/v1/auth/logout")
            return response.get("success", False)  # type: ignore[no-any-return]
        except Exception:
            return False

    def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        """
        Refresh an expired access token using a valid refresh token.

        Args:
            refresh_token: Refresh token string

        Returns:
            Dictionary containing new token info

        Raises:
            AuthenticationError: If refresh fails
            NetworkError: If request fails
        """
        data = {"refresh_token": refresh_token}

        response = self.http.post("/api/v1/auth/refresh", json_data=data, auth_required=False)

        # Update the HTTP client's API key with the new token
        if "api_key" in response:
            self.http.set_api_key(response["api_key"])

        return response
