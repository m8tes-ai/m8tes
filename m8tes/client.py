"""
M8tes client for interacting with the m8tes.ai platform.
"""

# mypy: disable-error-code="arg-type,attr-defined,no-untyped-def,no-any-return"
import os
from typing import Any

from .agent import Agent
from .auth.auth import AuthService
from .auth.credentials import CredentialManager
from .http.client import HTTPClient
from .services.agents import AgentService
from .services.instances import InstanceService
from .services.integrations import IntegrationService
from .services.runs import RunService
from .services.tasks import TaskService
from .services.users import UserService


class M8tes:
    """Main client for interacting with m8tes.ai."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: int = 30,
        profile: str = "default",
    ):
        """
        Initialize M8tes client.

        Args:
            api_key: API key for authentication. If not provided, checks keychain,
                then M8TES_API_KEY env var
            base_url: Base URL for API. If not provided, uses default or
                M8TES_BASE_URL env var
            timeout: Request timeout in seconds
            profile: Profile name for keychain storage (default: "default")
        """
        # Try multiple sources for API key: explicit param -> keychain -> env var
        if api_key is None:
            # Try keychain first
            credentials = CredentialManager(profile=profile)
            api_key = credentials.get_api_key()

            # Check if access token is expired and try refresh
            if api_key and credentials.is_access_token_expired():
                refresh_token = credentials.get_refresh_token()
                if refresh_token:
                    # Try to refresh the token
                    try:
                        refreshed_data = self._refresh_token_at_init(
                            base_url or os.getenv("M8TES_BASE_URL", "https://www.m8tes.ai"),
                            refresh_token,
                        )
                        if refreshed_data:
                            api_key = refreshed_data.get("api_key")
                            if api_key:
                                credentials.save_api_key(api_key)
                    except Exception:
                        # If refresh fails, clear expired tokens and continue
                        credentials.delete_api_key()
                        api_key = None

            # Fallback to environment variable
            if api_key is None:
                api_key = os.getenv("M8TES_API_KEY")

        # Note: api_key can be None for unauthenticated operations (login, register)
        # Protected endpoints will check authentication separately

        base_url = base_url or os.getenv("M8TES_BASE_URL", "https://www.m8tes.ai")

        # Initialize HTTP client
        self.http = HTTPClient(base_url=base_url, api_key=api_key, timeout=timeout, profile=profile)

        # Initialize services
        self.auth = AuthService(self.http)
        self.agents = AgentService(self.http)
        self.instances = InstanceService(self.http)
        self.runs = RunService(self.http)
        self.tasks = TaskService(self.http)
        self.users = UserService(self.http)
        self.integrations = IntegrationService(self.http, client=self)

        # Store reference to client in http for circular access
        self.http.client = self

    @property
    def api_key(self) -> str | None:
        """Get the API key."""
        return self.http.api_key

    @property
    def base_url(self) -> str:
        """Get the base URL."""
        return self.http.base_url

    @property
    def timeout(self) -> int:
        """Get the timeout."""
        return self.http.timeout

    @property
    def _session(self) -> object | None:
        """Get the HTTP session."""
        return self.http._session

    def _request(self, method: str, url: str, **kwargs) -> dict[str, Any]:
        """Make an HTTP request using the underlying HTTP client."""
        return self.http.request(method, url, **kwargs)

    # Agent operations (delegate to agent service)
    def create_agent(
        self,
        tools: list[str],
        instructions: str,
        name: str | None = None,
    ) -> "Agent":
        """
        Create a new agent.

        Args:
            tools: List of tool IDs to enable for the agent
                (e.g., ["google_ads_search", "google_ads_negatives"])
            instructions: Natural language instructions for the agent
            name: Optional name for the agent

        Returns:
            Agent instance
        """
        return self.agents.create_agent(tools, instructions, name)

    def get_agent(self, agent_id: str) -> "Agent":
        """
        Get an existing agent by ID.

        Args:
            agent_id: The agent's unique identifier

        Returns:
            Agent instance
        """
        return self.agents.get_agent(agent_id)

    def list_agents(self, limit: int = 10) -> list["Agent"]:
        """
        List all agents.

        Args:
            limit: Maximum number of agents to return

        Returns:
            List of Agent instances
        """
        return self.agents.list_agents(limit)

    # User operations (delegate to user service)
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
        return self.users.register_user(email, password, first_name)

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
        return self.users.login(email, password)

    def get_current_user(self) -> dict[str, Any]:
        """
        Get current authenticated user information.

        Returns:
            Dictionary containing user information

        Raises:
            AuthenticationError: If not authenticated
            NetworkError: If request fails
        """
        return self.users.get_current_user()

    def logout(self) -> bool:
        """
        Logout by invalidating current token.

        Returns:
            True if logout successful

        Raises:
            NetworkError: If request fails
        """
        return self.users.logout()

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
        return self.users.refresh_token(refresh_token)

    @property
    def google(self):
        """Google integration helpers."""
        return self.integrations.google

    @property
    def meta(self):
        """Meta Ads integration helpers."""
        return self.integrations.meta

    def _refresh_token_at_init(self, base_url: str, refresh_token: str) -> dict[str, Any] | None:
        """
        Refresh token during initialization (before HTTP client is ready).

        Args:
            base_url: API base URL
            refresh_token: Refresh token to use

        Returns:
            Dictionary with new token info if successful, None otherwise
        """
        try:
            import requests

            response = requests.post(
                f"{base_url}/api/v1/auth/refresh",
                json={"refresh_token": refresh_token},
                timeout=30,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                return response.json()

        except Exception:
            pass

        return None

    def close(self) -> None:
        """Close the HTTP session."""
        self.http.close()
