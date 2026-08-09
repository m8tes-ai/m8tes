"""
Task management commands for the m8tes CLI, on the v2 SDK.

Thin argparse layer over `cli.tasks.TaskCLI`, which talks to the v2 client. Each
command maps a fatal error to exit 1 and prints the same message it always has;
auth failures additionally print the login guidance.

Two error bases are caught because two still exist: the v2 client raises
`m8tes._exceptions.M8tesError` subclasses, while `cli.util.parse_id` (shared with
the not-yet-ported commands) still raises the legacy `m8tes.exceptions`
ValidationError for a non-numeric ID.
"""

from argparse import ArgumentParser, Namespace
from collections.abc import Callable
from typing import TYPE_CHECKING, ClassVar, Optional

from ..._exceptions import AuthenticationError, M8tesError
from ...exceptions import M8tesError as LegacyM8tesError
from ..base import Command, CommandGroup
from ..util import show_auth_guidance

if TYPE_CHECKING:
    from ..._client import M8tes
    from ..tasks import TaskCLI


def _run(action: str, work: Callable[[], None], *, cancelled: str | None = None) -> int:
    """Run a TaskCLI call, mapping every fatal error to exit 1 with its message."""
    try:
        work()
        return 0
    except AuthenticationError as e:
        print(f"❌ Authentication failed: {e}")
        show_auth_guidance()
        return 1
    except (M8tesError, LegacyM8tesError) as e:
        print(f"❌ {action}: {e}")
        return 1
    except KeyboardInterrupt:
        if cancelled is None:
            raise
        print(f"\n👋 {cancelled}")
        return 1


def _task_cli(client: "M8tes") -> "TaskCLI":
    """Build the TaskCLI (imported lazily so tests can patch the class)."""
    from ..tasks import TaskCLI

    return TaskCLI(client)


def _require_client(client: Optional["M8tes"], purpose: str = "task management") -> bool:
    """Print the auth guidance when no client was resolved."""
    if client:
        return True
    print(f"❌ Authentication required for {purpose}")
    show_auth_guidance()
    return False


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
            "--mate-id", help="Agent ID to assign task to (for non-interactive mode)"
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
        if not _require_client(client):
            return 1

        task_cli = _task_cli(client)  # type: ignore[arg-type]

        if not getattr(args, "non_interactive", False):
            return _run(
                "Task creation failed",
                task_cli.create_interactive,
                cancelled="Task creation cancelled.",
            )

        # Validate required fields for non-interactive
        mate_id = getattr(args, "mate_id", None)
        name = getattr(args, "name", None)
        instructions = getattr(args, "instructions", None)

        if not mate_id:
            print("❌ --mate-id is required for non-interactive mode")
            return 1
        if not name:
            print("❌ --name is required for non-interactive mode")
            return 1
        if not instructions:
            print("❌ --instructions is required for non-interactive mode")
            return 1

        return _run(
            "Task creation failed",
            lambda: task_cli.create_non_interactive(
                mate_id=mate_id,
                name=name,
                instructions=instructions,
                expected_output=getattr(args, "expected_output", None),
                goals=getattr(args, "goals", None),
            ),
            cancelled="Task creation cancelled.",
        )


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
            help="Filter by agent ID",
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
        if not _require_client(client):
            return 1

        task_cli = _task_cli(client)  # type: ignore[arg-type]
        return _run(
            "Error listing tasks",
            lambda: task_cli.list_interactive(
                mate_id=getattr(args, "mate_id", None),
                status=getattr(args, "status", None),
                include_disabled=getattr(args, "include_disabled", False),
                include_archived=getattr(args, "include_archived", False),
            ),
        )


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
        if not _require_client(client):
            return 1

        task_cli = _task_cli(client)  # type: ignore[arg-type]
        return _run("Error getting task", lambda: task_cli.get_interactive(args.task_id))


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
        if not _require_client(client, "task execution"):
            return 1

        task_cli = _task_cli(client)  # type: ignore[arg-type]
        return _run(
            "Task execution failed",
            lambda: task_cli.execute_interactive(args.task_id),
            cancelled="Task execution cancelled.",
        )


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
        if not _require_client(client):
            return 1

        name = getattr(args, "name", None)
        instructions = getattr(args, "instructions", None)
        expected_output = getattr(args, "expected_output", None)
        goals = getattr(args, "goals", None)

        if not any([name, instructions, expected_output, goals]):
            print("❌ At least one field must be provided for update")
            return 1

        task_cli = _task_cli(client)  # type: ignore[arg-type]
        return _run(
            "Error updating task",
            lambda: task_cli.update_interactive(
                task_id=args.task_id,
                name=name,
                instructions=instructions,
                expected_output=expected_output,
                goals=goals,
            ),
        )


class EnableCommand(Command):
    """Task enable command (v2 PATCH status=enabled)."""

    name = "enable"
    aliases: ClassVar[list[str]] = ["e"]
    description = "Enable a disabled task"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add enable-specific arguments."""
        parser.add_argument("task_id", help="Task ID to enable")

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        """Execute task enable."""
        if not _require_client(client):
            return 1

        task_cli = _task_cli(client)  # type: ignore[arg-type]
        return _run("Error enabling task", lambda: task_cli.enable_interactive(args.task_id))


class DisableCommand(Command):
    """Task disable command (v2 PATCH status=disabled)."""

    name = "disable"
    aliases: ClassVar[list[str]] = ["dis"]
    description = "Disable a task"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add disable-specific arguments."""
        parser.add_argument("task_id", help="Task ID to disable")

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        """Execute task disable."""
        if not _require_client(client):
            return 1

        task_cli = _task_cli(client)  # type: ignore[arg-type]
        return _run("Error disabling task", lambda: task_cli.disable_interactive(args.task_id))


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
        if not _require_client(client):
            return 1

        task_cli = _task_cli(client)  # type: ignore[arg-type]
        return _run("Error archiving task", lambda: task_cli.archive_interactive(args.task_id))
