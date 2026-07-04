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
        Get conversation messages for a run (GET /api/v1/runs/{id}/messages).

        Args:
            run_id: The run's unique identifier

        Returns:
            List of message dicts (role, content, content_blocks, per-message
            token/cost metrics), ordered by sequence.
        """
        raw: Any = self.http.request("GET", f"/api/v1/runs/{run_id}/messages")
        return raw if isinstance(raw, list) else raw.get("messages", [])

    def get_usage(self, run_id: int) -> dict:
        """
        Get aggregated token usage and cost for a run.

        There is no dedicated usage endpoint — this reads the run detail's
        aggregated metrics (GET /api/v1/runs/{id}/detail).

        Returns:
            Dict with message_count (int), total_tokens (int | None), and
            total_cost_usd (decimal string | None).
        """
        detail = self.get_details(run_id)
        return {
            "message_count": detail.get("message_count", 0),
            "total_tokens": detail.get("total_tokens"),
            "total_cost_usd": detail.get("total_cost_usd"),
        }

    def get_tool_executions(self, run_id: int) -> list:
        """
        Get the tool calls a run made, derived from its message content blocks.

        There is no dedicated tool-executions endpoint; this scans the run's
        messages for ``tool_use`` blocks. Success/duration are not available.

        Returns:
            List of {"tool_name": str, "arguments": dict | None} records.
        """
        tools = []
        for msg in self.get_conversation(run_id):
            for block in msg.get("content_blocks") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tools.append(
                        {"tool_name": block.get("name", "unknown"), "arguments": block.get("input")}
                    )
        return tools

    def get_details(self, run_id: int) -> dict:
        """
        Get the run with aggregated metrics (GET /api/v1/runs/{id}/detail).

        Returns:
            FLAT run dict — the run's fields plus message_count, total_tokens,
            and total_cost_usd (decimal string). There are no nested
            conversation/usage/tool_executions keys; use get_conversation /
            get_tool_executions for those.
        """
        response_data = self.http.request("GET", f"/api/v1/runs/{run_id}/detail")
        return response_data
