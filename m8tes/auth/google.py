"""Google OAuth authentication service for m8tes SDK."""

from typing import Any

from ..http.client import HTTPClient


class GoogleAuth:
    """Helper class for Google OAuth operations."""

    # mypy: disable-error-code="no-untyped-def,assignment"
    def __init__(self, http_client: HTTPClient, client: object = None) -> None:
        """
        Initialize Google OAuth service.

        Args:
            http_client: HTTP client instance
            client: M8tes client instance for backward compatibility
        """
        self.http = http_client
        self._client = client

    def start_connect(
        self, redirect_uri: str, state: str | None = None, access_type: str = "offline"
    ) -> dict[str, str]:
        """
        Start Google OAuth connection flow.

        Args:
            redirect_uri: URL to redirect after authorization
            state: Optional state parameter for tracking
            access_type: OAuth access type (default: "offline" for refresh tokens)

        Returns:
            Dictionary containing:
            - authorization_url: URL to redirect user to for authorization
            - state: CSRF state token to validate in callback
            - expires_in: State token expiration in seconds

        Raises:
            ValidationError: If redirect_uri is invalid
            NetworkError: If request fails
        """
        data = {"redirect_uri": redirect_uri, "access_type": access_type}

        if state:
            data["state"] = state

        response = self.http.post(
            "/api/v1/integrations/google-ads/auth/init",
            json_data=data,
        )

        return {
            "authorization_url": response["authorization_url"],
            "state": response["state"],
            "expires_in": response.get("expires_in", 600),
        }

    def finish_connect(
        self, code: str, state: str, redirect_uri: str, user_id: int | None = None
    ) -> dict[str, Any]:
        """
        Complete Google OAuth connection with authorization code.

        Args:
            code: Authorization code from OAuth callback
            state: State token from initial authorization
            redirect_uri: Same redirect URI used in authorization request
            user_id: Optional user ID if known

        Returns:
            Dictionary containing:
            - success: Whether integration was created successfully
            - integration_id: Database ID of created integration
            - user_id: User ID associated with integration
            - provider: Integration provider ("google")
            - kind: Integration type ("ads")
            - scopes: List of OAuth scopes granted
            - message: Success message

        Raises:
            OAuthError: If OAuth flow fails
            ValidationError: If parameters are invalid
            NetworkError: If request fails
        """
        data = {"code": code, "state": state, "redirect_uri": redirect_uri}

        if user_id:
            data["user_id"] = user_id  # type: ignore[assignment]

        return self.http.post(
            "/api/v1/integrations/google-ads/auth/callback",
            json_data=data,
        )

    def list_accessible_customers(self, refresh: bool = False) -> dict[str, Any]:
        """Retrieve accessible Google Ads customer IDs for the current user."""
        params = {"refresh": "true" if refresh else "false"}
        return self.http.get(
            "/api/v1/integrations/google-ads/customers",
            params=params,
        )

    def set_customer_id(
        self, customer_id: str, integration_id: int | None = None
    ) -> dict[str, Any]:
        """Set the active Google Ads customer ID for the current user."""
        normalized = "".join(ch for ch in str(customer_id) if ch.isdigit())
        data: dict[str, Any] = {"customer_id": normalized or str(customer_id)}
        if integration_id is not None:
            data["integration_id"] = integration_id
        return self.http.put(
            "/api/v1/integrations/google-ads/customer-id",
            json_data=data,
        )

    def get_status(self) -> dict[str, Any]:
        """
        Check Google Ads integration status for authenticated user.

        Returns:
            Dictionary containing:
            - has_integration: Whether user has active Google Ads integration
            - status: Integration status (active, expired, revoked) if exists
            - integration_id: Database ID of integration if exists
            - scopes: OAuth scopes if integration exists
            - created_at: When integration was created if exists
            - updated_at: Last update timestamp if exists
            - metadata: Additional integration metadata if exists

        Raises:
            AuthenticationError: If not authenticated
            NetworkError: If request fails
        """
        return self.http.get("/api/v1/integrations/google-ads/status")

    def disconnect(self) -> dict[str, Any]:
        """
        Delete/revoke Google Ads integration for authenticated user.

        Removes the integration from the database. The user will need to
        re-authorize to use Google Ads features again.

        Returns:
            Dictionary containing:
            - success: Whether deletion was successful
            - message: Result message
            - deleted_at: Deletion timestamp

        Raises:
            AuthenticationError: If not authenticated
            ValidationError: If no integration found
            NetworkError: If request fails
        """
        return self.http.delete("/api/v1/integrations/google-ads")

    @property
    def client(self) -> object:
        """Backward compatibility property for tests."""
        return self._client
