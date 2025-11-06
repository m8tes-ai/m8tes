"""Task operations service for m8tes SDK."""

from collections.abc import Generator
from typing import TYPE_CHECKING

import requests

from ..exceptions import AgentError, AuthenticationError
from ..http.client import HTTPClient
from ..streaming import AISDKStreamParser, StreamEvent

if TYPE_CHECKING:
    from ..task import Task


class TaskService:
    """Service for handling task operations."""

    def __init__(self, http_client: HTTPClient):
        """
        Initialize task service.

        Args:
            http_client: HTTP client instance
        """
        self.http = http_client

    def create(
        self,
        agent_instance_id: int,
        name: str,
        instructions: str,
        expected_output: str | None = None,
        goals: str | None = None,
    ) -> "Task":
        """
        Create a new task.

        Args:
            agent_instance_id: Agent instance ID
            name: Task name
            instructions: Task instructions
            expected_output: Expected output description
            goals: Task goals

        Returns:
            Task instance
        """
        from ..task import Task

        request_data = {
            "agent_instance_id": agent_instance_id,
            "name": name,
            "instructions": instructions,
        }
        if expected_output:
            request_data["expected_output"] = expected_output
        if goals:
            request_data["goals"] = goals

        response_data = self.http.request("POST", "/api/v1/tasks", json_data=request_data)
        return Task(task_service=self, data=response_data)

    def get(self, task_id: int) -> "Task":
        """
        Get a task by ID.

        Args:
            task_id: Task ID

        Returns:
            Task instance
        """
        from ..task import Task

        response_data = self.http.request("GET", f"/api/v1/tasks/{task_id}")
        return Task(task_service=self, data=response_data)

    def list(
        self,
        agent_instance_id: int | None = None,
        status: str | None = None,
        include_disabled: bool = False,
        include_archived: bool = False,
    ) -> list["Task"]:
        """
        List tasks with optional filters.

        Args:
            agent_instance_id: Filter by agent instance ID
            status: Filter by status
            include_disabled: Include disabled tasks
            include_archived: Include archived tasks

        Returns:
            List of Task instances
        """
        from ..task import Task

        params = {}
        if agent_instance_id:
            params["agent_instance_id"] = str(agent_instance_id)
        if status:
            params["status"] = status
        if include_disabled:
            params["include_disabled"] = "true"
        if include_archived:
            params["include_archived"] = "true"

        response_data = self.http.request("GET", "/api/v1/tasks", params=params)

        # API returns list directly
        tasks_list: list = response_data if isinstance(response_data, list) else []
        return [Task(task_service=self, data=task_data) for task_data in tasks_list]

    def update(
        self,
        task_id: int,
        name: str | None = None,
        instructions: str | None = None,
        expected_output: str | None = None,
        goals: str | None = None,
    ) -> "Task":
        """
        Update a task.

        Args:
            task_id: Task ID
            name: New task name
            instructions: New instructions
            expected_output: New expected output
            goals: New goals

        Returns:
            Updated Task instance
        """
        from ..task import Task

        update_data = {}
        if name is not None:
            update_data["name"] = name
        if instructions is not None:
            update_data["instructions"] = instructions
        if expected_output is not None:
            update_data["expected_output"] = expected_output
        if goals is not None:
            update_data["goals"] = goals

        if not update_data:
            raise ValueError("At least one field must be provided for update")

        response_data = self.http.request(
            "PATCH", f"/api/v1/tasks/{task_id}", json_data=update_data
        )
        return Task(task_service=self, data=response_data)

    def execute(self, task_id: int) -> Generator[StreamEvent, None, None]:
        """
        Execute a task with streaming support.

        Args:
            task_id: Task ID to execute

        Yields:
            StreamEvent objects from SSE stream

        Raises:
            AuthenticationError: If authentication fails
            AgentError: If execution fails
        """
        execute_url = f"{self.http.base_url}/api/v1/tasks/{task_id}/execute"

        try:
            response = requests.post(
                execute_url,
                headers={
                    "Authorization": f"Bearer {self.http.api_key}",
                    "Content-Type": "application/json",
                },
                stream=True,
                timeout=None,
            )
            response.raise_for_status()

            # Parse SSE stream using AISDKStreamParser
            yield from AISDKStreamParser.parse_stream(response)

        except requests.HTTPError as e:
            if e.response.status_code == 401:
                raise AuthenticationError(
                    "Authentication failed during task execution.\n"
                    "Your token may have expired. Please login again: m8tes --dev auth login"
                ) from e
            else:
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", error_data.get("message", str(e)))
                except Exception:
                    error_msg = str(e)
                raise AgentError(f"Task execution failed: {error_msg}") from e
        except requests.RequestException as e:
            raise AgentError(f"Failed to communicate with backend: {e}") from e

    def enable(self, task_id: int) -> "Task":
        """
        Enable a task.

        Args:
            task_id: Task ID

        Returns:
            Updated Task instance
        """
        from ..task import Task

        response_data = self.http.request("POST", f"/api/v1/tasks/{task_id}/enable")
        return Task(task_service=self, data=response_data)

    def disable(self, task_id: int) -> "Task":
        """
        Disable a task.

        Args:
            task_id: Task ID

        Returns:
            Updated Task instance
        """
        from ..task import Task

        response_data = self.http.request("POST", f"/api/v1/tasks/{task_id}/disable")
        return Task(task_service=self, data=response_data)

    def archive(self, task_id: int) -> bool:
        """
        Archive a task.

        Args:
            task_id: Task ID

        Returns:
            True if successful
        """
        response = self.http.request("DELETE", f"/api/v1/tasks/{task_id}")
        return bool(response.get("success", False))
