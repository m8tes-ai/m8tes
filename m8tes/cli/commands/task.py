"""
Task management commands for the m8tes CLI.

Provides commands for creating, listing, executing, and managing tasks.
"""

from argparse import ArgumentParser, Namespace
from typing import TYPE_CHECKING, ClassVar, Optional

from ...exceptions import AgentError, AuthenticationError, NetworkError, ValidationError
from ..base import Command, CommandGroup
from ..util import show_auth_guidance

if TYPE_CHECKING:
    from ...client import M8tes


class TaskCommandGroup(CommandGroup):
    """Task management command group."""

    name = "task"
    aliases: ClassVar[list[str]] = ["tasks"]
    description = "Manage tasks"
    requires_auth = True

    def __init__(self) -> None:
        super().__init__()
        # Register all task subcommands
        self.add_subcommand(CreateCommand())
        self.add_subcommand(ListCommand())
        self.add_subcommand(GetCommand())
        self.add_subcommand(ExecuteCommand())
        self.add_subcommand(UpdateCommand())
        self.add_subcommand(EnableCommand())
        self.add_subcommand(DisableCommand())
        self.add_subcommand(ArchiveCommand())


class CreateCommand(Command):
    """Task creation command."""

    name = "create"
    aliases: ClassVar[list[str]] = ["c"]
    description = "Create a new task"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add create-specific arguments."""
        # Non-interactive mode flags
        parser.add_argument(
            "--mate-id", help="Teammate ID to assign task to (for non-interactive mode)"
        )
        parser.add_argument("--name", help="Task name (for non-interactive mode)")
        parser.add_argument("--instructions", help="Task instructions (for non-interactive mode)")
        parser.add_argument(
            "--expected-output",
            help="Expected output description",
        )
        parser.add_argument(
            "--goals",
            help="Task goals",
        )
        parser.add_argument(
            "--non-interactive",
            action="store_true",
            help="Skip interactive prompts and use provided flags",
        )

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        """Execute task creation flow."""
        if not client:
            print("❌ Authentication required for task management")
            show_auth_guidance()
            return 1

        from ..tasks import TaskCLI

        task_cli = TaskCLI(client)
        try:
            # Check for non-interactive mode
            non_interactive = getattr(args, "non_interactive", False)

            if non_interactive:
                # Validate required fields for non-interactive
                mate_id = getattr(args, "mate_id", None)
                name = getattr(args, "name", None)
                instructions = getattr(args, "instructions", None)
                expected_output = getattr(args, "expected_output", None)
                goals = getattr(args, "goals", None)

                if not mate_id:
                    print("❌ --mate-id is required for non-interactive mode")
                    return 1
                if not name:
                    print("❌ --name is required for non-interactive mode")
                    return 1
                if not instructions:
                    print("❌ --instructions is required for non-interactive mode")
                    return 1

                # Create task directly
                task_cli.create_non_interactive(
                    mate_id=mate_id,
                    name=name,
                    instructions=instructions,
                    expected_output=expected_output,
                    goals=goals,
                )
            else:
                # Interactive mode
                task_cli.create_interactive()
            return 0
        except AuthenticationError as e:
            print(f"❌ Authentication failed: {e}")
            show_auth_guidance()
            return 1
        except (AgentError, NetworkError, ValidationError) as e:
            print(f"❌ Task creation failed: {e}")
            return 1
        except KeyboardInterrupt:
            print("\n👋 Task creation cancelled.")
            return 1


class ListCommand(Command):
    """Task listing command."""

    name = "list"
    aliases: ClassVar[list[str]] = ["ls"]
    description = "List tasks"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add list-specific arguments."""
        parser.add_argument(
            "--mate-id",
            help="Filter by teammate ID",
        )
        parser.add_argument(
            "--status",
            help="Filter by status",
        )
        parser.add_argument(
            "--include-disabled",
            action="store_true",
            help="Include disabled tasks",
        )
        parser.add_argument(
            "--include-archived",
            action="store_true",
            help="Include archived tasks",
        )

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        """Execute task listing."""
        if not client:
            print("❌ Authentication required for task management")
            show_auth_guidance()
            return 1

        from ..tasks import TaskCLI

        task_cli = TaskCLI(client)
        try:
            mate_id = getattr(args, "mate_id", None)
            status = getattr(args, "status", None)
            include_disabled = getattr(args, "include_disabled", False)
            include_archived = getattr(args, "include_archived", False)

            task_cli.list_interactive(
                mate_id=mate_id,
                status=status,
                include_disabled=include_disabled,
                include_archived=include_archived,
            )
            return 0
        except AuthenticationError as e:
            print(f"❌ Authentication failed: {e}")
            show_auth_guidance()
            return 1
        except (AgentError, NetworkError) as e:
            print(f"❌ Error listing tasks: {e}")
            return 1


