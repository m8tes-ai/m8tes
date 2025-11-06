"""
Tests for CLI command registry functionality.
"""

from argparse import ArgumentParser, Namespace
from typing import TYPE_CHECKING, ClassVar, Optional

import pytest

from m8tes.cli.base import Command, CommandGroup
from m8tes.cli.registry import CommandRegistry

if TYPE_CHECKING:
    from m8tes.client import M8tes


class MockCommand(Command):
    """Mock command for testing."""

    name = "test"
    aliases: ClassVar[list[str]] = ["t"]
    description = "Test command"
    requires_auth = False

    def __init__(self):
        self.executed = False
        self.execution_args = None
        self.execution_client = None

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--test-flag", action="store_true", help="Test flag")

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        self.executed = True
        self.execution_args = args
        self.execution_client = client
        return 0


class MockSubCommand(Command):
    """Mock subcommand for testing."""

    name = "sub"
    aliases: ClassVar[list[str]] = ["s"]
    description = "Test subcommand"
    requires_auth = True

    def __init__(self):
        self.executed = False

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--sub-flag", action="store_true", help="Sub flag")

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        self.executed = True
        return 0


class MockCommandGroup(CommandGroup):
    """Mock command group for testing."""

    name = "group"
    aliases: ClassVar[list[str]] = ["g"]
    description = "Test command group"
    requires_auth = False

    def __init__(self):
        super().__init__()
        self.add_subcommand(MockSubCommand())


class TestCommandRegistry:
    """Test cases for CommandRegistry."""

    def test_register_command(self):
        """Test registering a single command."""
        registry = CommandRegistry()
        command = MockCommand()

        registry.register_command(command)

        # Should be registered by both name and alias
        assert registry.has_command("test")
        assert registry.has_command("t")
        assert registry.get_command("test") is command
        assert registry.get_command("t") is command

    def test_register_command_duplicate_name(self):
        """Test that registering duplicate command names raises error."""
        registry = CommandRegistry()
        command1 = MockCommand()
        command2 = MockCommand()

        registry.register_command(command1)

        with pytest.raises(ValueError, match="Command 'test' is already registered"):
            registry.register_command(command2)

    def test_register_command_class(self):
        """Test registering a command class."""
        registry = CommandRegistry()

        registry.register_command_class(MockCommand)

        assert registry.has_command("test")
        assert isinstance(registry.get_command("test"), MockCommand)

    def test_register_command_group(self):
        """Test registering a command group with subcommands."""
        registry = CommandRegistry()
        group = MockCommandGroup()

        registry.register_command(group)

        # Group should be registered
        assert registry.has_command("group")
        assert registry.has_command("g")

        # Should be tracked as a command group
        command_groups = registry.get_command_groups()
        assert "group" in command_groups
        assert command_groups["group"] is group

    def test_get_command_not_found(self):
        """Test getting non-existent command raises KeyError."""
        registry = CommandRegistry()

        with pytest.raises(KeyError, match="Command 'nonexistent' not found"):
            registry.get_command("nonexistent")

    def test_get_primary_commands(self):
        """Test getting primary commands (excludes aliases)."""
        registry = CommandRegistry()
        command = MockCommand()
        registry.register_command(command)

        primary_commands = registry.get_primary_commands()

        # Should only include the command once, not for each alias
        assert len(primary_commands) == 1
        assert primary_commands[0] is command

    def test_clear_registry(self):
        """Test clearing the registry."""
        registry = CommandRegistry()
        command = MockCommand()
        registry.register_command(command)

        assert registry.has_command("test")

        registry.clear()

        assert not registry.has_command("test")
        assert len(registry.get_all_commands()) == 0
        assert len(registry.get_command_groups()) == 0


class TestCommand:
    """Test cases for Command base class."""

    def test_command_validation(self):
        """Test that Command subclasses must define required attributes."""

        with pytest.raises(ValueError, match="must define a 'name' attribute"):

            class InvalidCommand1(Command):
                description = "Test"

                def add_arguments(self, parser):
                    pass

                def execute(self, args, client=None):
                    return 0

        with pytest.raises(ValueError, match="must define a 'description' attribute"):

            class InvalidCommand2(Command):
                name = "test"

                def add_arguments(self, parser):
                    pass

                def execute(self, args, client=None):
                    return 0

    def test_get_all_names(self):
        """Test getting all names for a command."""
        command = MockCommand()
        names = command.get_all_names()

        assert names == ["test", "t"]


class TestCommandGroup:
    """Test cases for CommandGroup base class."""

    def test_add_subcommand(self):
        """Test adding subcommands to a group."""
        group = MockCommandGroup()
        subcommands = group.get_subcommands()

        # Should have one subcommand added in __init__
        assert len(subcommands) == 1
        assert isinstance(subcommands[0], MockSubCommand)

    def test_execute_subcommand(self):
        """Test executing a subcommand through the group."""
        group = MockCommandGroup()

        # Mock args for the subcommand
        args = Namespace()
        args.group_command = "sub"

        result = group.execute(args, None)

        assert result == 0
        # The subcommand should have been executed
        subcommand = group.get_subcommands()[0]
        assert subcommand.executed

    def test_execute_no_subcommand(self):
        """Test executing group without specifying subcommand."""
        group = MockCommandGroup()

        # Args without subcommand
        args = Namespace()

        result = group.execute(args, None)

        assert result == 1  # Should return error code

    def test_execute_unknown_subcommand(self):
        """Test executing group with unknown subcommand."""
        group = MockCommandGroup()

        # Args with unknown subcommand
        args = Namespace()
        args.group_command = "unknown"

        result = group.execute(args, None)

        assert result == 1  # Should return error code
