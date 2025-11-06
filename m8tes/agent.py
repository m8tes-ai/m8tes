"""
Agent class for managing AI marketing agents.
"""

# mypy: disable-error-code="assignment"
from collections.abc import Generator
from typing import TYPE_CHECKING, Any, Literal

from .exceptions import AgentError
from .streaming import AISDKStreamParser, StreamEvent

if TYPE_CHECKING:
    from .services.agents import AgentService

StreamFormat = Literal["events", "text", "json"]


class Agent:
    """Represents an AI marketing agent."""

    def __init__(self, agent_service: "AgentService", data: dict[str, Any]):
        """
        Initialize an Agent instance.

        Args:
            agent_service: Agent service instance
            data: Agent data from API
        """
        self.agent_service = agent_service
        self.id = data.get("id")
        self.name = data.get("name", "Untitled Agent")
        self.tools = data.get("tools", [])
        self.instructions = data.get("instructions", "")
        self._data = data

    def run(
        self,
        input_data: dict[str, Any] | None = None,
        stream: bool = True,
        format: StreamFormat = "json",
    ) -> Generator[StreamEvent | dict[str, Any] | str, None, None]:
        """
        Run the agent with streaming support.

        Args:
            input_data: Optional input data for the agent
            stream: Whether to stream results (default: True)
            format: Output format:
                - "json": Yield raw JSON dictionaries (default/backward compatible)
                - "events": Yield StreamEvent objects (typed API)
                - "text": Yield only text deltas as strings (simple text streaming)

        Yields:
            StreamEvent objects, strings, or dictionaries depending on format

        Examples:
            # Stream with typed events (recommended)
            for event in agent.run(stream=True, format="events"):
                if isinstance(event, TextDeltaEvent):
                    print(event.delta, end="", flush=True)
                elif isinstance(event, ToolCallStartEvent):
                    print(f"\\nUsing tool: {event.tool_name}")

            # Stream just text (simple)
            for text in agent.run(stream=True, format="text"):
                print(text, end="", flush=True)

            # Get complete response (non-streaming)
            for event in agent.run(stream=False):
                print(event)  # Single complete response
        """
        if not self.id:
            raise AgentError("Cannot run agent without an ID")

        # Prepare request data
        request_data = {"stream": stream}
        if input_data:
            request_data["input_data"] = input_data

        if stream:
            # Stream SSE events from the API
            yield from self._stream_agent_run(request_data, format=format)
        else:
            # Non-streaming API call
            response = self.agent_service.http.request(
                "POST", f"/api/v1/agents/{self.id}/run", json_data=request_data
            )
            if format == "json":
                yield response
            elif format == "text":
                # Extract text from response
                yield response.get("message", str(response))
            else:
                # For events format, wrap in event-like structure
                from .streaming import DoneEvent, StreamEventType, TextDeltaEvent

                text = response.get("message", str(response))
                yield TextDeltaEvent(type=StreamEventType.TEXT_DELTA, raw=response, delta=text)
                yield DoneEvent(type=StreamEventType.DONE, raw={})

    def _stream_agent_run(
        self, request_data: dict[str, Any], format: StreamFormat = "events"
    ) -> Generator[StreamEvent | dict[str, Any] | str, None, None]:
        """
        Stream agent execution events via SSE.

        Args:
            request_data: Request payload
            format: Output format (events, text, json)

        Yields:
            Parsed stream events in the specified format
        """
        import requests

        # Build URL
        url = f"{self.agent_service.http.base_url}/api/v1/agents/{self.id}/run"

        # Prepare headers
        headers = {
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
        }

        if self.agent_service.http.api_key:
            headers["Authorization"] = f"Bearer {self.agent_service.http.api_key}"

        try:
            # Make streaming request
            with requests.post(
                url,
                json=request_data,
                headers=headers,
                stream=True,
                timeout=None,  # No timeout for SSE streams
            ) as response:
                response.raise_for_status()

                # Parse AI SDK stream protocol
                if format == "events":
                    # Yield typed StreamEvent objects
                    for event in AISDKStreamParser.parse_stream(response):
                        yield event

                elif format == "text":
                    # Yield only text deltas as strings
                    from .streaming import TextDeltaEvent

                    for event in AISDKStreamParser.parse_stream(response):
                        if isinstance(event, TextDeltaEvent):
                            yield event.delta

                elif format == "json":
                    # Yield raw JSON dictionaries (legacy compatibility)
                    for event in AISDKStreamParser.parse_stream(response):
                        yield event.raw

        except requests.exceptions.RequestException as e:
            from .exceptions import NetworkError

            raise NetworkError(f"Failed to stream agent execution: {e}") from e

    def deploy(
        self,
        schedule: str | None = None,
        webhook_url: str | None = None,
        name: str | None = None,
    ) -> "Deployment":
        """
        Deploy the agent to the cloud.

        Args:
            schedule: Schedule for running (e.g., "daily", "hourly", "0 9 * * *")
            webhook_url: Optional webhook URL for notifications
            name: Optional deployment name

        Returns:
            Deployment instance
        """
        if not self.id:
            raise AgentError("Cannot deploy agent without an ID")

        # Implementation pending - contact support for deployment features
        raise NotImplementedError(
            "Deployment functionality is not yet available. Contact support for access."
        )

    def update(
        self,
        tools: list | None = None,
        instructions: str | None = None,
        name: str | None = None,
    ) -> "Agent":
        """
        Update agent configuration.

        Args:
            tools: New list of tools
            instructions: New instructions
            name: New name

        Returns:
            Updated Agent instance
        """
        # Implementation pending - contact support for update features
        raise NotImplementedError(
            "Agent update functionality is not yet available. Contact support for access."
        )

    def delete(self) -> bool:
        """
        Delete the agent.

        Returns:
            True if successful
        """
        if not self.id:
            raise AgentError("Cannot delete agent without an ID")

        # Implementation pending - contact support for delete features
        raise NotImplementedError(
            "Agent deletion is not yet available. Contact support for access."
        )

    def __repr__(self) -> str:
        return f"<Agent id={self.id} name='{self.name}'>"


