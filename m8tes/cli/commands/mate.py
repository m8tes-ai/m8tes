"""
Teammate management commands for the m8tes CLI.

Provides commands for creating, listing, running, and checking teammate status.
"""

from argparse import Action, ArgumentParser, Namespace
from collections.abc import Sequence
import shlex
from typing import TYPE_CHECKING, ClassVar, Optional

from ...exceptions import AgentError, AuthenticationError, NetworkError, ValidationError
from ..base import Command, CommandGroup
from ..util import show_auth_guidance

if TYPE_CHECKING:
    from ...client import M8tes


class MateCommandGroup(CommandGroup):
    """Teammate management command group."""

    name = "mate"
    aliases: ClassVar[list[str]] = ["teammate", "m"]
    description = "Manage AI teammates"
    requires_auth = True

    def __init__(self) -> None:
        super().__init__()
        # Register all teammate subcommands
        self.add_subcommand(CreateCommand())
        self.add_subcommand(ListCommand())
        self.add_subcommand(GetCommand())
        self.add_subcommand(TaskCommand())
        self.add_subcommand(ChatCommand())
        self.add_subcommand(UpdateCommand())
        self.add_subcommand(EnableCommand())
        self.add_subcommand(DisableCommand())
        self.add_subcommand(ArchiveCommand())


class CreateCommand(Command):
    """Teammate creation command."""

    name = "create"
    aliases: ClassVar[list[str]] = ["c"]
    description = "Create a new teammate"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add create-specific arguments."""
        # Non-interactive mode flags
        parser.add_argument("--name", help="Teammate name (for non-interactive mode)")
        parser.add_argument(
            "--tools",
            nargs="+",
            help=(
                "Tool IDs space-separated (for non-interactive mode). "
                "Example: --tools run_gaql_query. Required for non-interactive mode."
            ),
        )
        parser.add_argument(
            "--instructions",
            help="Teammate instructions (for non-interactive mode)",
        )
        parser.add_argument(
            "--role",
            help="Teammate role or persona (for non-interactive mode)",
        )
        parser.add_argument(
            "--goals",
            help=(
                "Goals & metrics description (for non-interactive mode). "
                'Example: --goals "Improve ROAS while keeping CPC under $2"'
            ),
        )
        parser.add_argument(
            "--integrations",
            nargs="+",
            type=int,
            help=(
                "Integration IDs (AppIntegration catalog IDs) space-separated. "
                "Example: --integrations 1 2. "
                "Run 'm8tes integrations list' to see available integrations."
            ),
        )
        parser.add_argument(
            "--non-interactive",
            action="store_true",
            help="Skip interactive prompts and use provided flags",
        )

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        """Execute teammate creation flow."""
        if not client:
            print("❌ Authentication required for teammate management")
            show_auth_guidance()
            return 1

        from ..mates import MateCLI

        mate_cli = MateCLI(client)
        try:
            # Check for non-interactive mode
            non_interactive = getattr(args, "non_interactive", False)

            if non_interactive:
                # Validate required fields for non-interactive
                name = getattr(args, "name", None)
                instructions = getattr(args, "instructions", None)
                tools = getattr(args, "tools", None)
                role = getattr(args, "role", None)
                goals_str = getattr(args, "goals", None)
                integration_ids = getattr(args, "integrations", None)

                if not name:
                    print("❌ --name is required for non-interactive mode")
                    return 1
                if not instructions:
                    print("❌ --instructions is required for non-interactive mode")
                    return 1
                if not tools:
                    print("❌ --tools is required for non-interactive mode")
                    print("   Example: --tools run_gaql_query")
                    return 1

                goals = goals_str.strip() if goals_str and goals_str.strip() else None

                # Create teammate directly
                mate_cli.create_non_interactive(
                    name=name,
                    tools=tools,
                    instructions=instructions,
                    role=role.strip() if role else None,
                    goals=goals,
                    integration_ids=integration_ids,
                )
            else:
                # Interactive mode
                mate_cli.create_interactive()
            return 0
        except AuthenticationError as e:
            print(f"❌ Authentication failed: {e}")
            show_auth_guidance()
            return 1
        except (AgentError, NetworkError, ValidationError) as e:
            print(f"❌ Teammate creation failed: {e}")
            return 1
        except KeyboardInterrupt:
            print("\n👋 Teammate creation cancelled.")
            return 1


class ListCommand(Command):
    """Teammate listing command."""

    name = "list"
    aliases: ClassVar[list[str]] = ["ls"]
    description = "List all teammates"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add list-specific arguments."""
        parser.add_argument(
            "--include-disabled",
            action="store_true",
            help="Include disabled teammates in the listing",
        )

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        """Execute teammate listing."""
        if not client:
            print("❌ Authentication required for teammate management")
            show_auth_guidance()
            return 1

        from ..mates import MateCLI

        mate_cli = MateCLI(client)
        try:
            include_disabled = getattr(args, "include_disabled", False)
            mate_cli.list_interactive(include_disabled=include_disabled)
            return 0
        except AuthenticationError as e:
            print(f"❌ Authentication failed: {e}")
            show_auth_guidance()
            return 1
        except (AgentError, NetworkError) as e:
            print(f"❌ Error listing teammates: {e}")
            return 1


