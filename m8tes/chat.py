"""
ChatSession class for interactive agent conversations.
"""

# mypy: disable-error-code="return-value"
from collections.abc import Generator
from typing import TYPE_CHECKING, Literal

from .streaming import StreamEvent

if TYPE_CHECKING:
    from .instance import AgentInstance
    from .run import Run

StreamFormat = Literal["events", "text", "json"]


class ChatSession:
    """Interactive chat session with preserved history."""

    def __init__(self, instance: "AgentInstance", run: "Run"):
        """
        Initialize a ChatSession.

        Args:
            instance: AgentInstance to chat with
            run: Run object tracking this chat session
        """
        self.instance = instance
        self.run = run

    def send(
        self, message: str, stream: bool = True, format: StreamFormat = "events"
    ) -> Generator[StreamEvent, None, None]:
        """
        Send message in chat session with streaming support.

        Args:
            message: User message
            stream: Enable streaming (default: True)
            format: Output format - "events", "text", or "json"

        Yields:
            StreamEvent objects (or strings/dicts based on format)
        """
        # Stream all events, passing run_id to backend so it reuses our run
        yield from self.instance._execute_via_sdk(
            message, mode="chat", format=format, stream=stream, run_id=self.run.id
        )

    def clear_history(self) -> None:
        """
        Clear conversation history.

        Resets the session ID so the next message starts a fresh conversation.
        """
        self.instance._session_id = None

    def end(self) -> None:
        """End chat session."""
        pass  # Run is tracked in backend, no need to update status

    def __enter__(self) -> "ChatSession":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Context manager exit - automatically end session."""
        self.end()
        return False  # Don't suppress exceptions

    def __repr__(self) -> str:
        return f"<ChatSession instance_id={self.instance.id} run_id={self.run.id}>"
