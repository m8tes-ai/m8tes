"""Integration services for m8tes SDK."""

from typing import Any

from ..auth.google import GoogleAuth
from ..auth.meta import MetaAuth
from ..http.client import HTTPClient


class IntegrationService:
    """Service for handling integrations."""

    # mypy: disable-error-code="no-untyped-def"
    def __init__(self, http_client: HTTPClient, client: object = None):
        """
        Initialize integration service.

        Args:
            http_client: HTTP client instance
            client: M8tes client instance for backward compatibility
        """
        self.http = http_client
        self._google = GoogleAuth(http_client, client)
        self._meta = MetaAuth(http_client, client)

    @property
    def google(self) -> GoogleAuth:
        """Google integration helpers."""
        return self._google

    @property
    def meta(self) -> MetaAuth:
        """Meta Ads integration helpers."""
        return self._meta

    def list_available(self) -> list[dict[str, Any]]:
        """
        List all available integrations (catalog).

        Returns a list of AppIntegration records from the catalog, showing
        all integration types that can be configured.

        Returns:
            List of AppIntegration catalog entries with fields:
                - id: AppIntegration ID (use this for agent.integration_ids)
                - slug: Integration identifier (e.g., "google-ads")
                - name: Display name (e.g., "Google Ads")
                - provider: Provider name (e.g., "google")
                - kind: Integration kind (e.g., "ads")
                - category: Integration category (e.g., "mcp_server")
                - is_active: Whether the integration is active

        Example:
            >>> integrations = client.integrations.list_available()
            >>> for integration in integrations:
            ...     print(f"{integration['id']}: {integration['name']}")
            1: Google Ads
            2: Meta Ads
        """
        return self.http.request("GET", "/api/v1/integrations/catalog")  # type: ignore[return-value]

    def list_user_integrations(self) -> list[dict[str, Any]]:
        """
        List user's configured integrations (OAuth credentials).

        Returns a list of Integration records that the user has connected,
        showing which integrations are currently configured and active.

        Returns:
            List of user Integration records with fields:
                - id: Integration ID (internal, don't use for agents)
                - provider: Provider name (e.g., "google")
                - kind: Integration kind (e.g., "ads")
                - status: Connection status ("active", "expired", "revoked")
                - account_id: Optional connected account ID
                - created_at: When the integration was connected
                - updated_at: Last update time

        Example:
            >>> integrations = client.integrations.list_user_integrations()
            >>> for integration in integrations:
            ...     if integration['status'] == 'active':
            ...         print(
            ...             f"{integration['provider']} {integration['kind']}: "
            ...             f"{integration['status']}"
            ...         )
            google ads: active
        """
        return self.http.request("GET", "/api/v1/integrations")  # type: ignore[return-value]
