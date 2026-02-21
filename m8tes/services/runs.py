"""Run operations service for m8tes SDK."""

from typing import TYPE_CHECKING, Any

from ..http.client import HTTPClient

if TYPE_CHECKING:
    from ..run import Run


class RunService:
    """Service for handling run operations."""

    # mypy: disable-error-code="no-untyped-def"
    def __init__(self, http_client: HTTPClient):
        """
        Initialize run service.

        Args:
            http_client: HTTP client instance
        """
        self.http = http_client

    def create(
        self,
        instance_id: int,
        run_mode: str,
        description: str | None = None,
    ) -> "Run":
        """
        Create a new run.

        Args:
            instance_id: Instance ID to create run for
            run_mode: Mode of run ("task" or "chat")
            description: Optional run description

        Returns:
            Run instance
        """
        # Prepare request data
        request_data = {
            "instance_id": instance_id,
            "run_mode": run_mode,
        }

        if description:
            request_data["description"] = description

        # Make API call
        response_data = self.http.request("POST", "/api/v1/runs", json_data=request_data)

        # Import here to avoid circular imports
        from ..run import Run

        return Run(run_service=self, data=response_data)

    def get(self, run_id: int) -> "Run":
        """
        Get an existing run by ID.

        Args:
            run_id: The run's unique identifier

        Returns:
            Run instance
        """
        # Make API call
        response_data = self.http.request("GET", f"/api/v1/runs/{run_id}")

        # Import here to avoid circular imports
        from ..run import Run

        return Run(run_service=self, data=response_data)

    def list_for_instance(self, instance_id: int, limit: int = 50) -> list["Run"]:
        """
        List runs for an instance.

        Args:
            instance_id: Instance ID
            limit: Maximum number of runs to return (default: 50)

        Returns:
            List of Run instances
        """
        params = {"instance_id": instance_id, "limit": limit}
        raw: Any = self.http.request("GET", "/api/v1/runs", params=params)

        # Import here to avoid circular imports
        from ..run import Run

        # API returns a plain list; guard against wrapped dicts for safety
        run_list: list[Any] = raw if isinstance(raw, list) else raw.get("runs", [])
        return [Run(run_service=self, data=d) for d in run_list]

    def list_user_runs(self, limit: int = 50) -> list["Run"]:
        """
        List all runs for the current user.

        Args:
            limit: Maximum number of runs to return (default: 50)

        Returns:
            List of Run instances
        """
        params = {"limit": limit}
        raw: Any = self.http.request("GET", "/api/v1/runs", params=params)

        # Import here to avoid circular imports
        from ..run import Run

        # API returns a plain list; guard against wrapped dicts for safety
        run_list: list[Any] = raw if isinstance(raw, list) else raw.get("runs", [])
        return [Run(run_service=self, data=d) for d in run_list]

    def get_conversation(self, run_id: int) -> list:
        """
        Get conversation messages for a run.

        Args:
            run_id: The run's unique identifier

        Returns:
            List of conversation messages
        """
        response_data = self.http.request("GET", f"/api/v1/runs/{run_id}/conversation")
        return response_data.get("messages", [])  # type: ignore[no-any-return]

    def get_usage(self, run_id: int) -> dict:
        """
        Get token usage and costs for a run.

        Args:
            run_id: The run's unique identifier

        Returns:
            Dictionary with usage statistics and costs
        """
        response_data = self.http.request("GET", f"/api/v1/runs/{run_id}/usage")
        return response_data

    def get_tool_executions(self, run_id: int) -> list:
        """
        Get tool execution history for a run.

        Args:
            run_id: The run's unique identifier

        Returns:
            List of tool execution records
        """
        response_data = self.http.request("GET", f"/api/v1/runs/{run_id}/tools")
        return response_data.get("executions", [])  # type: ignore[no-any-return]

    def get_details(self, run_id: int) -> dict:
        """
        Get comprehensive run details including conversation, usage, and tool executions.

        Args:
            run_id: The run's unique identifier

        Returns:
            Dictionary with all run data
        """
        response_data = self.http.request("GET", f"/api/v1/runs/{run_id}/details")
        return response_data
