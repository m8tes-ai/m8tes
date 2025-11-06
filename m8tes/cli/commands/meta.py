"""Meta Ads integration commands for the m8tes CLI."""

from __future__ import annotations

from argparse import ArgumentParser, Namespace
from typing import TYPE_CHECKING, ClassVar

from ...exceptions import AuthenticationError, NetworkError, OAuthError, ValidationError
from ..base import Command, CommandGroup

if TYPE_CHECKING:
    from ...client import M8tes


class MetaCommandGroup(CommandGroup):
    """Meta Ads integration command group."""

    name = "meta"
    aliases: ClassVar[list[str]] = ["facebook"]
    description = "Manage Meta Ads integration"
    requires_auth = True

    def __init__(self) -> None:
        super().__init__()
        self.add_subcommand(ConnectCommand())
        self.add_subcommand(StatusCommand())
        self.add_subcommand(DisconnectCommand())


class ConnectCommand(Command):
    """Connect Meta Ads account."""

    name = "connect"
    aliases: ClassVar[list[str]] = ["c"]
    description = "Connect Meta Ads account"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add connect arguments."""
        parser.add_argument(
            "--redirect-uri",
            default="https://localhost:8080/callback",
            help="OAuth redirect URI (default: https://localhost:8080/callback)",
        )
        parser.add_argument(
            "--no-browser",
            action="store_true",
            help="Do not attempt to open the authorization URL in a browser",
        )

    def execute(self, args: Namespace, client: M8tes | None = None) -> int:
        """Execute Meta Ads connection flow."""
        if not client:
            print("❌ Authentication required for Meta integration")
            return 1

        from ..meta import MetaIntegrationCLI

        meta_cli = MetaIntegrationCLI(client)
        try:
            auto_browser = not getattr(args, "no_browser", False)
            meta_cli.connect_interactive(
                redirect_uri=args.redirect_uri,
                auto_browser=auto_browser,
            )
            return 0
        except (AuthenticationError, NetworkError, OAuthError, ValidationError) as exc:
            print(f"❌ Meta connection failed: {exc}")
            return 1
        except KeyboardInterrupt:
            print("\n👋 Meta connection cancelled.")
            return 1


class StatusCommand(Command):
    """Show Meta Ads integration status."""

    name = "status"
    aliases: ClassVar[list[str]] = ["s"]
    description = "Check Meta Ads integration status"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Status command has no additional arguments."""
        return None

    def execute(self, args: Namespace, client: M8tes | None = None) -> int:
        """Execute status command."""
        if not client:
            print("❌ Authentication required for Meta integration")
            return 1

        from ..meta import MetaIntegrationCLI

        meta_cli = MetaIntegrationCLI(client)
        try:
            meta_cli.show_status()
            return 0
        except (AuthenticationError, NetworkError) as exc:
            print(f"❌ Error checking Meta status: {exc}")
            return 1


class DisconnectCommand(Command):
    """Disconnect Meta Ads integration."""

    name = "disconnect"
    aliases: ClassVar[list[str]] = ["d"]
    description = "Disconnect Meta Ads"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Disconnect command has no additional arguments."""
        return None

    def execute(self, args: Namespace, client: M8tes | None = None) -> int:
        """Execute disconnect command."""
        if not client:
            print("❌ Authentication required for Meta integration")
            return 1

        from ..meta import MetaIntegrationCLI

        meta_cli = MetaIntegrationCLI(client)
        try:
            meta_cli.disconnect_interactive()
            return 0
        except (AuthenticationError, NetworkError, ValidationError) as exc:
            print(f"❌ Meta disconnect failed: {exc}")
            return 1
        except KeyboardInterrupt:
            print("\n👋 Meta disconnect cancelled.")
            return 1