class GetCommand(Command):
    """Teammate get command."""

    name = "get"
    aliases: ClassVar[list[str]] = ["g"]
    description = "Get teammate details by ID"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add get-specific arguments."""
        parser.add_argument("mate_id", help="Teammate ID to retrieve")

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        """Execute teammate get."""
        if not client:
            print("❌ Authentication required for teammate management")
            show_auth_guidance()
            return 1

        from ..mates import MateCLI

        mate_cli = MateCLI(client)
        try:
            mate_id = args.mate_id
            mate_cli.get_interactive(mate_id)
            return 0
        except AuthenticationError as e:
            print(f"❌ Authentication failed: {e}")
            show_auth_guidance()
            return 1
        except (AgentError, NetworkError) as e:
            print(f"❌ Error getting teammate: {e}")
            return 1


class _SplitCommandArgsAction(Action):
    """Ensure command args are consistently tokenized.

    When users wrap the task message in quotes, argparse delivers it
    as a single string. Tokenizing here keeps downstream logic working
    with a uniform list of words regardless of quoting.
    """

    def __call__(  # type: ignore[override]
        self,
        parser: ArgumentParser,
        namespace: Namespace,
        values: Sequence[str],
        option_string: str | None = None,
    ) -> None:
        flattened: list[str] = []
        for value in values:
            if isinstance(value, str):
                flattened.extend(shlex.split(value))
            else:
                flattened.append(value)  # type: ignore[unreachable]

        existing = getattr(namespace, self.dest, None)
        if isinstance(existing, list):
            setattr(namespace, self.dest, [*existing, *flattened])
        else:
            setattr(namespace, self.dest, list(flattened))


class TaskCommand(Command):
    """Teammate task execution command."""

    name = "task"
    aliases: ClassVar[list[str]] = ["t"]
    description = "Execute a one-off task"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add task-specific arguments."""
        parser.add_argument(
            "command_args",
            nargs="+",
            action=_SplitCommandArgsAction,
            help=(
                "[mate_id] message - mate_id is optional (will auto-detect). "
                'Examples: task 7 "Do X" or task "Do X"'
            ),
        )
        parser.add_argument(
            "--output",
            choices=["verbose", "compact", "json"],
            default="verbose",
            help=("Output format: verbose (rich UI), compact (text only), json (raw events)"),
        )
        parser.add_argument(
            "--no-stream",
            action="store_true",
            help="Disable streaming (wait for complete response)",
        )
        parser.add_argument(
            "--debug",
            action="store_true",
            help="Enable debug mode with detailed logging and event traces",
        )

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        """Execute teammate task."""
        if not client:
            print("❌ Authentication required for teammate tasks")
            show_auth_guidance()
            return 1

        from ..mates import MateCLI

        mate_cli = MateCLI(client)
        try:
            # Parse flexible arguments: [mate_id] message
            # Try parsing first arg as integer mate_id
            mate_id = None
            message = None

            try:
                mate_id = int(args.command_args[0])
                if len(args.command_args) < 2:
                    print("❌ Message required when specifying mate_id")
                    print("   Usage: m8tes mate task <mate_id> <message>")
                    print('   Example: m8tes mate task 7 "Do something"')
                    return 1
                message = " ".join(args.command_args[1:])
            except (ValueError, IndexError):
                # First arg not numeric → auto-detect
                mate_id = None
                message = " ".join(args.command_args)

            if not message or not message.strip():
                print("❌ Task message cannot be empty")
                return 1

            # Get or confirm mate_id (with auto-detection)
            confirmed_mate_id = mate_cli.select_or_confirm_mate(mate_id)

            if confirmed_mate_id is None:
                return 1

            output_format = getattr(args, "output", "verbose")
            debug = getattr(args, "debug", False)

            mate_cli.task_interactive(
                message,
                str(confirmed_mate_id),
                output_format=output_format,
                debug=debug,
            )
            return 0
        except AuthenticationError as e:
            print(f"❌ Authentication failed: {e}")
            show_auth_guidance()
            return 1
        except (AgentError, NetworkError) as e:
            print(f"❌ Teammate task failed: {e}")
            return 1
        except KeyboardInterrupt:
            print("\n👋 Task cancelled.")
            return 1