class Deployment:
    """Represents a deployed agent."""

    def __init__(self, agent_service: "AgentService", data: dict[str, Any]):
        """
        Initialize a Deployment instance.

        Args:
            agent_service: Agent service instance
            data: Deployment data from API
        """
        self.agent_service = agent_service
        self.id = data.get("id")
        self.agent_id = data.get("agent_id")
        self.name = data.get("name")
        self.schedule = data.get("schedule")
        self.webhook_url = data.get("webhook_url")
        self.status = data.get("status", "active")
        self._data = data

    def pause(self) -> bool:
        """
        Pause the deployment.

        Returns:
            True if successful
        """
        # Implementation pending - contact support for deployment features
        raise NotImplementedError(
            "Deployment pause functionality is not yet available. Contact support for access."
        )

    def resume(self) -> bool:
        """
        Resume the deployment.

        Returns:
            True if successful
        """
        # Implementation pending - contact support for deployment features
        raise NotImplementedError(
            "Deployment resume functionality is not yet available. Contact support for access."
        )

    def delete(self) -> bool:
        """
        Delete the deployment.

        Returns:
            True if successful
        """
        # Implementation pending - contact support for deployment features
        raise NotImplementedError(
            "Deployment deletion is not yet available. Contact support for access."
        )

    def get_runs(self, limit: int = 10) -> list:
        """
        Get recent runs for this deployment.

        Args:
            limit: Maximum number of runs to return

        Returns:
            List of run dictionaries
        """
        # Implementation pending - contact support for run history features
        raise NotImplementedError(
            "Deployment run history is not yet available. Contact support for access."
        )

    def __repr__(self) -> str:
        return f"<Deployment id={self.id} agent_id={self.agent_id} status={self.status}>"
