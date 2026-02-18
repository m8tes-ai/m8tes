"""
Tests for CLI command implementations.
"""

from argparse import ArgumentParser, Namespace
from unittest.mock import Mock, patch

from m8tes.cli.commands.auth import (
    AuthCommandGroup,
    LoginCommand,
    LogoutCommand,
    RegisterCommand,
    StatusCommand,
)
from m8tes.cli.commands.google import (
    ConnectCommand,
    DisconnectCommand,
    GoogleCommandGroup,
    StatusCommand as GoogleStatusCommand,
)
from m8tes.cli.commands.mate import (
    ArchiveCommand,
    ChatCommand,
    CreateCommand,
    DisableCommand,
    EnableCommand,
    GetCommand,
    ListCommand,
    MateCommandGroup,
    TaskCommand,
    UpdateCommand,
)
from m8tes.cli.commands.meta import (
    ConnectCommand as MetaConnectCommand,
    DisconnectCommand as MetaDisconnectCommand,
    MetaCommandGroup,
    StatusCommand as MetaStatusCommand,
)


class TestAuthCommands:
    """Test cases for authentication commands."""

    def test_auth_command_group_setup(self):
        """Test that auth command group has correct subcommands."""
        group = AuthCommandGroup()
        subcommands = group.get_subcommands()

        assert len(subcommands) == 4

        # Check subcommand types
        subcommand_types = [type(cmd) for cmd in subcommands]
        assert RegisterCommand in subcommand_types
        assert LoginCommand in subcommand_types
        assert StatusCommand in subcommand_types
        assert LogoutCommand in subcommand_types

    def test_register_command_attributes(self):
        """Test register command has correct attributes."""
        cmd = RegisterCommand()

        assert cmd.name == "register"
        assert "r" in cmd.aliases
        assert not cmd.requires_auth
        assert "Register" in cmd.description

    def test_login_command_arguments(self):
        """Test login command adds correct arguments."""
        cmd = LoginCommand()
        parser = ArgumentParser()

        cmd.add_arguments(parser)

        # Parse with --no-save flag
        args = parser.parse_args(["--no-save"])
        assert args.no_save

        # Parse without flag
        args = parser.parse_args([])
        assert not args.no_save

    @patch("m8tes.cli.auth.AuthCLI")
    def test_register_command_execute_success(self, mock_auth_cli_class):
        """Test register command execution success."""
        mock_auth_cli = Mock()
        mock_auth_cli_class.return_value = mock_auth_cli

        cmd = RegisterCommand()
        args = Namespace()

        result = cmd.execute(args, None)

        assert result == 0
        mock_auth_cli.register_interactive.assert_called_once()

    @patch("m8tes.cli.auth.AuthCLI")
    def test_register_command_execute_keyboard_interrupt(self, mock_auth_cli_class):
        """Test register command handles keyboard interrupt."""
        mock_auth_cli = Mock()
        mock_auth_cli.register_interactive.side_effect = KeyboardInterrupt()
        mock_auth_cli_class.return_value = mock_auth_cli

        cmd = RegisterCommand()
        args = Namespace()

        result = cmd.execute(args, None)

        assert result == 1

    @patch("m8tes.cli.auth.prompt")
    @patch("m8tes.cli.auth.prompt_email")
    @patch("m8tes.cli.auth.prompt_password_confirm")
    def test_register_requires_first_name_prompt(self, mock_password, mock_email, mock_prompt):
        """Test that registration collects first name once without last name prompt."""
        from m8tes.cli.auth import AuthCLI
        from m8tes.client import M8tes

        # Setup mocks
        mock_email.return_value = "test@example.com"
        mock_password.return_value = "password123"
        mock_prompt.side_effect = ["John"]

        # Create mock client
        mock_client = Mock(spec=M8tes)
        mock_client.register_user.return_value = {
            "user": {"id": 1, "email": "test@example.com"},
            "api_key": "test-api-key",
        }

        auth_cli = AuthCLI(mock_client, base_url="http://test")

        # Mock get_current_account_info to return None (no existing credentials)
        auth_cli.get_current_account_info = Mock(return_value=None)

        auth_cli.register_interactive()

        # Verify register_user was called with first_name only
        mock_client.register_user.assert_called_once()
        call_args = mock_client.register_user.call_args
        assert call_args.kwargs.get("first_name") == "John"
        assert call_args.kwargs.get("email") == "test@example.com"

        # Verify prompt was called only once for first_name
        assert mock_prompt.call_count == 1

    @patch("m8tes.cli.auth.AuthCLI")
    def test_login_command_execute_with_no_save(self, mock_auth_cli_class):
        """Test login command with --no-save flag."""
        mock_auth_cli = Mock()
        mock_auth_cli_class.return_value = mock_auth_cli

        cmd = LoginCommand()
        args = Namespace(no_save=True)

        result = cmd.execute(args, None)

        assert result == 0
        mock_auth_cli.login_interactive.assert_called_once_with(save_token=False)


