"""Instance operations service for m8tes SDK."""

from typing import TYPE_CHECKING, Any, cast

from ..http.client import HTTPClient

if TYPE_CHECKING:
    from ..instance import AgentInstance


class InstanceService:
    """Service for handling agent instance operations."""

    # mypy: disable-error-code="assignment"
    def __init__(self, http_client: HTTPClient):
        """
        Initialize instance service.

        Args:
            http_client: HTTP client instance
        """
        self.http = http_client

    def create(
        self,
        name: str,
        tools: list[str],
        instructions: str,
        agent_type: str = "marketing",
        user_instructions: str | None = None,
        *,
        role: str | None = None,
        goals: str | None = None,
        integration_ids: list[int] | None = None,
    ) -> "AgentInstance":
        """
        Create a new agent instance.

        Args:
            name: Instance name
            tools: List of tool IDs to enable
            instructions: Agent behavior instructions
            agent_type: Type of agent (default: marketing)
            user_instructions: User-specific behavioral guidelines
            role: Optional teammate persona or specialization
            goals: Optional goals and success metrics (plain text)
            integration_ids: Optional list of AppIntegration IDs (catalog references)
                to enable for this agent. Use client.integrations.list_available()
                to see available integrations.

        Returns:
            AgentInstance instance

        Note:
            The execution mode (OpenAI SDK, Claude SDK, or Cloudflare) is automatically
            determined by the backend based on the AGENT_SDK environment variable.
        """
        # Prepare request data
        request_data: dict[str, Any] = {
            "name": name,
            "tools": tools,
            "instructions": instructions,
            "agent_type": agent_type,
        }

        if user_instructions:
            request_data["user_instructions"] = user_instructions
        if role:
            request_data["role"] = role
        if goals:
            request_data["goals"] = goals
        if integration_ids is not None:
            request_data["integration_ids"] = integration_ids

        # Make API call
        response_data = self.http.request(
            "POST", "/api/v1/agents/instances", json_data=request_data
        )

        # Import here to avoid circular imports
        from ..instance import AgentInstance

        return AgentInstance(instance_service=self, data=response_data)

    def get(self, instance_id: int) -> "AgentInstance":
        """
        Get an existing instance by ID.

        Args:
            instance_id: The instance's unique identifier

        Returns:
            AgentInstance instance
        """
        # Make API call
        response_data = self.http.request("GET", f"/api/v1/agents/instances/{instance_id}")

        # Import here to avoid circular imports
        from ..instance import AgentInstance

        return AgentInstance(instance_service=self, data=response_data)

    def list(
        self, include_disabled: bool = False, include_archived: bool = False
    ) -> list["AgentInstance"]:
        """
        List all instances.

        Args:
            include_disabled: Include disabled instances (default: False)
            include_archived: Include archived instances (default: False)

        Returns:
            List of AgentInstance instances (enabled first, then disabled, then archived)
        """
        # Make API call with query parameters
        params = {
            "include_disabled": "true" if include_disabled else "false",
            "include_archived": "true" if include_archived else "false",
        }
        response_data = self.http.request("GET", "/api/v1/agents/instances", params=params)

        # Import here to avoid circular imports
        from ..instance import AgentInstance

        # Create AgentInstance instances from response
        # The API returns a list directly, not a dict with "instances" key
        # Cast to list since HTTPClient.request() returns dict[str, Any] but this endpoint
        # actually returns a list
        instances_list = cast(list[dict[str, Any]], response_data)
        instances = []
        for instance_data in instances_list:
            instances.append(AgentInstance(instance_service=self, data=instance_data))

        return instances

    def update(
        self,
        instance_id: int,
        name: str | None = None,
        instructions: str | None = None,
    ) -> "AgentInstance":
        """
        Update an existing instance.

        Args:
            instance_id: Instance ID to update
            name: New name (optional)
            instructions: New instructions (optional)

        Returns:
            Updated AgentInstance instance
        """
        # Prepare update data
        update_data = {}
        if name is not None:
            update_data["name"] = name
        if instructions is not None:
            update_data["instructions"] = instructions

        if not update_data:
            raise ValueError("At least one field must be provided for update")

        # Make API call
        response_data = self.http.request(
            "PATCH", f"/api/v1/agents/instances/{instance_id}", json_data=update_data
        )

        # Import here to avoid circular imports
        from ..instance import AgentInstance

        return AgentInstance(instance_service=self, data=response_data)

    def enable(self, instance_id: int) -> "AgentInstance":
        """
        Enable a disabled instance.

        Args:
            instance_id: Instance ID to enable

        Returns:
            Updated AgentInstance instance

        Raises:
            ValidationError: If instance not found
            AuthenticationError: If not authorized
            NetworkError: If request fails
        """
        response_data = self.http.request("POST", f"/api/v1/agents/instances/{instance_id}/enable")

        # Import here to avoid circular imports
        from ..instance import AgentInstance

        return AgentInstance(instance_service=self, data=response_data)

    def disable(self, instance_id: int) -> "AgentInstance":
        """
        Disable an instance (soft disable, still visible with flag).

        This sets the instance status to DISABLED and is_active to False.
        The instance remains visible when listing with include_disabled=True.

        Args:
            instance_id: Instance ID to disable

        Returns:
            Updated AgentInstance instance

        Raises:
            ValidationError: If instance not found
            AuthenticationError: If not authorized
            NetworkError: If request fails
        """
        response_data = self.http.request("POST", f"/api/v1/agents/instances/{instance_id}/disable")

        # Import here to avoid circular imports
        from ..instance import AgentInstance

        return AgentInstance(instance_service=self, data=response_data)

    def archive(self, instance_id: int) -> bool:
        """
        Archive an instance (soft delete, hidden from default listings).

        This performs a soft delete by setting the instance status to ARCHIVED
        and is_active to False. The instance and its run history are preserved
        in the database but will not appear in default listings.

        Args:
            instance_id: Instance ID to archive

        Returns:
            True if successful

        Raises:
            ValidationError: If instance not found
            AuthenticationError: If not authorized
            NetworkError: If request fails
        """
        # Make API call - backend returns 204 NO_CONTENT on success
        response = self.http.request("DELETE", f"/api/v1/agents/instances/{instance_id}")
        # 204 responses return {"success": True} from HTTP client
        return bool(response.get("success", False))

    def auto_detect(self) -> tuple["AgentInstance", dict[str, Any]]:
        """
        Auto-detect the best agent instance for the current user.

        Selection logic:
        1. Returns agent with most recent run (LAST_USED) if runs exist
        2. Falls back to most recently created agent (LAST_CREATED) if no runs
        3. Only considers enabled agents (ignores disabled/archived)

        Returns:
            Tuple of (AgentInstance, metadata_dict) where metadata contains:
            - reason: "last_used" or "last_created"
            - last_used_at: ISO timestamp or None

        Raises:
            ValidationError: If user has no enabled agents
            AuthenticationError: If not authorized
            NetworkError: If request fails

        Example:
            >>> instance, metadata = client.instances.auto_detect()
            >>> print(f"Using {instance.name} (reason: {metadata['reason']})")
        """
        response_data = self.http.request("GET", "/api/v1/agents/instances/auto-detect")

        # Import here to avoid circular imports
        from ..instance import AgentInstance

        # Extract agent data and metadata
        agent_data = response_data["agent"]
        metadata = {
            "reason": response_data["reason"],
            "last_used_at": response_data.get("last_used_at"),
        }

        # Create AgentInstance from agent data
        instance = AgentInstance(instance_service=self, data=agent_data)

        return instance, metadata
