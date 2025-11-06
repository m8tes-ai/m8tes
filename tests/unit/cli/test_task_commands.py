"""
Tests for Task CLI command implementations.
"""

from argparse import ArgumentParser, Namespace
from unittest.mock import Mock, patch


class TestTaskCommands:
    """Test cases for task management commands."""

    def test_task_command_group_setup(self):
        """Test that task command group has correct subcommands."""
        from m8tes.cli.commands.task import TaskCommandGroup

        group = TaskCommandGroup()
        subcommands = group.get_subcommands()

        assert len(subcommands) == 8

        # Check subcommand types
        from m8tes.cli.commands.task import (
            ArchiveCommand,
            CreateCommand,
            DisableCommand,
            EnableCommand,
            ExecuteCommand,
            GetCommand,
            ListCommand,
            UpdateCommand,
        )

        subcommand_types = [type(cmd) for cmd in subcommands]
        assert CreateCommand in subcommand_types
        assert ListCommand in subcommand_types
        assert GetCommand in subcommand_types
        assert ExecuteCommand in subcommand_types
        assert UpdateCommand in subcommand_types
        assert EnableCommand in subcommand_types
        assert DisableCommand in subcommand_types
        assert ArchiveCommand in subcommand_types

    def test_create_command_attributes(self):
        """Test create command has correct attributes."""
        from m8tes.cli.commands.task import CreateCommand

        cmd = CreateCommand()

        assert cmd.name == "create"
        assert "c" in cmd.aliases
        assert cmd.requires_auth
        assert "Create" in cmd.description

    def test_create_command_arguments(self):
        """Test create command adds correct arguments."""
        from m8tes.cli.commands.task import CreateCommand

        cmd = CreateCommand()
        parser = ArgumentParser()

        cmd.add_arguments(parser)

        # Test with no arguments (interactive mode)
        args = parser.parse_args([])
        assert getattr(args, "mate_id", None) is None
        assert getattr(args, "name", None) is None
        assert getattr(args, "instructions", None) is None
        assert getattr(args, "non_interactive", False) is False

        # Test with all arguments (non-interactive mode)
        args = parser.parse_args(
            [
                "--mate-id",
                "123",
                "--name",
                "Test Task",
                "--instructions",
                "Do something",
                "--expected-output",
                "A report",
                "--goals",
                "Optimize performance",
                "--non-interactive",
            ]
        )
        assert args.mate_id == "123"
        assert args.name == "Test Task"
        assert args.instructions == "Do something"
        assert args.expected_output == "A report"
        assert args.goals == "Optimize performance"
        assert args.non_interactive is True

    def test_create_command_requires_client(self):
        """Test create command requires authenticated client."""
        from m8tes.cli.commands.task import CreateCommand

        cmd = CreateCommand()
        args = Namespace(mate_id="123", name="Test", instructions="Do it")

        result = cmd.execute(args, None)

        assert result == 1

    @patch("m8tes.cli.tasks.TaskCLI")
    def test_create_command_execute_interactive(self, mock_task_cli_class):
        """Test create command execution in interactive mode."""
        from m8tes.cli.commands.task import CreateCommand

        mock_task_cli = Mock()
        mock_task_cli_class.return_value = mock_task_cli
        mock_client = Mock()

        cmd = CreateCommand()
        args = Namespace(
            mate_id=None,
            name=None,
            instructions=None,
            expected_output=None,
            goals=None,
            non_interactive=False,
        )

        result = cmd.execute(args, mock_client)

        assert result == 0
        # In interactive mode, create_interactive is called with no arguments
        mock_task_cli.create_interactive.assert_called_once_with()

    @patch("m8tes.cli.tasks.TaskCLI")
    def test_create_command_execute_non_interactive(self, mock_task_cli_class):
        """Test create command execution in non-interactive mode."""
        from m8tes.cli.commands.task import CreateCommand

        mock_task_cli = Mock()
        mock_task_cli_class.return_value = mock_task_cli
        mock_client = Mock()

        cmd = CreateCommand()
        args = Namespace(
            mate_id="123",
            name="Test Task",
            instructions="Do something",
            expected_output="A report",
            goals="Optimize",
            non_interactive=True,
        )

        result = cmd.execute(args, mock_client)

        assert result == 0
        # In non-interactive mode, create_non_interactive is called with all arguments
        mock_task_cli.create_non_interactive.assert_called_once_with(
            mate_id="123",
            name="Test Task",
            instructions="Do something",
            expected_output="A report",
            goals="Optimize",
        )

    def test_list_command_attributes(self):
        """Test list command has correct attributes."""
        from m8tes.cli.commands.task import ListCommand

        cmd = ListCommand()

        assert cmd.name == "list"
        assert "ls" in cmd.aliases
        assert cmd.requires_auth
        assert "List" in cmd.description

    def test_list_command_arguments(self):
        """Test list command adds correct arguments."""
        from m8tes.cli.commands.task import ListCommand

        cmd = ListCommand()
        parser = ArgumentParser()

        cmd.add_arguments(parser)

        # Test with mate_id filter
        args = parser.parse_args(["--mate-id", "123"])
        assert args.mate_id == "123"

        # Test with status filter
        args = parser.parse_args(["--status", "pending"])
        assert args.status == "pending"

        # Test with include flags
        args = parser.parse_args(["--include-disabled", "--include-archived"])
        assert args.include_disabled
        assert args.include_archived

    @patch("m8tes.cli.tasks.TaskCLI")
    def test_list_command_execute_success(self, mock_task_cli_class):
        """Test list command execution success."""
        from m8tes.cli.commands.task import ListCommand

        mock_task_cli = Mock()
        mock_task_cli_class.return_value = mock_task_cli
        mock_client = Mock()

        cmd = ListCommand()
        args = Namespace(
            mate_id="123", status="pending", include_disabled=True, include_archived=False
        )

        result = cmd.execute(args, mock_client)

        assert result == 0
        mock_task_cli.list_interactive.assert_called_once_with(
            mate_id="123", status="pending", include_disabled=True, include_archived=False
        )

    def test_get_command_attributes(self):
        """Test get command has correct attributes."""
        from m8tes.cli.commands.task import GetCommand

        cmd = GetCommand()

        assert cmd.name == "get"
        assert "g" in cmd.aliases
        assert cmd.requires_auth
        assert "Get" in cmd.description

    def test_get_command_arguments(self):
        """Test get command adds correct arguments."""
        from m8tes.cli.commands.task import GetCommand

        cmd = GetCommand()
        parser = ArgumentParser()

        cmd.add_arguments(parser)

        # Test with task ID
        args = parser.parse_args(["42"])
        assert args.task_id == "42"

    @patch("m8tes.cli.tasks.TaskCLI")
    def test_get_command_execute_success(self, mock_task_cli_class):
        """Test get command execution success."""
        from m8tes.cli.commands.task import GetCommand

        mock_task_cli = Mock()
        mock_task_cli_class.return_value = mock_task_cli
        mock_client = Mock()

        cmd = GetCommand()
        args = Namespace(task_id="42")

        result = cmd.execute(args, mock_client)

        assert result == 0
        mock_task_cli.get_interactive.assert_called_once_with("42")

    def test_execute_command_attributes(self):
        """Test execute command has correct attributes."""
        from m8tes.cli.commands.task import ExecuteCommand

        cmd = ExecuteCommand()

        assert cmd.name == "execute"
        assert "exec" in cmd.aliases or "x" in cmd.aliases
        assert cmd.requires_auth
        assert "Execute" in cmd.description or "execute" in cmd.description.lower()

    def test_execute_command_arguments(self):
        """Test execute command adds correct arguments."""
        from m8tes.cli.commands.task import ExecuteCommand

        cmd = ExecuteCommand()
        parser = ArgumentParser()

        cmd.add_arguments(parser)

        # Test with task ID
        args = parser.parse_args(["42"])
        assert args.task_id == "42"

    @patch("m8tes.cli.tasks.TaskCLI")
    def test_execute_command_execute_success(self, mock_task_cli_class):
        """Test execute command execution success."""
        from m8tes.cli.commands.task import ExecuteCommand

        mock_task_cli = Mock()
        mock_task_cli_class.return_value = mock_task_cli
        mock_client = Mock()

        cmd = ExecuteCommand()
        args = Namespace(task_id="42")

        result = cmd.execute(args, mock_client)

        assert result == 0
        mock_task_cli.execute_interactive.assert_called_once_with("42")

    def test_update_command_attributes(self):
        """Test update command has correct attributes."""
        from m8tes.cli.commands.task import UpdateCommand

        cmd = UpdateCommand()

        assert cmd.name == "update"
        assert "u" in cmd.aliases
        assert cmd.requires_auth
        assert "Update" in cmd.description

    def test_update_command_arguments(self):
        """Test update command adds correct arguments."""
        from m8tes.cli.commands.task import UpdateCommand

        cmd = UpdateCommand()
        parser = ArgumentParser()

        cmd.add_arguments(parser)

        # Test with all update fields
        args = parser.parse_args(
            [
                "42",
                "--name",
                "New Name",
                "--instructions",
                "New instructions",
                "--expected-output",
                "New output",
                "--goals",
                "New goals",
            ]
        )
        assert args.task_id == "42"
        assert args.name == "New Name"
        assert args.instructions == "New instructions"
        assert args.expected_output == "New output"
        assert args.goals == "New goals"

    @patch("m8tes.cli.tasks.TaskCLI")
    def test_update_command_execute_success(self, mock_task_cli_class):
        """Test update command execution success."""
        from m8tes.cli.commands.task import UpdateCommand

        mock_task_cli = Mock()
        mock_task_cli_class.return_value = mock_task_cli
        mock_client = Mock()

        cmd = UpdateCommand()
        args = Namespace(
            task_id="42",
            name="New Name",
            instructions="New instructions",
            expected_output="New output",
            goals="New goals",
        )

        result = cmd.execute(args, mock_client)

        assert result == 0
        mock_task_cli.update_interactive.assert_called_once_with(
            task_id="42",
            name="New Name",
            instructions="New instructions",
            expected_output="New output",
            goals="New goals",
        )

    def test_enable_command_attributes(self):
        """Test enable command has correct attributes."""
        from m8tes.cli.commands.task import EnableCommand

        cmd = EnableCommand()

        assert cmd.name == "enable"
        assert "e" in cmd.aliases
        assert cmd.requires_auth

    @patch("m8tes.cli.tasks.TaskCLI")
    def test_enable_command_execute_success(self, mock_task_cli_class):
        """Test enable command execution success."""
        from m8tes.cli.commands.task import EnableCommand

        mock_task_cli = Mock()
        mock_task_cli_class.return_value = mock_task_cli
        mock_client = Mock()

        cmd = EnableCommand()
        args = Namespace(task_id="42")

        result = cmd.execute(args, mock_client)

        assert result == 0
        mock_task_cli.enable_interactive.assert_called_once_with("42")

    def test_disable_command_attributes(self):
        """Test disable command has correct attributes."""
        from m8tes.cli.commands.task import DisableCommand

        cmd = DisableCommand()

        assert cmd.name == "disable"
        assert "dis" in cmd.aliases
        assert cmd.requires_auth

    @patch("m8tes.cli.tasks.TaskCLI")
    def test_disable_command_execute_success(self, mock_task_cli_class):
        """Test disable command execution success."""
        from m8tes.cli.commands.task import DisableCommand

        mock_task_cli = Mock()
        mock_task_cli_class.return_value = mock_task_cli
        mock_client = Mock()

        cmd = DisableCommand()
        args = Namespace(task_id="42")

        result = cmd.execute(args, mock_client)

        assert result == 0
        mock_task_cli.disable_interactive.assert_called_once_with("42")

    def test_archive_command_attributes(self):
        """Test archive command has correct attributes."""
        from m8tes.cli.commands.task import ArchiveCommand

        cmd = ArchiveCommand()

        assert cmd.name == "archive"
        assert "arc" in cmd.aliases or "a" in cmd.aliases
        assert cmd.requires_auth

    @patch("m8tes.cli.tasks.TaskCLI")
    def test_archive_command_execute_success(self, mock_task_cli_class):
        """Test archive command execution success."""
        from m8tes.cli.commands.task import ArchiveCommand

        mock_task_cli = Mock()
        mock_task_cli_class.return_value = mock_task_cli
        mock_client = Mock()

        cmd = ArchiveCommand()
        args = Namespace(task_id="42")

        result = cmd.execute(args, mock_client)

        assert result == 0
        mock_task_cli.archive_interactive.assert_called_once_with("42")
