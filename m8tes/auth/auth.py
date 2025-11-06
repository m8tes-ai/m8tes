"""Core authentication service for m8tes SDK."""

from typing import Any

from ..exceptions import ValidationError
from ..http.client import HTTPClient
from ..utils.validation import validate_email, validate_password


class AuthService:
    """Service for handling user authentication operations."""

    # mypy: disable-error-code="no-any-return"
    def __init__(self, http_client: HTTPClient):
        """
        Initialize authentication service.

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
            Dictionary containing user info and success message

        Raises:
            ValidationError: If registration fails
            NetworkError: If request fails
        """
        # Strip whitespace and validate inputs
        email = email.strip()
        password = password.strip()

        # Validate email
        email_error = validate_email(email)
        if email_error:
            raise ValidationError(email_error)

        # Validate password
        password_error = validate_password(password)
        if password_error:
            raise ValidationError(password_error)

        first_name = first_name.strip()
        if not first_name:
            raise ValidationError("First name is required")

        data = {
            "email": email,
            "password": password,
            "first_name": first_name,
        }

        return self.http.post("/api/v1/auth/register", json_data=data, auth_required=False)

    def login(self, email: str, password: str) -> str:
        """
        Login user and get API key.

        Args:
            email: User's email address
            password: User's password

        Returns:
            API key string that can be used for authentication

        Raises:
            ValidationError: If inputs are invalid
            AuthenticationError: If login fails
            NetworkError: If request fails
        """
        # Strip whitespace and validate inputs
        email = email.strip()
        password = password.strip()

        # Validate email
        email_error = validate_email(email)
        if email_error:
            raise ValidationError(email_error)

        # For login, just check that password is not empty
        if not password:
            raise ValidationError("Password is required")

        data = {
            "email": email,
            "password": password,
        }

        response = self.http.post("/api/v1/auth/login", json_data=data, auth_required=False)

        # Update the HTTP client's API key with the new token
        if "api_key" in response:
            self.http.set_api_key(response["api_key"])

        return response.get("api_key", "")  # type: ignore[no-any-return]

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
        return response.get("user", {})  # type: ignore[no-any-return]

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
