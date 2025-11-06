"""
Authentication commands for the m8tes CLI.

Provides user registration, login, logout, and status commands.
"""

from argparse import ArgumentParser, Namespace
from typing import TYPE_CHECKING, ClassVar, Optional

from ...exceptions import AuthenticationError, NetworkError, ValidationError
from ..base import Command, CommandGroup

if TYPE_CHECKING:
    from ...client import M8tes


class AuthCommandGroup(CommandGroup):
    """Authentication command group."""

    name = "auth"
    aliases: ClassVar[list[str]] = ["a"]
    description = "Manage authentication"
    requires_auth = False

    def __init__(self) -> None:
        super().__init__()
        # Register all auth subcommands
        self.add_subcommand(RegisterCommand())
        self.add_subcommand(LoginCommand())
        self.add_subcommand(StatusCommand())
        self.add_subcommand(LogoutCommand())


class RegisterCommand(Command):
    """User registration command."""

    name = "register"
    aliases: ClassVar[list[str]] = ["r"]
    description = "Register new user account"
    requires_auth = False

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add register-specific arguments."""
        pass  # No additional arguments needed

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        """Execute user registration flow."""
        from ..auth import AuthCLI

        base_url = getattr(args, "base_url", None)
        if getattr(args, "dev", False) and not base_url:
            base_url = "http://127.0.0.1:8000"

        auth_cli = AuthCLI(client, base_url)
        try:
            auth_cli.register_interactive()
            return 0
        except (AuthenticationError, NetworkError, ValidationError) as e:
            print(f"❌ Registration failed: {e}")
            return 1
        except KeyboardInterrupt:
            print("\n👋 Registration cancelled.")
            return 1


class LoginCommand(Command):
    """User login command."""

    name = "login"
    aliases: ClassVar[list[str]] = ["l"]
    description = "Login and save credentials"
    requires_auth = False

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add login-specific arguments."""
        parser.add_argument(
            "--no-save", action="store_true", help="Don't save credentials to config file"
        )

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        """Execute user login flow."""
        from ..auth import AuthCLI

        base_url = getattr(args, "base_url", None)
        if getattr(args, "dev", False) and not base_url:
            base_url = "http://127.0.0.1:8000"

        auth_cli = AuthCLI(client, base_url)
        try:
            save_token = not getattr(args, "no_save", False)
            auth_cli.login_interactive(save_token=save_token)
            return 0
        except (AuthenticationError, NetworkError, ValidationError) as e:
            print(f"❌ Login failed: {e}")
            return 1
        except KeyboardInterrupt:
            print("\n👋 Login cancelled.")
            return 1


class StatusCommand(Command):
    """Authentication status command."""

    name = "status"
    aliases: ClassVar[list[str]] = ["s"]
    description = "Check authentication status"
    requires_auth = False  # Can work without auth to show current state

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add status-specific arguments."""
        pass  # No additional arguments needed

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        """Show current authentication status."""
        from ..auth import AuthCLI

        base_url = getattr(args, "base_url", None)
        if getattr(args, "dev", False) and not base_url:
            base_url = "http://127.0.0.1:8000"

        auth_cli = AuthCLI(client, base_url)
        try:
            auth_cli.show_status()
            return 0
        except Exception as e:
            print(f"❌ Error checking status: {e}")
            return 1


class LogoutCommand(Command):
    """User logout command."""

    name = "logout"
    aliases: ClassVar[list[str]] = ["o"]
    description = "Logout and clear saved credentials"
    requires_auth = False  # Can work without auth to clear saved credentials

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add logout-specific arguments."""
        pass  # No additional arguments needed

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        """Execute user logout flow."""
        from ..auth import AuthCLI

        base_url = getattr(args, "base_url", None)
        if getattr(args, "dev", False) and not base_url:
            base_url = "http://127.0.0.1:8000"

        auth_cli = AuthCLI(client, base_url)
        try:
            auth_cli.logout_interactive()
            return 0
        except Exception as e:
            print(f"❌ Logout failed: {e}")
            return 1