class ChatCommand(Command):
    """Interactive chat command."""

    name = "chat"
    aliases: ClassVar[list[str]] = ["ch"]
    description = "Start interactive chat session"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add chat-specific arguments."""
        parser.add_argument(
            "mate_id",
            nargs="?",
            help="Teammate ID (optional, will auto-detect if not provided)",
        )
        parser.add_argument(
            "--resume",
            type=int,
            metavar="RUN_ID",
            help="Resume chat from previous run ID",
        )
        parser.add_argument(
            "--output",
            choices=["verbose", "compact", "json"],
            default="verbose",
            help=("Output format: verbose (rich UI), compact (text only), json (raw events)"),
        )

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        """Start interactive chat session."""
        if not client:
            print("❌ Authentication required for teammate chat")
            show_auth_guidance()
            return 1

        from ..mates import MateCLI

        mate_cli = MateCLI(client)
        try:
            # Parse mate_id (may be None for auto-detect)
            mate_id = None
            if args.mate_id:
                try:
                    mate_id = int(args.mate_id)
                except ValueError:
                    print(f"❌ Invalid teammate ID: {args.mate_id}")
                    return 1

            # Get or confirm mate_id (with auto-detection)
            confirmed_mate_id = mate_cli.select_or_confirm_mate(mate_id)

            if confirmed_mate_id is None:
                return 1

            resume_run_id = getattr(args, "resume", None)
            output_format = getattr(args, "output", "verbose")

            if output_format == "verbose":
                mate_cli.chat_interactive(str(confirmed_mate_id), resume_run_id=resume_run_id)
            else:
                mate_cli.chat_interactive(
                    str(confirmed_mate_id),
                    resume_run_id=resume_run_id,
                    output_format=output_format,
                )
            return 0
        except AuthenticationError as e:
            print(f"❌ Authentication failed: {e}")
            show_auth_guidance()
            return 1
        except (AgentError, NetworkError) as e:
            print(f"❌ Teammate chat failed: {e}")
            return 1
        except KeyboardInterrupt:
            print("\n👋 Chat session ended.")
            return 0


class UpdateCommand(Command):
    """Teammate update command."""

    name = "update"
    aliases: ClassVar[list[str]] = ["u"]
    description = "Update teammate configuration"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add update-specific arguments."""
        parser.add_argument("mate_id", help="Teammate ID to update")
        # Non-interactive mode flags
        parser.add_argument("--name", help="New teammate name (for non-interactive mode)")
        parser.add_argument(
            "--instructions", help="New teammate instructions (for non-interactive mode)"
        )
        parser.add_argument(
            "--non-interactive",
            action="store_true",
            help="Skip interactive prompts and use provided flags",
        )

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        """Execute teammate update."""
        if not client:
            print("❌ Authentication required for teammate management")
            show_auth_guidance()
            return 1

        from ..mates import MateCLI

        mate_cli = MateCLI(client)
        try:
            mate_id = args.mate_id

            # Check for non-interactive mode
            non_interactive = getattr(args, "non_interactive", False)
            if non_interactive:
                name = getattr(args, "name", None)
                instructions = getattr(args, "instructions", None)

                if not name and not instructions:
                    print(
                        "❌ At least one of --name or --instructions is required "
                        "for non-interactive mode"
                    )
                    return 1

                mate_cli.update_non_interactive(
                    mate_id=mate_id, name=name, instructions=instructions
                )
            else:
                # Interactive mode
                mate_cli.update_interactive(mate_id)
            return 0
        except AuthenticationError as e:
            print(f"❌ Authentication failed: {e}")
            show_auth_guidance()
            return 1
        except (AgentError, NetworkError, ValidationError) as e:
            print(f"❌ Error updating teammate: {e}")
            return 1


