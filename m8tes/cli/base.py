"""
Base classes and interfaces for CLI commands.

Provides the foundation for a scalable, plugin-based CLI architecture.
"""

from abc import ABC, abstractmethod
from argparse import ArgumentParser, Namespace
from typing import TYPE_CHECKING, ClassVar, Optional

if TYPE_CHECKING:
    from ..client import M8tes


class Command(ABC):
    """
    Abstract base class for CLI commands.

    All CLI commands should inherit from this class to ensure consistent
    interface and enable automatic discovery by the command registry.
    """

    # Command metadata - must be defined by subclasses
    name: str = ""
    aliases: ClassVar[list[str]] = []
    description: str = ""

    # Whether this command requires an authenticated client
    requires_auth: bool = True

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Validate that required attributes are defined."""
        super().__init_subclass__(**kwargs)
        # Skip validation for CommandGroup base class
        if cls.__name__ == "CommandGroup":
            return
        if not cls.name:
            raise ValueError(f"Command class {cls.__name__} must define a 'name' attribute")
        if not cls.description:
            raise ValueError(f"Command class {cls.__name__} must define a 'description' attribute")

    @abstractmethod
    def add_arguments(self, parser: ArgumentParser) -> None:
        """
        Add command-specific arguments to the argument parser.

        Args:
            parser: The argparse subparser for this command
        """
        pass

    @abstractmethod
    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        """
        Execute the command with the given arguments.

        Args:
            args: Parsed command arguments
            client: M8tes client instance (may be None for auth commands)

        Returns:
            Exit code (0 for success, non-zero for error)
        """
        pass

    def get_all_names(self) -> list[str]:
        """Get all names (primary + aliases) for this command."""
        return [self.name, *self.aliases]


class CommandGroup(Command):
    """
    Base class for command groups that contain subcommands.

    Examples: auth (login, logout, status), google (connect, status, disconnect)
    """

    # Set default values to avoid validation errors for abstract base
    name: str = ""
    aliases: ClassVar[list[str]] = []
    description: str = ""

    def __init__(self) -> None:
        self.subcommands: list[Command] = []

    def add_subcommand(self, command: Command) -> None:
        """Add a subcommand to this group."""
        self.subcommands.append(command)

    def get_subcommands(self) -> list[Command]:
        """Get all subcommands in this group."""
        return self.subcommands.copy()

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add subparser for all subcommands."""
        if not self.subcommands:
            return

        subparsers = parser.add_subparsers(
            dest=f"{self.name}_command", help=f"{self.description} commands"
        )

        for command in self.subcommands:
            # Create subparser with primary name and aliases
            subparser = subparsers.add_parser(
                command.name, aliases=command.aliases, help=command.description
            )
            command.add_arguments(subparser)

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        """Execute the appropriate subcommand based on parsed arguments."""
        subcommand_name = getattr(args, f"{self.name}_command", None)
        if not subcommand_name:
            # No subcommand specified, print help
            print(f"Error: No subcommand specified for '{self.name}'")
            print(f"Available subcommands: {', '.join(cmd.name for cmd in self.subcommands)}")
            return 1

        # Find the matching subcommand
        for command in self.subcommands:
            if subcommand_name in command.get_all_names():
                return command.execute(args, client)

        print(f"Error: Unknown subcommand '{subcommand_name}' for '{self.name}'")
        return 1
