"""
Command registry for automatic command discovery and registration.

Provides a centralized way to register and discover CLI commands.
"""

import importlib
import inspect

from .base import Command, CommandGroup


class CommandRegistry:
    """
    Registry for CLI commands with automatic discovery capabilities.

    Commands can be registered manually or discovered automatically from modules.
    """

    def __init__(self) -> None:
        self._commands: dict[str, Command] = {}
        self._command_groups: dict[str, CommandGroup] = {}

    def register_command(self, command: Command) -> None:
        """
        Register a single command instance.

        Args:
            command: Command instance to register
        """
        if not isinstance(command, Command):
            raise TypeError(f"Expected Command instance, got {type(command)}")

        # Register by primary name and all aliases
        for name in command.get_all_names():
            if name in self._commands:
                raise ValueError(f"Command '{name}' is already registered")
            self._commands[name] = command

        # If it's a command group, also track it separately
        if isinstance(command, CommandGroup):
            self._command_groups[command.name] = command

    def register_command_class(self, command_class: type[Command]) -> None:
        """
        Register a command class by instantiating it.

        Args:
            command_class: Command class to instantiate and register
        """
        if not issubclass(command_class, Command):
            raise TypeError(f"Expected Command subclass, got {command_class}")

        command = command_class()
        self.register_command(command)

    def discover_commands_from_module(self, module_name: str) -> None:
        """
        Discover and register all Command classes from a module.

        Args:
            module_name: Full module name (e.g., 'm8tes.cli.commands.auth')
        """
        try:
            module = importlib.import_module(module_name)
        except ImportError as e:
            raise ImportError(f"Could not import module '{module_name}': {e}") from e

        # Find all Command classes in the module
        for _name, obj in inspect.getmembers(module):
            if (
                inspect.isclass(obj)
                and issubclass(obj, Command)
                and obj is not Command
                and obj is not CommandGroup
            ):
                # Skip abstract classes
                if inspect.isabstract(obj):
                    continue

                # Only register CommandGroup instances (top-level commands)
                # Individual subcommands are registered by their parent groups
                if issubclass(obj, CommandGroup):
                    self.register_command_class(obj)

    def auto_discover_commands(self, package_name: str = "m8tes.cli.commands") -> None:
        """
        Automatically discover commands from a package.

        Args:
            package_name: Package to scan for command modules
        """
        # Common command module names to try
        command_modules = [
            f"{package_name}.auth",
            f"{package_name}.meta",
            f"{package_name}.google",
            f"{package_name}.mate",
            f"{package_name}.task",
            f"{package_name}.run",
        ]

        for module_name in command_modules:
            try:
                self.discover_commands_from_module(module_name)
            except ImportError:
                # Module doesn't exist, skip it
                continue

    def get_command(self, name: str) -> Command:
        """
        Get a registered command by name or alias.

        Args:
            name: Command name or alias

        Returns:
            Command instance

        Raises:
            KeyError: If command is not found
        """
        if name not in self._commands:
            raise KeyError(f"Command '{name}' not found")
        return self._commands[name]

    def get_all_commands(self) -> dict[str, Command]:
        """Get all registered commands."""
        return self._commands.copy()

    def get_command_groups(self) -> dict[str, CommandGroup]:
        """Get all registered command groups."""
        return self._command_groups.copy()

    def get_primary_commands(self) -> list[Command]:
        """
        Get list of commands by their primary names (excludes aliases).

        Returns:
            List of unique command instances
        """
        seen_commands = set()
        primary_commands = []

        for name, command in self._commands.items():
            if command not in seen_commands and name == command.name:
                seen_commands.add(command)
                primary_commands.append(command)

        return primary_commands

    def has_command(self, name: str) -> bool:
        """Check if a command is registered."""
        return name in self._commands

    def clear(self) -> None:
        """Clear all registered commands."""
        self._commands.clear()
        self._command_groups.clear()


# Global command registry instance
registry = CommandRegistry()
