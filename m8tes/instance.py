"""
AgentInstance class for managing persistent agent instances.
"""

# mypy: disable-error-code="misc,attr-defined,import-not-found,no-any-return,assignment,arg-type"
from collections.abc import Generator
from contextlib import suppress
from typing import TYPE_CHECKING, Any, Literal

import requests

from .streaming import AISDKStreamParser, StreamEvent

if TYPE_CHECKING:
    from .chat import ChatSession
    from .services.instances import InstanceService

StreamFormat = Literal["events", "text", "json"]


class AgentInstance:
    """Represents a persistent agent instance."""

    def __init__(self, instance_service: "InstanceService", data: dict[str, Any]):
        """
        Initialize an AgentInstance.

        Args:
            instance_service: Instance service instance
            data: Instance data from API
        """
        self.service = instance_service
        self.id = data.get("id")
        self.cloudflare_instance_id = data.get("cloudflare_instance_id")
        self.user_id = data.get("user_id")
        self.name = data.get("name")
        self.agent_type = data.get("agent_type")
        self.role = data.get("role")
        self.instructions = data.get("instructions")
        self.tools = data.get("tools", [])
        self.tool_configs = data.get("tool_configs", {})
        self.goals = data.get("goals")
        self.status = data.get("status")
        self.is_active = data.get("is_active")
        self.run_count = data.get("run_count", 0)
        self.created_at = data.get("created_at")
        self.updated_at = data.get("updated_at")
        self._data = data

    def execute_task(
        self, message: str, stream: bool = True, format: StreamFormat = "events"
    ) -> Generator[StreamEvent, None, None]:
        """
        Execute one-off task with streaming support (clears history first).

        Args:
            message: Task description
            stream: Enable streaming (default: True)
            format: Output format - "events" (StreamEvent objects),
                "text" (strings), or "json" (dicts)

        Yields:
            StreamEvent objects (or strings/dicts based on format)

        Examples:
            # Stream with typed events
            for event in instance.execute_task("Show my campaigns", stream=True):
                if isinstance(event, TextDeltaEvent):
                    print(event.delta, end="")

            # Stream just text
            for text in instance.execute_task("Show my campaigns", stream=True, format="text"):
                print(text, end="")
        """
        # Execute via Claude SDK endpoint
        yield from self._execute_via_sdk(message, format=format, stream=stream)

    def _execute_via_sdk(
        self,
        message: str,
        format: StreamFormat = "events",
        stream: bool = True,
        mode: Literal["task", "chat"] = "task",
        session_id: str | None = None,
        run_id: int | None = None,
    ) -> Generator[StreamEvent, None, None]:
        """
        Execute task via Claude SDK execution endpoint.

        Args:
            message: Task description
            format: Output format (events, text, json)
            stream: Enable streaming (default: True)
            mode: Execution mode - "task" for one-off, "chat" for conversation
            session_id: Optional session ID to resume (chat mode only)
            run_id: Optional run ID to reuse (prevents duplicate run creation)

        Yields:
            StreamEvent objects (or strings/dicts based on format)
        """

        from .exceptions import AgentError, AuthenticationError
        from .streaming import DoneEvent, StreamEventType, TextDeltaEvent

        backend_url = self.service.http.base_url
        execute_url = f"{backend_url}/api/v1/agents/instances/{self.id}/execute"

        # Build request body
        body = {"task": message, "mode": mode, "stream": stream}

        # Only include session_id if explicitly provided (for resuming conversations)
        if mode == "chat" and session_id:
            body["session_id"] = session_id

        # Include run_id if provided (backend will reuse instead of creating new)
        if run_id:
            body["run_id"] = run_id

        try:
            response = requests.post(
                execute_url,
                json=body,
                headers={
                    "Authorization": f"Bearer {self.service.http.api_key}",
                    "Content-Type": "application/json",
                },
                stream=stream,  # Enable streaming mode for requests
                timeout=None if stream else 120,  # No timeout for streams
            )
            response.raise_for_status()

            # Check if response is SSE (streaming)
            content_type = response.headers.get("content-type", "")
            if "text/event-stream" in content_type:
                # Parse SSE stream
                yield from self._parse_sse_stream(response, format)
            else:
                # Non-streaming response (JSON)
                result = response.json()

                # Extract response text
                text = result.get("response", str(result))

                # Yield in appropriate format
                if format == "text":
                    yield text
                elif format == "json":
                    yield result
                else:  # events
                    yield TextDeltaEvent(type=StreamEventType.TEXT_DELTA, raw=result, delta=text)
                    yield DoneEvent(type=StreamEventType.DONE, raw={})

        except requests.HTTPError as e:
            if e.response.status_code == 401:
                raise AuthenticationError(
                    "Authentication failed during agent execution.\n"
                    "Your token may have expired. Please login again: m8tes auth login"
                ) from e
            else:
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", error_data.get("message", str(e)))
                except Exception:
                    error_msg = str(e)
                raise AgentError(f"Agent execution failed: {error_msg}") from e
        except requests.RequestException as e:
            raise AgentError(f"Failed to communicate with backend: {e}") from e

    def _parse_sse_stream(
        self, response: object, format: StreamFormat
    ) -> Generator[StreamEvent, None, None]:
        """
        Parse Server-Sent Events (SSE) stream from response.

        Args:
            response: requests Response object with streaming enabled
            format: Output format (events, text, json)

        Yields:
            StreamEvent objects (or strings/dicts based on format)
        """
        import json

        from .streaming import DoneEvent, StreamEvent, StreamEventType, TextDeltaEvent

        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue

            # SSE format: "data: {json}\n\n"
            if line.startswith("data: "):
                data_str = line[6:]  # Remove "data: " prefix

                # Handle special [DONE] marker
                if data_str.strip() == "[DONE]":
                    event = DoneEvent(type=StreamEventType.DONE, raw={})
                    if format == "events":
                        yield event
                    elif format == "json":
                        yield {}
                    # Don't yield anything for text format on DONE
                    continue

                try:
                    event_data = json.loads(data_str)

                    # Debug: Log all events to see structure
                    event_type = event_data.get("type", "unknown")
                    if event_type == "unknown":
                        # Check for nested event structure
                        event_field = event_data.get("event", {})
                        if isinstance(event_field, dict):
                            event_type = f"event.{event_field.get('type', 'unknown')}"
                    # print(
                    #     f"[SDK DEBUG] Received SSE event: type={event_type}, "
                    #     f"keys={list(event_data.keys())}"
                    # )

                    # Detect session.created events and suppress them from downstream consumers
                    event_field = event_data.get("event", {})
                    if (
                        isinstance(event_field, dict)
                        and event_field.get("type") == "session.created"
                    ):
                        continue  # Skip StreamEvent.from_dict() - don't yield this event

                    # Convert to StreamEvent objects (may yield multiple events)
                    events = StreamEvent.from_dict(event_data)

                    # Yield in appropriate format
                    if format == "events":
                        for event in events:
                            yield event
                    elif format == "text":
                        # Only yield text deltas as strings
                        for event in events:
                            if isinstance(event, TextDeltaEvent):
                                yield event.delta
                    elif format == "json":
                        # Yield raw JSON envelope for compatibility
                        yield event_data

                except json.JSONDecodeError:
                    # Skip malformed JSON
                    continue

    def start_chat_session(self, resume_run_id: int | None = None) -> "ChatSession":
        """
        Start interactive chat session (preserves history).

        Args:
            resume_run_id: Optional run ID to resume (loads session_id for continuity)

        Returns:
            ChatSession object for multi-turn conversation
        """
        if resume_run_id:
            # Load existing run for resumption
            # Backend will handle session resumption based on run.claude_session_id
            run = self.service.http.client.runs.get(resume_run_id)
        else:
            # Create new chat run for fresh conversation
            run = self.service.http.client.runs.create(
                instance_id=self.id, run_mode="chat", description="Interactive chat session"
            )

        from .chat import ChatSession

        return ChatSession(self, run)

    def _execute_on_worker(
        self, message: str, clear_first: bool = False, run_id: int | None = None
    ) -> dict[str, Any]:
        """
        Execute message via backend proxy (non-streaming).

        Args:
            message: Message to send to agent
            clear_first: Whether to clear history before execution
            run_id: Optional run ID for tracking

        Returns:
            Response data from backend
        """
        from ..exceptions import AgentError, AuthenticationError

        # Use backend URL instead of direct worker access
        backend_url = self.service.http.base_url
        chat_url = f"{backend_url}/api/v1/agent/instances/{self.id}/chat"
        clear_url = f"{backend_url}/api/v1/agent/instances/{self.id}/chat/clear"

        # Clear history if task mode
        if clear_first:
            with suppress(requests.RequestException):
                requests.post(
                    clear_url,
                    headers={
                        "Authorization": f"Bearer {self.service.http.api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=30,
                )

        # Execute chat via backend proxy
        chat_payload = {"message": message, "stream": False}
        if run_id is not None:
            chat_payload["runId"] = run_id

        try:
            chat_response = requests.post(
                chat_url,
                json=chat_payload,
                headers={
                    "Authorization": f"Bearer {self.service.http.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=60,
            )
            chat_response.raise_for_status()
            return chat_response.json()
        except requests.HTTPError as e:
            if e.response.status_code == 401:
                raise AuthenticationError(
                    "Authentication failed during agent execution.\n"
                    "Your token may have expired. Please login again: m8tes auth login"
                ) from e
            else:
                # Try to get detailed error from response
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", error_data.get("message", str(e)))
                except Exception:
                    error_msg = str(e)
                raise AgentError(f"Agent execution failed: {error_msg}") from e
        except requests.RequestException as e:
            raise AgentError(f"Failed to communicate with backend: {e}") from e

    def _execute_on_worker_streaming(
        self,
        message: str,
        clear_first: bool = False,
        run_id: int | None = None,
        stream: bool = True,
        format: StreamFormat = "events",
    ) -> Generator[StreamEvent, None, None]:
        """
        Execute message via backend proxy with streaming support.

        Args:
            message: Message to send to agent
            clear_first: Whether to clear history before execution
            run_id: Optional run ID for tracking
            stream: Enable streaming
            format: Output format (events, text, json)

        Yields:
            StreamEvent objects (or strings/dicts based on format)
        """
        from .exceptions import AgentError, AuthenticationError
        from .streaming import TextDeltaEvent

        # Use backend URL instead of direct worker access
        backend_url = self.service.http.base_url
        chat_url = f"{backend_url}/api/v1/agent/instances/{self.id}/chat"
        init_url = f"{chat_url}/init"
        clear_url = f"{backend_url}/api/v1/agent/instances/{self.id}/chat/clear"

        common_headers = {
            "Authorization": f"Bearer {self.service.http.api_key}",
            "Content-Type": "application/json",
        }

        # Initialize worker session before clearing/chatting so workers can warm
        # up while tests can provide dedicated mocked responses.
        init_payload = {"stream": stream}
        if run_id is not None:
            init_payload["runId"] = run_id

        try:
            init_response = requests.post(
                init_url,
                json=init_payload,
                headers=common_headers,
                timeout=30,
            )
            init_response.raise_for_status()
        except requests.RequestException:
            # Worker initialization is best-effort; continue when it fails.
            pass

        # Clear history if task mode
        if clear_first:
            with suppress(requests.RequestException):
                requests.post(
                    clear_url,
                    headers=common_headers,
                    timeout=30,
                )

        # Execute chat via backend proxy
        chat_payload = {"message": message, "stream": stream}
        if run_id is not None:
            chat_payload["runId"] = run_id

        try:
            if stream:
                # Streaming request
                chat_response = requests.post(
                    chat_url,
                    json=chat_payload,
                    headers={
                        **common_headers,
                        "Accept": "text/event-stream",
                        "Cache-Control": "no-cache",
                    },
                    stream=True,
                    timeout=None,  # No timeout for streams
                )
                chat_response.raise_for_status()

                # Parse AI SDK stream protocol
                if format == "events":
                    # Yield typed StreamEvent objects
                    for event in AISDKStreamParser.parse_stream(chat_response):
                        yield event

                elif format == "text":
                    # Yield only text deltas as strings
                    for event in AISDKStreamParser.parse_stream(chat_response):
                        if isinstance(event, TextDeltaEvent):
                            yield event.delta

                elif format == "json":
                    # Yield raw JSON dictionaries
                    for event in AISDKStreamParser.parse_stream(chat_response):
                        yield event.raw

            else:
                # Non-streaming request
                chat_response = requests.post(
                    chat_url,
                    json=chat_payload,
                    headers=common_headers,
                    timeout=60,
                )
                chat_response.raise_for_status()
                response_data = chat_response.json()

                # Wrap in event-like structure
                from .streaming import DoneEvent, StreamEventType

                text = response_data.get("message", str(response_data))

                if format == "text":
                    yield text
                elif format == "json":
                    yield response_data
                else:  # events
                    yield TextDeltaEvent(
                        type=StreamEventType.TEXT_DELTA, raw=response_data, delta=text
                    )
                    yield DoneEvent(type=StreamEventType.DONE, raw={})

        except requests.HTTPError as e:
            if e.response.status_code == 401:
                raise AuthenticationError(
                    "Authentication failed during agent execution.\n"
                    "Your token may have expired. Please login again: m8tes auth login"
                ) from e
            else:
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", error_data.get("message", str(e)))
                except Exception:
                    error_msg = str(e)
                raise AgentError(f"Agent execution failed: {error_msg}") from e
        except requests.RequestException as e:
            raise AgentError(f"Failed to communicate with backend: {e}") from e

    def update(
        self,
        name: str | None = None,
        instructions: str | None = None,
    ) -> "AgentInstance":
        """
        Update instance configuration.

        Args:
            name: New name
            instructions: New instructions

        Returns:
            Updated AgentInstance instance
        """
        updated = self.service.update(self.id, name=name, instructions=instructions)
        self.__dict__.update(updated.__dict__)
        return self

    def enable(self) -> "AgentInstance":
        """
        Enable the instance.

        Returns:
            Updated AgentInstance instance

        Raises:
            ValidationError: If instance not found
            AuthenticationError: If not authorized
            NetworkError: If request fails
        """
        updated = self.service.enable(self.id)
        self.__dict__.update(updated.__dict__)
        return self

    def disable(self) -> "AgentInstance":
        """
        Disable the instance (soft disable, still visible with flag).

        This sets the instance status to DISABLED and is_active to False.
        The instance remains visible when listing with include_disabled=True.

        Returns:
            Updated AgentInstance instance

        Raises:
            ValidationError: If instance not found
            AuthenticationError: If not authorized
            NetworkError: If request fails
        """
        updated = self.service.disable(self.id)
        self.__dict__.update(updated.__dict__)
        return self

    def archive(self) -> bool:
        """
        Archive the instance (soft delete, hidden from default listings).

        This performs a soft delete by setting the instance status to ARCHIVED
        and is_active to False. The instance and its run history are preserved
        in the database but will not appear in default listings.

        Returns:
            True if successful

        Raises:
            ValidationError: If instance not found
            AuthenticationError: If not authorized
            NetworkError: If request fails
        """
        return self.service.archive(self.id)

    def __repr__(self) -> str:
        return (
            f"<AgentInstance id={self.id} name='{self.name}' "
            f"cloudflare_id='{self.cloudflare_instance_id}'>"
        )
