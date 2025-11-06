"""
Task management CLI commands.

Provides interactive commands for creating and managing tasks.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import M8tes


class TaskCLI:
    """CLI for task management operations."""

    def __init__(self, client: "M8tes"):
        """
        Initialize TaskCLI.

        Args:
            client: M8tes client instance
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

        # Step 1: Show available teammates and get mate_id
        try:
            instances = self.client.instances.list()
            if not instances:
                print("❌ No teammates available. Create a teammate first.")
                print("💡 Run: m8tes mate create")
                return

            print("Available teammates:")
            print()
            for instance in instances:
                status_emoji = "✅" if instance.status == "enabled" else "⏸️"
                print(f"  {status_emoji} {instance.id}: {instance.name}")
                if instance.role:
                    print(f"     Role: {instance.role}")
            print()
        except Exception as e:
            print(f"❌ Failed to list teammates: {e}")
            return

        # Prompt for teammate ID
        mate_id_str = prompt("Teammate ID: ")
        try:
            mate_id = int(mate_id_str)
        except ValueError:
            print("❌ Teammate ID must be a number")
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
        print(f"  Teammate ID: {mate_id}")
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
        try:
            print("⏳ Creating task...")
            task = self.client.tasks.create(
                agent_instance_id=mate_id,
                name=task_name,
                instructions=instructions,
                expected_output=expected_output,
                goals=goals,
            )

            print("✅ Task created successfully!")
            print(f"   ID: {task.id}")
            print(f"   Name: {task.name}")
            print(f"   Status: {task.status}")
            print()
            print("💡 To execute this task:")
            print(f"   m8tes task execute {task.id}")

        except Exception as e:
            raise Exception(f"Failed to create task: {e}") from e

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
            mate_id: Teammate ID to assign task to
            name: Task name
            instructions: Task instructions
            expected_output: Expected output description
            goals: Task goals
        """
        try:
            task = self.client.tasks.create(
                agent_instance_id=int(mate_id),
                name=name,
                instructions=instructions,
                expected_output=expected_output,
                goals=goals,
            )

            print("✅ Task created successfully!")
            print(f"   ID: {task.id}")
            print(f"   Name: {task.name}")
            print(f"   Status: {task.status}")
            print()
            print("💡 To execute this task:")
            print(f"   m8tes task execute {task.id}")

        except Exception as e:
            raise Exception(f"Failed to create task: {e}") from e

    def list_interactive(
        self,
        mate_id: str | None = None,
        status: str | None = None,
        include_disabled: bool = False,
        include_archived: bool = False,
    ) -> None:
        """
        List tasks with optional filters.

        Args:
            mate_id: Filter by teammate ID
            status: Filter by status
            include_disabled: Include disabled tasks
            include_archived: Include archived tasks
        """
        try:
            print("📋 Tasks")
            print()

            agent_instance_id = int(mate_id) if mate_id else None
            tasks = self.client.tasks.list(
                agent_instance_id=agent_instance_id,
                status=status,
                include_disabled=include_disabled,
                include_archived=include_archived,
            )

            if not tasks:
                print("No tasks found.")
                print(
                    "💡 Create a new task with: m8tes task create <mate_id> <name> <instructions>"
                )
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
                if task.agent_instance_id:
                    print(f"   Teammate: {task.agent_instance_id}")

                # Truncate instructions
                instructions = (task.instructions or "").strip()
                if instructions:
                    if len(instructions) > 80:
                        instructions = instructions[:77] + "..."
                    print(f"   Instructions: {instructions}")

                if task.expected_output:
                    print(f"   Expected output: {task.expected_output[:80]}")

                print()

        except Exception as e:
            print(f"❌ Failed to list tasks: {e}")

    def get_interactive(self, task_id: str) -> None:
        """
        Get task details by ID.

        Args:
            task_id: Task ID to retrieve
        """
        try:
            task = self.client.tasks.get(int(task_id))

            print("📋 Task Details")
            print()
            print(f"  ID: {task.id}")
            print(f"  Name: {task.name}")
            print(f"  Status: {task.status}")
            if task.agent_instance_id:
                print(f"  Teammate: {task.agent_instance_id}")
            print(f"  Instructions: {task.instructions}")
            if task.expected_output:
                print(f"  Expected output: {task.expected_output}")
            if task.goals:
                print(f"  Goals: {task.goals}")
            if task.created_at:
                print(f"  Created: {task.created_at}")
            if task.updated_at:
                print(f"  Updated: {task.updated_at}")

        except ValueError as e:
            print(f"❌ Invalid task ID: {e}")
        except Exception as e:
            print(f"❌ Failed to get task: {e}")

    def execute_interactive(self, task_id: str) -> None:
        """
        Execute a task with streaming.

        Args:
            task_id: Task ID to execute
        """
        from .display import create_display

        try:
            task = self.client.tasks.get(int(task_id))

            print(f"🎯 Executing task: {task.name}")
            print()

            # Create display renderer
            display = create_display("verbose")
            display.start()

            # Stream task execution
            try:
                for event in task.execute():
                    display.on_event(event)

                display.finish()

                # Check for errors
                if display.accumulator.has_errors():
                    print("\n❌ Task execution failed:")
                    for error in display.accumulator.get_errors():
                        print(f"   {error}")
                else:
                    print("\n✅ Task completed")

            except KeyboardInterrupt:
                display.finish()
                print("\n\n⏸️  Task execution interrupted")
                raise

        except Exception as e:
            print(f"❌ Failed to execute task: {e}")

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
        try:
            task = self.client.tasks.update(
                int(task_id),
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

        except Exception as e:
            print(f"❌ Failed to update task: {e}")

    def enable_interactive(self, task_id: str) -> None:
        """
        Enable a disabled task.

        Args:
            task_id: Task ID to enable
        """
        try:
            task = self.client.tasks.enable(int(task_id))

            print("✅ Task enabled successfully!")
            print(f"   ID: {task.id}")
            print(f"   Status: {task.status}")

        except Exception as e:
            print(f"❌ Failed to enable task: {e}")

    def disable_interactive(self, task_id: str) -> None:
        """
        Disable a task.

        Args:
            task_id: Task ID to disable
        """
        try:
            task = self.client.tasks.disable(int(task_id))

            print("✅ Task disabled successfully!")
            print(f"   ID: {task.id}")
            print(f"   Status: {task.status}")

        except Exception as e:
            print(f"❌ Failed to disable task: {e}")

    def archive_interactive(self, task_id: str) -> None:
        """
        Archive a task.

        Args:
            task_id: Task ID to archive
        """
        try:
            success = self.client.tasks.archive(int(task_id))

            if success:
                print("✅ Task archived successfully!")
                print(f"   ID: {task_id}")
            else:
                print("❌ Failed to archive task")

        except Exception as e:
            print(f"❌ Failed to archive task: {e}")