class EnableCommand(Command):
    """Teammate enable command."""

    name = "enable"
    aliases: ClassVar[list[str]] = ["e"]
    description = "Enable a disabled teammate"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add enable-specific arguments."""
        parser.add_argument("mate_id", help="Teammate ID to enable")

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        """Execute teammate enable."""
        if not client:
            print("❌ Authentication required for teammate management")
            show_auth_guidance()
            return 1

        from ..mates import MateCLI

        mate_cli = MateCLI(client)
        try:
            mate_id = args.mate_id
            mate_cli.enable_interactive(mate_id)
            return 0
        except AuthenticationError as e:
            print(f"❌ Authentication failed: {e}")
            show_auth_guidance()
            return 1
        except (AgentError, NetworkError, ValidationError) as e:
            print(f"❌ Error enabling teammate: {e}")
            return 1


class DisableCommand(Command):
    """Teammate disable command."""

    name = "disable"
    aliases: ClassVar[list[str]] = ["dis"]
    description = "Disable a teammate (keeps visible with flag, preserves history)"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add disable-specific arguments."""
        parser.add_argument("mate_id", help="Teammate ID to disable")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Skip confirmation prompt",
        )

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        """Execute teammate disable."""
        if not client:
            print("❌ Authentication required for teammate management")
            show_auth_guidance()
            return 1

        from ..mates import MateCLI

        mate_cli = MateCLI(client)
        try:
            mate_id = args.mate_id
            force = getattr(args, "force", False)
            mate_cli.disable_interactive(mate_id, force)
            return 0
        except AuthenticationError as e:
            print(f"❌ Authentication failed: {e}")
            show_auth_guidance()
            return 1
        except ValidationError:
            # Specific handling for validation errors (already shown in disable_interactive)
            return 1
        except (AgentError, NetworkError):
            # Network/agent errors (already shown in disable_interactive)
            return 1
        except Exception:
            # Catch-all for unexpected errors (already shown in disable_interactive)
            return 1


class ArchiveCommand(Command):
    """Teammate archive command."""

    name = "archive"
    aliases: ClassVar[list[str]] = ["a", "arc"]
    description = "Archive a teammate (hidden from listings, preserves history)"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add archive-specific arguments."""
        parser.add_argument("mate_id", help="Teammate ID to archive")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Skip confirmation prompt",
        )

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        """Execute teammate archiving."""
        if not client:
            print("❌ Authentication required for teammate management")
            show_auth_guidance()
            return 1

        from ..mates import MateCLI

        mate_cli = MateCLI(client)
        try:
            mate_id = args.mate_id
            force = getattr(args, "force", False)
            mate_cli.archive_interactive(mate_id, force)
            return 0
        except AuthenticationError as e:
            print(f"❌ Authentication failed: {e}")
            show_auth_guidance()
            return 1
        except ValidationError:
            # Specific handling for validation errors (already shown in archive_interactive)
            return 1
        except (AgentError, NetworkError):
            # Network/agent errors (already shown in archive_interactive)
            return 1
        except Exception:
            # Catch-all for unexpected errors (already shown in archive_interactive)
            return 1
