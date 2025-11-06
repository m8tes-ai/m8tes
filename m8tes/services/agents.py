"""Agent operations service for m8tes SDK."""

from typing import TYPE_CHECKING

from ..http.client import HTTPClient

if TYPE_CHECKING:
    from ..agent import Agent


class AgentService:
    """Service for handling agent operations."""

    def __init__(self, http_client: HTTPClient):
        """
        Initialize agent service.

        Args:
            http_client: HTTP client instance
        """
        self.http = http_client

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
        # Prepare request data
        request_data = {
            "tools": tools,
            "instructions": instructions,
        }

        if name:
            request_data["name"] = name

        # Make API call
        response_data = self.http.request("POST", "/api/v1/agents", json_data=request_data)

        # Import here to avoid circular imports
        from ..agent import Agent

        return Agent(agent_service=self, data=response_data)

    def get_agent(self, agent_id: str) -> "Agent":
        """
        Get an existing agent by ID.

        Args:
            agent_id: The agent's unique identifier

        Returns:
            Agent instance
        """
        # Make API call
        response_data = self.http.request("GET", f"/api/v1/agents/{agent_id}")

        # Import here to avoid circular imports
        from ..agent import Agent

        return Agent(agent_service=self, data=response_data)

    def list_agents(self, limit: int = 10) -> list["Agent"]:
        """
        List all agents.

        Args:
            limit: Maximum number of agents to return

        Returns:
            List of Agent instances
        """
        # Make API call with query parameters
        params = {"limit": limit}
        response_data = self.http.request("GET", "/api/v1/agents", params=params)

        # Import here to avoid circular imports
        from ..agent import Agent

        # Create Agent instances from response
        agents = []
        for agent_data in response_data.get("agents", []):
            agents.append(Agent(agent_service=self, data=agent_data))

        return agents