class TestGoogleCommands:
    """Test cases for Google integration commands."""

    def test_google_command_group_setup(self):
        """Test that google command group has correct subcommands."""
        group = GoogleCommandGroup()
        subcommands = group.get_subcommands()

        assert len(subcommands) == 3

        # Check subcommand types
        subcommand_types = [type(cmd) for cmd in subcommands]
        assert ConnectCommand in subcommand_types
        assert GoogleStatusCommand in subcommand_types
        assert DisconnectCommand in subcommand_types

    def test_connect_command_attributes(self):
        """Test connect command has correct attributes."""
        cmd = ConnectCommand()

        assert cmd.name == "connect"
        assert "c" in cmd.aliases
        assert cmd.requires_auth
        assert "Connect" in cmd.description

    def test_connect_command_arguments(self):
        """Test connect command adds correct arguments."""
        cmd = ConnectCommand()
        parser = ArgumentParser()

        cmd.add_arguments(parser)

        # Test default arguments
        args = parser.parse_args([])
        assert args.redirect_uri == "http://localhost:8080/callback"
        assert args.port == 8080
        assert not args.browser
        assert not args.no_browser
        assert not args.manual

        # Test with custom arguments
        args = parser.parse_args(
            [
                "--redirect-uri",
                "http://example.com/callback",
                "--port",
                "9000",
                "--no-browser",
                "--manual",
            ]
        )
        assert args.redirect_uri == "http://example.com/callback"
        assert args.port == 9000
        assert args.no_browser
        assert args.manual

    def test_connect_command_requires_client(self):
        """Test connect command requires authenticated client."""
        cmd = ConnectCommand()
        args = Namespace()

        result = cmd.execute(args, None)

        assert result == 1

    @patch("m8tes.cli.google.GoogleIntegrationCLI")
    def test_connect_command_execute_success(self, mock_google_cli_class):
        """Test connect command execution success."""
        mock_google_cli = Mock()
        mock_google_cli_class.return_value = mock_google_cli
        mock_client = Mock()

        cmd = ConnectCommand()
        args = Namespace(
            redirect_uri="http://localhost:8080/callback", no_browser=False, manual=False, port=8080
        )

        result = cmd.execute(args, mock_client)

        assert result == 0
        mock_google_cli.connect_interactive.assert_called_once_with(
            redirect_uri="http://localhost:8080/callback",
            auto_browser=True,  # not no_browser
            use_local_server=True,  # not manual
            port=8080,
        )


