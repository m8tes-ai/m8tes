"""Task class for managing work assignments."""

from collections.abc import Generator
from typing import TYPE_CHECKING, Any

from .streaming import StreamEvent

if TYPE_CHECKING:
    from .services.tasks import TaskService


class Task:
    """Represents a task assignment."""

    def __init__(self, task_service: "TaskService", data: dict[str, Any]):
        """
        Initialize a Task.

        Args:
            task_service: Task service instance
            data: Task data from API
        """
        self.service = task_service
        self.id: int = data["id"]  # Required field, will raise KeyError if missing
        self.agent_instance_id = data.get("agent_instance_id")
        self.name = data.get("name")
        self.instructions = data.get("instructions")
        self.expected_output = data.get("expected_output")
        self.goals = data.get("goals")
        self.status = data.get("status")
        self.created_at = data.get("created_at")
        self.updated_at = data.get("updated_at")
        self._data = data

    def execute(self) -> Generator[StreamEvent, None, None]:
        """
        Execute task with streaming.

        Yields:
            StreamEvent objects from SSE stream
        """
        yield from self.service.execute(self.id)

    def update(
        self,
        name: str | None = None,
        instructions: str | None = None,
        expected_output: str | None = None,
        goals: str | None = None,
    ) -> "Task":
        """
        Update task configuration.

        Args:
            name: New task name
            instructions: New instructions
            expected_output: New expected output
            goals: New goals

        Returns:
            Updated Task instance
        """
        updated = self.service.update(
            self.id,
            name=name,
            instructions=instructions,
            expected_output=expected_output,
            goals=goals,
        )
        self.__dict__.update(updated.__dict__)
        return self

    def enable(self) -> "Task":
        """
        Enable task.

        Returns:
            Updated Task instance
        """
        updated = self.service.enable(self.id)
        self.__dict__.update(updated.__dict__)
        return self

    def disable(self) -> "Task":
        """
        Disable task.

        Returns:
            Updated Task instance
        """
        updated = self.service.disable(self.id)
        self.__dict__.update(updated.__dict__)
        return self

    def archive(self) -> bool:
        """
        Archive task.

        Returns:
            True if successful
        """
        return self.service.archive(self.id)

    def __repr__(self) -> str:
        return f"<Task id={self.id} name='{self.name}' status='{self.status}'>"
