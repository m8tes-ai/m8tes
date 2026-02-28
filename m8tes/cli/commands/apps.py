"""Generic app connection commands backed by the v2 SDK client."""

from __future__ import annotations

from argparse import ArgumentParser, Namespace
from typing import TYPE_CHECKING, ClassVar

from ..._exceptions import M8tesError
from ..base import Command, CommandGroup
from ..util import show_auth_guidance
from ..v2 import v2_client_from_args

if TYPE_CHECKING:
    from ...client import M8tes


class AppsCommandGroup(CommandGroup):
    """App catalog and connection management commands."""

    name = "apps"
    aliases: ClassVar[list[str]] = ["app"]
    description = "List and manage app connections"
    requires_auth = True

    def __init__(self) -> None:
        super().__init__()
        self.add_subcommand(ListAppsCommand())
        self.add_subcommand(ConnectOAuthCommand())
        self.add_subcommand(ConnectApiKeyCommand())
        self.add_subcommand(ConnectCompleteCommand())
        self.add_subcommand(DisconnectCommand())


class ListAppsCommand(Command):
    """List available apps and connection state."""

    name = "list"
    aliases: ClassVar[list[str]] = ["ls"]
    description = "List available apps and connection status"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--user-id", help="Filter connection state for one end-user")

    def execute(self, args: Namespace, client: M8tes | None = None) -> int:
        if not client:
            print("❌ Authentication required for app management")
            show_auth_guidance()
            return 1

        try:
            with v2_client_from_args(args, client) as v2_client:
                page = v2_client.apps.list(user_id=getattr(args, "user_id", None))

            print("\n🔌 Apps")
            print("=" * 72)
            if not page.data:
                print("No apps available.")
                return 0

            for app in page.data:
                status = "connected" if app.connected else "not connected"
                print(f"{app.name:<24} {app.auth_type:<14} {status}")
            return 0
        except M8tesError as e:
            print(f"❌ Failed to list apps: {e}")
            return 1


class ConnectOAuthCommand(Command):
    """Start an OAuth connection flow."""

    name = "connect-oauth"
    aliases: ClassVar[list[str]] = ["oauth"]
    description = "Start an OAuth connection flow for an app"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("app_name", help="App provider name, for example gmail")
        parser.add_argument("--redirect-uri", required=True, help="OAuth callback URL")
        parser.add_argument("--user-id", help="Scope the connection to one end-user")

    def execute(self, args: Namespace, client: M8tes | None = None) -> int:
        if not client:
            print("❌ Authentication required for app management")
            show_auth_guidance()
            return 1

        try:
            with v2_client_from_args(args, client) as v2_client:
                result = v2_client.apps.connect_oauth(
                    args.app_name,
                    args.redirect_uri,
                    user_id=getattr(args, "user_id", None),
                )

            print("\n✅ OAuth flow started")
            print(f"   App: {args.app_name}")
            print(f"   Connection ID: {result.connection_id}")
            print(f"   Authorization URL: {result.authorization_url}")
            print("   Redirect your user to the URL above, then run connect-complete.")
            return 0
        except M8tesError as e:
            print(f"❌ Failed to start OAuth flow: {e}")
            return 1


class ConnectApiKeyCommand(Command):
    """Connect an API key-based app."""

    name = "connect-api-key"
    aliases: ClassVar[list[str]] = ["api-key"]
    description = "Connect an API key app"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("app_name", help="App provider name, for example gemini")
        parser.add_argument("app_api_key", help="API key to store for this app")
        parser.add_argument("--user-id", help="Scope the connection to one end-user")

    def execute(self, args: Namespace, client: M8tes | None = None) -> int:
        if not client:
            print("❌ Authentication required for app management")
            show_auth_guidance()
            return 1

        try:
            with v2_client_from_args(args, client) as v2_client:
                result = v2_client.apps.connect_api_key(
                    args.app_name,
                    args.app_api_key,
                    user_id=getattr(args, "user_id", None),
                )

            print("\n✅ App connected")
            print(f"   App: {result.app}")
            print(f"   Status: {result.status}")
            return 0
        except M8tesError as e:
            print(f"❌ Failed to connect app: {e}")
            return 1


class ConnectCompleteCommand(Command):
    """Complete an OAuth connection flow."""

    name = "connect-complete"
    aliases: ClassVar[list[str]] = ["complete"]
    description = "Complete an OAuth connection after the provider redirect"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("app_name", help="App provider name, for example gmail")
        parser.add_argument("connection_id", help="Connection ID returned by connect-oauth")
        parser.add_argument("--user-id", help="Scope the connection to one end-user")

    def execute(self, args: Namespace, client: M8tes | None = None) -> int:
        if not client:
            print("❌ Authentication required for app management")
            show_auth_guidance()
            return 1

        try:
            with v2_client_from_args(args, client) as v2_client:
                result = v2_client.apps.connect_complete(
                    args.app_name,
                    args.connection_id,
                    user_id=getattr(args, "user_id", None),
                )

            print("\n✅ OAuth connection completed")
            print(f"   App: {result.app}")
            print(f"   Status: {result.status}")
            return 0
        except M8tesError as e:
            print(f"❌ Failed to complete OAuth connection: {e}")
            return 1


class DisconnectCommand(Command):
    """Disconnect an app connection."""

    name = "disconnect"
    aliases: ClassVar[list[str]] = ["rm"]
    description = "Disconnect an app"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("app_name", help="App provider name, for example gmail")
        parser.add_argument("--user-id", help="Disconnect the app for one end-user")

    def execute(self, args: Namespace, client: M8tes | None = None) -> int:
        if not client:
            print("❌ Authentication required for app management")
            show_auth_guidance()
            return 1

        try:
            with v2_client_from_args(args, client) as v2_client:
                v2_client.apps.disconnect(args.app_name, user_id=getattr(args, "user_id", None))

            print("\n✅ App disconnected")
            print(f"   App: {args.app_name}")
            return 0
        except M8tesError as e:
            print(f"❌ Failed to disconnect app: {e}")
            return 1
