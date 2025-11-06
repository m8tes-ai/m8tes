"""
Google Ads integration commands for the m8tes CLI.

Provides commands for connecting, managing, and checking Google Ads integration.
"""

from argparse import ArgumentParser, Namespace
from typing import TYPE_CHECKING, ClassVar, Optional

from ...exceptions import AuthenticationError, NetworkError, OAuthError, ValidationError
from ..base import Command, CommandGroup

if TYPE_CHECKING:
    from ...client import M8tes


class GoogleCommandGroup(CommandGroup):
    """Google Ads integration command group."""

    name = "google"
    aliases: ClassVar[list[str]] = ["g"]
    description = "Manage Google Ads integration"
    requires_auth = True

    def __init__(self) -> None:
        super().__init__()
        # Register all google subcommands
        self.add_subcommand(ConnectCommand())
        self.add_subcommand(StatusCommand())
        self.add_subcommand(DisconnectCommand())


class ConnectCommand(Command):
    """Google Ads connection command."""

    name = "connect"
    aliases: ClassVar[list[str]] = ["c"]
    description = "Connect Google Ads account"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add connect-specific arguments."""
        parser.add_argument(
            "--redirect-uri",
            default="http://localhost:8080/callback",
            help="OAuth redirect URI (default: http://localhost:8080/callback)",
        )
        parser.add_argument(
            "--browser", action="store_true", help="Auto-open browser (default: True)"
        )
        parser.add_argument(
            "--no-browser", action="store_true", help="Disable automatic browser opening"
        )
        parser.add_argument(
            "--manual", action="store_true", help="Force manual OAuth flow (no local server)"
        )
        parser.add_argument(
            "--port", type=int, default=8080, help="Local server port (default: 8080)"
        )

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        """Execute Google Ads connection flow."""
        if not client:
            print("❌ Authentication required for Google integration")
            return 1

        from ..google import GoogleIntegrationCLI

        google_cli = GoogleIntegrationCLI(client)
        try:
            # Determine browser behavior
            auto_browser = not getattr(args, "no_browser", False)
            use_local_server = not getattr(args, "manual", False)

            google_cli.connect_interactive(
                redirect_uri=args.redirect_uri,
                auto_browser=auto_browser,
                use_local_server=use_local_server,
                port=args.port,
            )
            return 0
        except (AuthenticationError, NetworkError, OAuthError, ValidationError) as e:
            print(f"❌ Google connection failed: {e}")
            return 1
        except KeyboardInterrupt:
            print("\n👋 Google connection cancelled.")
            return 1


class StatusCommand(Command):
    """Google Ads status command."""

    name = "status"
    aliases: ClassVar[list[str]] = ["s"]
    description = "Check Google Ads integration status"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add status-specific arguments."""
        pass  # No additional arguments needed

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        """Show Google Ads integration status."""
        if not client:
            print("❌ Authentication required for Google integration")
            return 1

        from ..google import GoogleIntegrationCLI

        google_cli = GoogleIntegrationCLI(client)
        try:
            google_cli.show_status()
            return 0
        except (AuthenticationError, NetworkError) as e:
            print(f"❌ Error checking Google status: {e}")
            return 1


class DisconnectCommand(Command):
    """Google Ads disconnect command."""

    name = "disconnect"
    aliases: ClassVar[list[str]] = ["d"]
    description = "Remove Google Ads integration"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add disconnect-specific arguments."""
        pass  # No additional arguments needed

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        """Execute Google Ads disconnect flow."""
        if not client:
            print("❌ Authentication required for Google integration")
            return 1

        from ..google import GoogleIntegrationCLI

        google_cli = GoogleIntegrationCLI(client)
        try:
            google_cli.disconnect_interactive()
            return 0
        except (AuthenticationError, NetworkError) as e:
            print(f"❌ Google disconnect failed: {e}")
            return 1
        except KeyboardInterrupt:
            print("\n👋 Google disconnect cancelled.")
            return 1
