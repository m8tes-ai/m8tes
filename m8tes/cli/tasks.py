"""
Task management CLI commands, on the v2 SDK.

`TaskCLI` drives `m8tes task …` through the v2 developer client
(`m8tes._client.M8tes`) — the CLI is an API customer like anyone else, so a fix
lands once. Nothing here touches the legacy v1 client, task model, or services.

Error contract: fatal failures raise typed v2 exceptions (`m8tes._exceptions`) so
the command layer maps them to a non-zero exit code. Helpers never swallow a
fatal error — a swallowed error made `m8tes task list` exit 0 on auth failure.

Known v2 gap, surfaced rather than worked around:
- **`Tasks.list()` has no `status` / `include_disabled` query twin**, so the CLI
  pages through the list and filters locally to keep both flags meaningful.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from .._exceptions import RunFailedError
from .util import parse_id as _parse_id

if TYPE_CHECKING:
    from .._client import M8tes
    from .._streaming import RunStream
    from .._types import Task


def _is_visible(task: Task, *, status: str | None, include_disabled: bool) -> bool:
    """Client-side stand-in for the v1 list filters v2 does not expose as query params."""
    if status:
        return task.status == status
    return include_disabled or task.status != "disabled"


class TaskCLI:
    """CLI for task management operations."""

    def __init__(self, client: M8tes):
        """
        Initialize TaskCLI.

        Args:
            client: v2 SDK client
        """
        self.client = client

    def create_interactive(self) -> None:
        """
        Interactive task creation flow.

        Prompts the user for all required fields.
        """
        from .prompt import confirm_prompt, prompt

        print("📝 Create New Task")
        print()
        print("Configure your task by providing all required information.")
        print()

        # Step 1: Show available agents and get mate_id
        agents = list(self.client.agents.list().auto_paging_iter())
        if not agents:
            print("❌ No agents available. Create an agent first.")
            print("💡 Run: m8tes agent create")
            return

        print("Available agents:")
        print()
        for agent in agents:
            status_emoji = "✅" if agent.status == "enabled" else "⏸️"
            print(f"  {status_emoji} {agent.id}: {agent.name}")
            if agent.role:
                print(f"     Role: {agent.role}")
        print()

        # Prompt for agent ID
        mate_id_str = prompt("Agent ID: ")
        try:
            mate_id = int(mate_id_str)
        except ValueError:
            print("❌ Agent ID must be a number")
            return

        # Step 2: Task name (required)
        task_name = prompt("Task name: ")
        if not task_name.strip():
            print("❌ Task name cannot be empty")
            return

        # Step 3: Instructions (required, multi-line)
        print()
        print("Instructions: Describe what this task should do.")
        print("When you're finished press Enter twice")
        print()

        instructions_lines: list[str] = []
        try:
            while True:
                line = input()
                if line.strip().lower() == "/done":
                    break
                if line == "" and instructions_lines and instructions_lines[-1] == "":
                    break
                instructions_lines.append(line)
        except EOFError:
            pass

        instructions = "\n".join(instructions_lines).strip()
        if not instructions:
            print("❌ Instructions cannot be empty")
            return

        # Step 4: Expected output (optional)
        print()
        expected_output_input = prompt("Expected output (optional): ", allow_empty=True)
        expected_output: str | None = (
            None if not expected_output_input.strip() else expected_output_input
        )

        # Step 5: Goals (optional)
        print()
        goals_input = prompt("Goals (optional): ", allow_empty=True)
        goals: str | None = None if not goals_input.strip() else goals_input

        # Show summary
        print()
        print("=" * 60)
        print("📋 Task Configuration Summary:")
        print("=" * 60)
        print(f"  Agent ID: {mate_id}")
        print(f"  Task Name: {task_name}")
        print(f"  Instructions: {instructions[:100]}{'...' if len(instructions) > 100 else ''}")
        if expected_output:
            print(f"  Expected Output: {expected_output}")
        if goals:
            print(f"  Goals: {goals}")
        print("=" * 60)
        print()

        # Confirm creation
        if not confirm_prompt("Create this task?", default=True):
            print("❌ Task creation cancelled")
            return

        # Create the task
        print("⏳ Creating task...")
        task = self.client.tasks.create(
            agent_id=mate_id,
            name=task_name,
            instructions=instructions,
            expected_output=expected_output,
            goals=goals,
        )

        self._print_created(task)

    def create_non_interactive(
        self,
        mate_id: str,
        name: str,
        instructions: str,
        expected_output: str | None = None,
        goals: str | None = None,
    ) -> None:
        """
        Non-interactive task creation.

        Args:
            mate_id: Agent ID to assign task to
            name: Task name
            instructions: Task instructions
            expected_output: Expected output description
            goals: Task goals
        """
        task = self.client.tasks.create(
            agent_id=_parse_id(mate_id, "Teammate ID"),
            name=name,
            instructions=instructions,
            expected_output=expected_output,
            goals=goals,
        )

        self._print_created(task)

    def _print_created(self, task: Task) -> None:
        """Shared confirmation for both creation flows."""
        print("✅ Task created successfully!")
        print(f"   ID: {task.id}")
        print(f"   Name: {task.name}")
        print(f"   Status: {task.status}")
        print()
        print("💡 To execute this task:")
        print(f"   m8tes task execute {task.id}")

    def list_interactive(
        self,
        mate_id: str | None = None,
        status: str | None = None,
        include_disabled: bool = False,
        include_archived: bool = False,
    ) -> None:
        """
        List tasks with optional filters.

        v2 exposes no status/include_disabled query params on `Tasks.list()`, so
        those flags are honoured client-side (see the module docstring);
        `include_archived` maps straight to the query param.

        Args:
            mate_id: Filter by agent ID
            status: Filter by status
            include_disabled: Include disabled tasks
            include_archived: Include archived tasks
        """
        print("📋 Tasks")
        print()

        agent_id = _parse_id(mate_id, "Teammate ID") if mate_id else None
        page = self.client.tasks.list(agent_id=agent_id, include_archived=include_archived)
        tasks = [
            task
            for task in page.auto_paging_iter()
            if _is_visible(task, status=status, include_disabled=include_disabled)
        ]

        if not tasks:
            print("No tasks found.")
            print("💡 Create a new task with: m8tes task create <mate_id> <name> <instructions>")
            return

        for task in tasks:
            # Status emoji
            if task.status == "enabled":
                status_emoji = "✅"
            elif task.status == "disabled":
                status_emoji = "⏸️"
            elif task.status == "archived":
                status_emoji = "🗑️"
            else:
                status_emoji = "📋"

            print(f"{status_emoji} {task.name}")
            print(f"   ID: {task.id}")
            print(f"   Status: {task.status}")
            if task.teammate_id:
                print(f"   Agent: {task.teammate_id}")

            # Truncate instructions
            instructions = (task.instructions or "").strip()
            if instructions:
                if len(instructions) > 80:
                    instructions = instructions[:77] + "..."
                print(f"   Instructions: {instructions}")

            if task.expected_output:
                print(f"   Expected output: {task.expected_output[:80]}")

            print()

    def get_interactive(self, task_id: str) -> None:
        """
        Get task details by ID.

        Args:
            task_id: Task ID to retrieve
        """
        task = self.client.tasks.get(_parse_id(task_id, "Task ID"))

        print("📋 Task Details")
        print()
        print(f"  ID: {task.id}")
        print(f"  Name: {task.name}")
        print(f"  Status: {task.status}")
        if task.teammate_id:
            print(f"  Agent: {task.teammate_id}")
        print(f"  Instructions: {task.instructions}")
        if task.expected_output:
            print(f"  Expected output: {task.expected_output}")
        if task.goals:
            print(f"  Goals: {task.goals}")
        if task.created_at:
            print(f"  Created: {task.created_at}")
        if task.updated_at:
            print(f"  Updated: {task.updated_at}")

    def execute_interactive(self, task_id: str) -> None:
        """
        Execute a task with streaming.

        Args:
            task_id: Task ID to execute
        """
        from .display import create_display

        parsed_id = _parse_id(task_id, "Task ID")
        task = self.client.tasks.get(parsed_id)

        print(f"🎯 Executing task: {task.name}")
        print()

        # Create display renderer
        display = create_display("verbose")
        display.start()

        # Stream the run (RunStream closes the response when iteration ends)
        stream = cast("RunStream", self.client.tasks.run(parsed_id, stream=True))
        try:
            for event in stream:
                display.on_event(event)

            display.finish()

            # Check for errors
            if display.accumulator.has_errors():
                errors = display.accumulator.get_errors()
                print("\n❌ Task execution failed:")
                for error in errors:
                    print(f"   {error}")
                raise RunFailedError("Run finished with errors", details={"errors": errors})
            print("\n✅ Task completed")

        except KeyboardInterrupt:
            display.finish()
            print("\n\n⏸️  Task execution interrupted")
            raise

    def update_interactive(
        self,
        task_id: str,
        name: str | None = None,
        instructions: str | None = None,
        expected_output: str | None = None,
        goals: str | None = None,
    ) -> None:
        """
        Update a task.

        Args:
            task_id: Task ID to update
            name: New task name
            instructions: New instructions
            expected_output: New expected output
            goals: New goals
        """
        task = self.client.tasks.update(
            _parse_id(task_id, "Task ID"),
            name=name,
            instructions=instructions,
            expected_output=expected_output,
            goals=goals,
        )

        print("✅ Task updated successfully!")
        print(f"   ID: {task.id}")
        if name:
            print(f"   Name: {task.name}")
        if instructions:
            print("   Instructions: Updated")
        if expected_output:
            print("   Expected output: Updated")
        if goals:
            print("   Goals: Updated")

    def enable_interactive(self, task_id: str) -> None:
        """Enable a disabled task (re-arms schedules its disable paused)."""
        task = self.client.tasks.update(_parse_id(task_id, "Task ID"), status="enabled")
        print("✅ Task enabled!")
        print(f"   ID: {task.id}")
        print(f"   Status: {task.status}")

    def disable_interactive(self, task_id: str) -> None:
        """Disable a task (pauses its schedules and event triggers)."""
        task = self.client.tasks.update(_parse_id(task_id, "Task ID"), status="disabled")
        print("⏸️  Task disabled!")
        print(f"   ID: {task.id}")
        print(f"   Status: {task.status}")

    def archive_interactive(self, task_id: str) -> None:
        """
        Archive a task.

        Args:
            task_id: Task ID to archive
        """
        # v2 DELETE archives and answers 204 — failure arrives as a typed exception,
        # so there is no success flag to check any more.
        self.client.tasks.delete(_parse_id(task_id, "Task ID"))

        print("✅ Task archived successfully!")
        print(f"   ID: {task_id}")
