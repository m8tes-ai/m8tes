"""
Main CLI entry point for m8tes SDK.

The CLI is a plain v2 API customer: every command runs through the same v2 SDK
client a developer uses (session login/refresh is the one platform-only
exception, handled in cli/auth.py).
"""

import argparse
import os
import sys

from m8tes import __version__

from .._client import M8tes
from .registry import registry
from .util import SuggestingArgumentParser, graceful_main, suggest_commands
from .v2 import normalize_v2_base_url


def create_client(
    api_key: str | None = None, base_url: str | None = None, allow_no_key: bool = False
) -> M8tes | None:
    """Create a v2 SDK client, resolving the key from args → keychain → env."""
    try:
        # Try to load saved API key if not provided (refreshes an expired session token)
        from_profile = False
        if not api_key:
            from .auth import AuthCLI

            auth_cli = AuthCLI(base_url=base_url)
            saved_key = auth_cli.get_valid_api_key()
            if saved_key:
                api_key = saved_key
                from_profile = True

        # Normalize the env fallback too: CLI users set M8TES_BASE_URL to a bare
        # host (the session-auth convention), which the v2 client would otherwise
        # consume raw and send /tasks/ requests to the host root.
        client = M8tes(
            api_key=api_key,
            base_url=normalize_v2_base_url(base_url or os.getenv("M8TES_BASE_URL")),
        )
        # Credential PROVENANCE, recorded where it is known. The session-auth
        # surface (cli/google.py) may only let a key from the credential store
        # drive the profile's refresh dance — and re-deriving that downstream
        # would mean another credential-store read (see auth/http.py).
        client.api_key_from_profile = from_profile
        return client
    except Exception as e:
        if allow_no_key:
            return None
        print(f"❌ {e}")
        # Don't repeat guidance if it's already in the error message
        if "m8tes auth" not in str(e):
            print(
                "💡 Try 'm8tes auth login' to authenticate or "
                "set M8TES_API_KEY environment variable"
            )
        sys.exit(1)


def _real_main(argv: list[str]) -> int:
    """Real main CLI logic that handles command parsing and execution."""
    # Discover and register all commands
    registry.auto_discover_commands()

    # Create main parser (suggests close matches on invalid choice)
    parser = SuggestingArgumentParser(
        prog="m8tes",
        description="m8tes SDK - Ship agents. Skip the infrastructure.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Global arguments
    parser.add_argument(
        "--api-key", help="M8tes API key (or set M8TES_API_KEY environment variable)"
    )
    parser.add_argument("--base-url", help="Custom API base URL")
    parser.add_argument(
        "--dev",
        action="store_true",
        help=(
            "Use local development server (http://127.0.0.1:8000, or port from M8TES_PORT env var)"
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    # Create subparsers for commands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Register all discovered commands
    for command in registry.get_primary_commands():
        # Create subparser with primary name and aliases
        subparser = subparsers.add_parser(
            command.name, aliases=command.aliases, help=command.description
        )
        command.add_arguments(subparser)

    # Parse arguments
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    # Set base URL for dev mode
    base_url = args.base_url
    if args.dev:
        dev_port = os.getenv("M8TES_PORT", "8000")
        base_url = f"http://127.0.0.1:{dev_port}"

    # Store these in args for commands to access
    args.base_url = base_url
    args.dev = getattr(args, "dev", False)

    # Get the command to execute
    try:
        command = registry.get_command(args.command)
    except KeyError:
        known = sorted({c.name for c in registry.get_primary_commands()})
        suggestions = suggest_commands(args.command, known)
        print(f"❌ Unknown command: {args.command}")
        if suggestions:
            print(f"💡 Did you mean: {', '.join(suggestions)}?")
        else:
            print(f"Available: {', '.join(known)}")
        return 1

    # Create client if needed
    client = None
    if command.requires_auth:
        client = create_client(args.api_key, base_url)
    else:
        # For commands that don't require auth, try to create client but allow failure
        client = create_client(args.api_key, base_url, allow_no_key=True)

    # Execute the command
    try:
        return command.execute(args, client)
    except Exception as e:
        print(f"❌ Command execution failed: {e}")
        return 1


def main() -> None:
    """Main CLI entry point with graceful interrupt handling."""
    code = graceful_main(_real_main, sys.argv[1:])
    raise SystemExit(code)


if __name__ == "__main__":
    main()