class TestMetaCommands:
    """Test cases for Meta Ads integration commands."""

    def test_meta_command_group_setup(self):
        """Meta command group wiring should include connect/status/disconnect."""
        group = MetaCommandGroup()
        subcommands = group.get_subcommands()

        assert len(subcommands) == 3

        subcommand_types = [type(cmd) for cmd in subcommands]
        assert MetaConnectCommand in subcommand_types
        assert MetaStatusCommand in subcommand_types
        assert MetaDisconnectCommand in subcommand_types

    def test_meta_connect_command_attributes(self):
        """Meta connect command mirrors Google command contract."""
        cmd = MetaConnectCommand()

        assert cmd.name == "connect"
        assert "c" in cmd.aliases
        assert cmd.requires_auth
        assert "Connect" in cmd.description

    def test_meta_connect_command_arguments(self):
        """Connect command should expose redirect-uri and browser flags."""
        cmd = MetaConnectCommand()
        parser = ArgumentParser()

        cmd.add_arguments(parser)

        args = parser.parse_args([])
        assert args.redirect_uri == "https://localhost:8080/callback"
        assert not args.no_browser

        args = parser.parse_args(
            [
                "--redirect-uri",
                "https://app.m8tes.ai/oauth",
                "--no-browser",
            ]
        )
        assert args.redirect_uri == "https://app.m8tes.ai/oauth"
        assert args.no_browser

    def test_meta_connect_command_requires_client(self):
        """Authenticated client is mandatory for meta connect."""
        cmd = MetaConnectCommand()
        args = Namespace()

        result = cmd.execute(args, None)

        assert result == 1

    @patch("m8tes.cli.meta.MetaIntegrationCLI")
    def test_meta_connect_command_execute_success(self, mock_meta_cli_class):
        """Ensure command delegates to interactive CLI with expected args."""
        mock_meta_cli = Mock()
        mock_meta_cli_class.return_value = mock_meta_cli
        mock_client = Mock()

        cmd = MetaConnectCommand()
        args = Namespace(
            redirect_uri="https://localhost:8080/callback",
            no_browser=False,
        )

        result = cmd.execute(args, mock_client)

        assert result == 0
        mock_meta_cli.connect_interactive.assert_called_once_with(
            redirect_uri="https://localhost:8080/callback",
            auto_browser=True,
        )

    @patch("m8tes.cli.meta.MetaIntegrationCLI")
    def test_meta_status_command_execute_success(self, mock_meta_cli_class):
        """Status command should invoke CLI status helper."""
        mock_meta_cli = Mock()
        mock_meta_cli_class.return_value = mock_meta_cli
        mock_client = Mock()

        cmd = MetaStatusCommand()
        args = Namespace()

        result = cmd.execute(args, mock_client)

        assert result == 0
        mock_meta_cli.show_status.assert_called_once_with()

    @patch("m8tes.cli.meta.MetaIntegrationCLI")
    def test_meta_disconnect_command_execute_success(self, mock_meta_cli_class):
        """Disconnect command should trigger CLI helper."""
        mock_meta_cli = Mock()
        mock_meta_cli_class.return_value = mock_meta_cli
        mock_client = Mock()

        cmd = MetaDisconnectCommand()
        args = Namespace()

        result = cmd.execute(args, mock_client)

        assert result == 0
        mock_meta_cli.disconnect_interactive.assert_called_once_with()


