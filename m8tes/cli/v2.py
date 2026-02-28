"""Helpers for CLI commands that need the v2 SDK client."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from .._client import M8tes as V2Client
from .._exceptions import AuthenticationError
from .auth import AuthCLI


def normalize_v2_base_url(base_url: str | None) -> str | None:
    """Convert a root or v1 base URL into the v2 SDK base URL."""
    if not base_url:
        return None

    normalized = base_url.rstrip("/")
    if normalized.endswith("/api/v2") or normalized.endswith("/v2"):
        return normalized
    if normalized.endswith("/api/v1"):
        return f"{normalized[: -len('/api/v1')]}/api/v2"
    if normalized.endswith("/api"):
        return f"{normalized}/v2"
    return f"{normalized}/api/v2"


def get_v2_api_key(args: Any, client: Any = None) -> str | None:
    """Resolve an API key from CLI args, the current client, or saved credentials."""
    api_key: str | None = getattr(args, "api_key", None)
    if api_key:
        return api_key

    client_key: str | None = getattr(client, "api_key", None)
    if client_key:
        return client_key

    auth_cli = AuthCLI(base_url=getattr(args, "base_url", None))
    return auth_cli.get_saved_api_key()


def create_v2_client(args: Any, client: Any = None) -> V2Client:
    """Create an authenticated v2 SDK client for CLI commands."""
    api_key = get_v2_api_key(args, client)
    if not api_key:
        raise AuthenticationError(
            "Authentication required. Run 'm8tes auth login' or pass --api-key."
        )

    base_url = normalize_v2_base_url(
        getattr(args, "base_url", None) or getattr(client, "base_url", None)
    )
    return V2Client(api_key=api_key, base_url=base_url)


@contextmanager
def v2_client_from_args(args: Any, client: Any = None) -> Generator[V2Client, None, None]:
    """Yield a v2 SDK client and always close its HTTP session."""
    v2_client = create_v2_client(args, client)
    try:
        yield v2_client
    finally:
        v2_client.close()
