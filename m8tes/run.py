"""
Run class for managing agent execution runs.
"""

# mypy: disable-error-code="arg-type"
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .services.runs import RunService


class Run:
    """Represents an agent execution run - lifecycle tracking only."""

    def __init__(self, run_service: "RunService", data: dict[str, Any]):
        """
        Initialize a Run instance.

        Args:
            run_service: Run service instance
            data: Run data from API
        """
        self.service = run_service

        # Core identity
        self.id = data.get("id")
        self.claude_session_id = data.get("claude_session_id")
        self.instance_id = data.get("instance_id")
        self.user_id = data.get("user_id")

        # Configuration
        self.run_mode = data.get("run_mode")
        self.description = data.get("description")
        self.task_id = data.get("task_id")
        self.trigger_source = data.get("trigger_source")
        self.trigger_data = data.get("trigger_data")
        self.channel = data.get("channel")

        # Session continuity (claude_session_id is for Claude SDK resume)
        self.claude_session_id = data.get("claude_session_id")
        self.status = data.get("status")
        self.last_sequence = data.get("last_sequence")

        # Sandbox metrics
        self.sandbox_id = data.get("sandbox_id")
        self.sandbox_metadata = data.get("sandbox_metadata")
        self.sandbox_connect_started_at = data.get("sandbox_connect_started_at")
        self.sandbox_connect_completed_at = data.get("sandbox_connect_completed_at")
        self.sandbox_connect_duration_ms = data.get("sandbox_connect_duration_ms")

        # Timestamps
        self.created_at = data.get("created_at")
        self.updated_at = data.get("updated_at")
        self.started_at = data.get("started_at")
        self.last_activity_at = data.get("last_activity_at")

        self._data = data
        self._worker_response = None  # Set by instance.execute_task()
        self._error = None  # Set on error

    def refresh(self) -> None:
        """Reload run data from backend."""
        updated = self.service.get(self.id)
        self.__dict__.update(updated.__dict__)

    @property
    def metrics(self) -> dict[str, Any]:
        """
        Get metrics from worker response.

        Returns:
            Metrics dictionary from worker execution
        """
        if self._worker_response:
            return self._worker_response.get("metrics", {})  # type: ignore[unreachable]
        return {}  # type: ignore[unreachable]

    @property
    def duration_seconds(self) -> float:
        """Get duration from worker response metrics."""
        return self.metrics.get("duration_seconds", 0)  # type: ignore[no-any-return]

    def get_conversation(self) -> list[dict[str, Any]]:
        """
        Get conversation messages for this run.

        Returns:
            List of conversation messages

        Example:
            >>> run = instance.execute_task("What campaigns do I have?")
            >>> messages = run.get_conversation()
            >>> for msg in messages:
            ...     print(f"{msg['role']}: {msg['content']}")
        """
        return self.service.get_conversation(self.id)  # type: ignore[no-any-return]

    def get_usage(self) -> dict[str, Any]:
        """
        Get aggregated token usage and cost for this run.

        Returns:
            Dict with message_count, total_tokens, and total_cost_usd
            (decimal string — coerce with float()).

        Example:
            >>> run = instance.execute_task("Show me top keywords")
            >>> usage = run.get_usage()
            >>> print(f"Cost: ${float(usage['total_cost_usd'] or 0):.4f}")
            >>> print(f"Tokens: {usage['total_tokens']}")
        """
        return self.service.get_usage(self.id)  # type: ignore[no-any-return]

    def get_tool_executions(self) -> list[dict[str, Any]]:
        """
        Get the tool calls this run made (derived from message content blocks).

        Success/duration are not tracked per tool call; each record carries
        the tool name and its input arguments.

        Example:
            >>> run = instance.execute_task("Analyze campaign performance")
            >>> tools = run.get_tool_executions()
            >>> for tool in tools:
            ...     print(f"Tool: {tool['tool_name']}")
        """
        return self.service.get_tool_executions(self.id)  # type: ignore[no-any-return]

    def get_details(self) -> dict[str, Any]:
        """
        Get the run with aggregated metrics — a FLAT dict.

        Returns:
            The run's fields plus message_count, total_tokens, and
            total_cost_usd (decimal string). No nested keys.

        Example:
            >>> run = instance.execute_task("Help me optimize my ads")
            >>> details = run.get_details()
            >>> print(f"Messages: {details['message_count']}")
            >>> print(f"Cost: ${float(details['total_cost_usd'] or 0):.4f}")
        """
        return self.service.get_details(self.id)  # type: ignore[no-any-return]

    def __repr__(self) -> str:
        session_id_short = self.claude_session_id[:8] if self.claude_session_id else "N/A"
        return (
            f"<Run id={self.id} session_id={session_id_short} "
            f"instance_id={self.instance_id} mode={self.run_mode} status={self.status}>"
        )