class TestMateCommands:
    """Test cases for teammate management commands."""

    def test_mate_command_group_setup(self):
        """Test that teammate command group has correct subcommands."""
        group = MateCommandGroup()
        subcommands = group.get_subcommands()

        assert len(subcommands) == 9

        # Check subcommand types
        subcommand_types = [type(cmd) for cmd in subcommands]
        assert CreateCommand in subcommand_types
        assert ListCommand in subcommand_types
        assert GetCommand in subcommand_types
        assert TaskCommand in subcommand_types
        assert ChatCommand in subcommand_types
        assert UpdateCommand in subcommand_types
        assert ArchiveCommand in subcommand_types
        assert EnableCommand in subcommand_types
        assert DisableCommand in subcommand_types

    def test_create_command_attributes(self):
        """Test create command has correct attributes."""
        cmd = CreateCommand()

        assert cmd.name == "create"
        assert "c" in cmd.aliases
        assert cmd.requires_auth
        assert "Create" in cmd.description

    def test_get_command_arguments(self):
        """Test get command adds correct arguments."""
        cmd = GetCommand()
        parser = ArgumentParser()

        cmd.add_arguments(parser)

        # Test with mate ID
        args = parser.parse_args(["mate-123"])
        assert args.mate_id == "mate-123"

    def test_create_command_requires_client(self):
        """Test create command requires authenticated client."""
        cmd = CreateCommand()
        args = Namespace()

        result = cmd.execute(args, None)

        assert result == 1

    @patch("m8tes.cli.mates.MateCLI")
    def test_create_command_execute_success(self, mock_mate_cli_class):
        """Test create command execution success."""
        mock_mate_cli = Mock()
        mock_mate_cli_class.return_value = mock_mate_cli
        mock_client = Mock()

        cmd = CreateCommand()
        args = Namespace()

        result = cmd.execute(args, mock_client)

        assert result == 0
        mock_mate_cli.create_interactive.assert_called_once()

    @patch("m8tes.cli.mates.confirm_prompt", return_value=True)
    @patch("m8tes.cli.mates.prompt")
    @patch("builtins.input")
    def test_mate_creation_role_before_name_order(self, mock_input, mock_prompt, mock_confirm):
        """Test that mate creation prompts for role before name."""
        from m8tes.cli.mates import MateCLI

        # Setup input mocks for multi-line instructions and goals
        mock_input.side_effect = [
            "Optimize campaigns",  # instructions line 1
            "",  # instructions end (first empty line)
            "",  # instructions end confirmation (double enter)
            "",  # goals multi-line end
        ]

        # Setup prompt mocks - role first, then name
        mock_prompt.side_effect = [
            "Campaign Optimizer",  # role (asked first)
            "CampaignMate",  # name (asked second)
            "",  # tools selection (empty)
            "",  # goals (empty)
        ]

        # Create mock client and instance
        mock_client = Mock()
        mock_instance = Mock()
        mock_instance.id = 123
        mock_instance.name = "CampaignMate"
        mock_instance.role = "Campaign Optimizer"
        mock_instance.tools = []
        mock_instance.goals = None
        mock_client.instances = Mock()
        mock_client.instances.create = Mock(return_value=mock_instance)

        mate_cli = MateCLI(mock_client)
        mate_cli.create_interactive()

        # Verify prompt call order: role comes before name
        assert mock_prompt.call_count >= 2
        prompt_calls = [str(call) for call in mock_prompt.call_args_list]

        # First call should be for role
        assert "role" in prompt_calls[0].lower() or "teammate role" in prompt_calls[0].lower()
        # Second call should be for name
        assert "name" in prompt_calls[1].lower() and "teammate name" in prompt_calls[1].lower()

        # Verify instance was created with correct data
        mock_client.instances.create.assert_called_once()
        call_kwargs = mock_client.instances.create.call_args.kwargs
        assert call_kwargs["name"] == "CampaignMate"
        assert call_kwargs["role"] == "Campaign Optimizer"

    @patch("m8tes.cli.mates.MateCLI")
    def test_get_command_execute_with_mate_id(self, mock_mate_cli_class):
        """Test get command execution with teammate ID."""
        mock_mate_cli = Mock()
        mock_mate_cli_class.return_value = mock_mate_cli
        mock_client = Mock()

        cmd = GetCommand()
        args = Namespace(mate_id="mate-123")

        result = cmd.execute(args, mock_client)

        assert result == 0
        mock_mate_cli.get_interactive.assert_called_once_with("mate-123")

    def test_task_command_attributes(self):
        """Test task command has correct attributes."""
        cmd = TaskCommand()

        assert cmd.name == "task"
        assert "t" in cmd.aliases
        assert cmd.requires_auth
        assert "task" in cmd.description.lower()

    def test_task_command_arguments(self):
        """Test task command adds correct arguments."""
        cmd = TaskCommand()
        parser = ArgumentParser()

        cmd.add_arguments(parser)

        # Test with mate_id and message
        args = parser.parse_args(["mate-123", "Run analysis on campaign"])
        assert args.command_args == ["mate-123", "Run", "analysis", "on", "campaign"]
        assert args.output == "verbose"
        assert args.debug is False

    @patch("m8tes.cli.mates.MateCLI")
    def test_task_command_execute_success(self, mock_mate_cli_class):
        """Test task command execution success."""
        mock_mate_cli = Mock()
        mock_mate_cli.select_or_confirm_mate = Mock(return_value=123)
        mock_mate_cli_class.return_value = mock_mate_cli
        mock_client = Mock()

        cmd = TaskCommand()
        args = Namespace(command_args=["123", "Run", "analysis"], output="verbose", debug=False)

        result = cmd.execute(args, mock_client)

        assert result == 0
        mock_mate_cli.task_interactive.assert_called_once_with(
            "Run analysis", "123", output_format="verbose", debug=False
        )

    def test_chat_command_attributes(self):
        """Test chat command has correct attributes."""
        cmd = ChatCommand()

        assert cmd.name == "chat"
        assert "ch" in cmd.aliases
        assert cmd.requires_auth
        assert "chat" in cmd.description.lower()

    @patch("m8tes.cli.mates.MateCLI")
    def test_chat_command_execute_success(self, mock_mate_cli_class):
        """Test chat command execution success."""
        mock_mate_cli = Mock()
        mock_mate_cli.select_or_confirm_mate = Mock(return_value=123)
        mock_mate_cli_class.return_value = mock_mate_cli
        mock_client = Mock()

        cmd = ChatCommand()
        args = Namespace(mate_id="123", resume=None, output="verbose")

        result = cmd.execute(args, mock_client)

        assert result == 0
        mock_mate_cli.chat_interactive.assert_called_once_with("123", resume_run_id=None)