class GetCommand(Command):
    """Task get command."""

    name = "get"
    aliases: ClassVar[list[str]] = ["g"]
    description = "Get task details by ID"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add get-specific arguments."""
        parser.add_argument("task_id", help="Task ID to retrieve")

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        """Execute task get."""
        if not client:
            print("❌ Authentication required for task management")
            show_auth_guidance()
            return 1

        from ..tasks import TaskCLI

        task_cli = TaskCLI(client)
        try:
            task_id = args.task_id
            task_cli.get_interactive(task_id)
            return 0
        except AuthenticationError as e:
            print(f"❌ Authentication failed: {e}")
            show_auth_guidance()
            return 1
        except (AgentError, NetworkError) as e:
            print(f"❌ Error getting task: {e}")
            return 1


class ExecuteCommand(Command):
    """Task execution command."""

    name = "execute"
    aliases: ClassVar[list[str]] = ["exec", "x"]
    description = "Execute a task"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add execute-specific arguments."""
        parser.add_argument("task_id", help="Task ID to execute")

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        """Execute task."""
        if not client:
            print("❌ Authentication required for task execution")
            show_auth_guidance()
            return 1

        from ..tasks import TaskCLI

        task_cli = TaskCLI(client)
        try:
            task_id = args.task_id
            task_cli.execute_interactive(task_id)
            return 0
        except AuthenticationError as e:
            print(f"❌ Authentication failed: {e}")
            show_auth_guidance()
            return 1
        except (AgentError, NetworkError) as e:
            print(f"❌ Task execution failed: {e}")
            return 1
        except KeyboardInterrupt:
            print("\n👋 Task execution cancelled.")
            return 1


class UpdateCommand(Command):
    """Task update command."""

    name = "update"
    aliases: ClassVar[list[str]] = ["u"]
    description = "Update task configuration"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add update-specific arguments."""
        parser.add_argument("task_id", help="Task ID to update")
        parser.add_argument("--name", help="New task name")
        parser.add_argument("--instructions", help="New task instructions")
        parser.add_argument("--expected-output", help="New expected output")
        parser.add_argument("--goals", help="New task goals")

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        """Execute task update."""
        if not client:
            print("❌ Authentication required for task management")
            show_auth_guidance()
            return 1

        from ..tasks import TaskCLI

        task_cli = TaskCLI(client)
        try:
            task_id = args.task_id
            name = getattr(args, "name", None)
            instructions = getattr(args, "instructions", None)
            expected_output = getattr(args, "expected_output", None)
            goals = getattr(args, "goals", None)

            if not any([name, instructions, expected_output, goals]):
                print("❌ At least one field must be provided for update")
                return 1

            task_cli.update_interactive(
                task_id=task_id,
                name=name,
                instructions=instructions,
                expected_output=expected_output,
                goals=goals,
            )
            return 0
        except AuthenticationError as e:
            print(f"❌ Authentication failed: {e}")
            show_auth_guidance()
            return 1
        except (AgentError, NetworkError, ValidationError) as e:
            print(f"❌ Error updating task: {e}")
            return 1


class EnableCommand(Command):
    """Task enable command."""

    name = "enable"
    aliases: ClassVar[list[str]] = ["e"]
    description = "Enable a disabled task"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add enable-specific arguments."""
        parser.add_argument("task_id", help="Task ID to enable")

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        """Execute task enable."""
        if not client:
            print("❌ Authentication required for task management")
            show_auth_guidance()
            return 1

        from ..tasks import TaskCLI

        task_cli = TaskCLI(client)
        try:
            task_id = args.task_id
            task_cli.enable_interactive(task_id)
            return 0
        except AuthenticationError as e:
            print(f"❌ Authentication failed: {e}")
            show_auth_guidance()
            return 1
        except (AgentError, NetworkError, ValidationError) as e:
            print(f"❌ Error enabling task: {e}")
            return 1


class DisableCommand(Command):
    """Task disable command."""

    name = "disable"
    aliases: ClassVar[list[str]] = ["dis"]
    description = "Disable a task"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add disable-specific arguments."""
        parser.add_argument("task_id", help="Task ID to disable")

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        """Execute task disable."""
        if not client:
            print("❌ Authentication required for task management")
            show_auth_guidance()
            return 1

        from ..tasks import TaskCLI

        task_cli = TaskCLI(client)
        try:
            task_id = args.task_id
            task_cli.disable_interactive(task_id)
            return 0
        except AuthenticationError as e:
            print(f"❌ Authentication failed: {e}")
            show_auth_guidance()
            return 1
        except (AgentError, NetworkError, ValidationError) as e:
            print(f"❌ Error disabling task: {e}")
            return 1


class ArchiveCommand(Command):
    """Task archive command."""

    name = "archive"
    aliases: ClassVar[list[str]] = ["arc", "a"]
    description = "Archive a task"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add archive-specific arguments."""
        parser.add_argument("task_id", help="Task ID to archive")

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        """Execute task archiving."""
        if not client:
            print("❌ Authentication required for task management")
            show_auth_guidance()
            return 1

        from ..tasks import TaskCLI

        task_cli = TaskCLI(client)
        try:
            task_id = args.task_id
            task_cli.archive_interactive(task_id)
            return 0
        except AuthenticationError as e:
            print(f"❌ Authentication failed: {e}")
            show_auth_guidance()
            return 1
        except (AgentError, NetworkError, ValidationError) as e:
            print(f"❌ Error archiving task: {e}")
            return 1