class TestRunCommands:
    """Test cases for run management commands."""

    def test_run_command_group_setup(self):
        """Test that run command group has correct subcommands."""
        from m8tes.cli.commands.run import RunCommandGroup

        group = RunCommandGroup()
        subcommands = group.get_subcommands()

        assert len(subcommands) == 6

    def test_run_command_group_attributes(self):
        """Test run command group has correct attributes."""
        from m8tes.cli.commands.run import RunCommandGroup

        group = RunCommandGroup()
        assert group.name == "run"
        assert "r" in group.aliases
        assert group.requires_auth
        assert "run" in group.description.lower()
        # Must not contain "agent" in description
        assert "agent" not in group.description.lower()

    def test_get_run_command_attributes(self):
        """Test get run command has correct attributes."""
        from m8tes.cli.commands.run import GetRunCommand

        cmd = GetRunCommand()
        assert cmd.name == "get"
        assert "g" in cmd.aliases
        assert cmd.requires_auth

    def test_get_run_command_arguments(self):
        """Test get run command adds correct arguments."""
        from m8tes.cli.commands.run import GetRunCommand

        cmd = GetRunCommand()
        parser = ArgumentParser()
        cmd.add_arguments(parser)

        args = parser.parse_args(["123"])
        assert args.run_id == "123"

    def test_list_runs_command_attributes(self):
        """Test list runs command has correct attributes."""
        from m8tes.cli.commands.run import ListRunsCommand

        cmd = ListRunsCommand()
        assert cmd.name == "list"
        assert "ls" in cmd.aliases
        assert cmd.requires_auth

    def test_list_runs_command_arguments(self):
        """Test list runs command adds correct arguments."""
        from m8tes.cli.commands.run import ListRunsCommand

        cmd = ListRunsCommand()
        parser = ArgumentParser()
        cmd.add_arguments(parser)

        args = parser.parse_args(["--limit", "25"])
        assert args.limit == 25

    def test_list_teammate_runs_command_attributes(self):
        """Test list teammate runs command uses 'teammate' not 'agent' terminology."""
        from m8tes.cli.commands.run import ListTeammateRunsCommand

        cmd = ListTeammateRunsCommand()
        assert cmd.name == "list-mate"
        assert "lm" in cmd.aliases
        assert cmd.requires_auth
        assert "teammate" in cmd.description.lower()
        assert "agent" not in cmd.description.lower()

    def test_list_teammate_runs_command_arguments(self):
        """Test list teammate runs command uses mate_id parameter."""
        from m8tes.cli.commands.run import ListTeammateRunsCommand

        cmd = ListTeammateRunsCommand()
        parser = ArgumentParser()
        cmd.add_arguments(parser)

        args = parser.parse_args(["7", "--limit", "5"])
        assert args.mate_id == "7"
        assert args.limit == 5

    def test_list_teammate_runs_requires_client(self):
        """Test list teammate runs command requires authenticated client."""
        from m8tes.cli.commands.run import ListTeammateRunsCommand

        cmd = ListTeammateRunsCommand()
        args = Namespace(mate_id="7", limit=10)

        result = cmd.execute(args, None)
        assert result == 1

    def test_conversation_command_attributes(self):
        """Test conversation command has correct attributes."""
        from m8tes.cli.commands.run import ConversationCommand

        cmd = ConversationCommand()
        assert cmd.name == "conversation"
        assert "conv" in cmd.aliases
        assert cmd.requires_auth

    def test_usage_command_attributes(self):
        """Test usage command has correct attributes."""
        from m8tes.cli.commands.run import UsageCommand

        cmd = UsageCommand()
        assert cmd.name == "usage"
        assert "cost" in cmd.aliases
        assert cmd.requires_auth

    def test_tools_command_attributes(self):
        """Test tools command has correct attributes."""
        from m8tes.cli.commands.run import ToolsCommand

        cmd = ToolsCommand()
        assert cmd.name == "tools"
        assert "executions" in cmd.aliases
        assert cmd.requires_auth
