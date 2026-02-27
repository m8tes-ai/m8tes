"""M8tes developer SDK — Stripe-style client for the v2 API."""

from __future__ import annotations

import os

from ._exceptions import AuthenticationError
from ._http import HTTPClient
from ._resources import (
    Apps,
    Auth,
    Memories,
    Permissions,
    Runs,
    Settings,
    Tasks,
    Teammates,
    Users,
    Webhooks,
)


class M8tes:
    """Developer client for the m8tes v2 API.

    Usage:
        client = M8tes(api_key="m8_...")
        teammate = client.teammates.create(name="Bot", tools=["gmail"])
        for event in client.runs.create(teammate_id=teammate.id, message="Do X"):
            print(event.type, event.raw)
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: int = 300,
    ):
        api_key = api_key or os.environ.get("M8TES_API_KEY")
        base_url = base_url or os.environ.get("M8TES_BASE_URL") or "https://m8tes.ai/api/v2"
        if not api_key:
            raise AuthenticationError(
                "No API key provided. Pass api_key= or set M8TES_API_KEY env var."
            )

        self._http = HTTPClient(api_key=api_key, base_url=base_url, timeout=timeout)
        self.auth = Auth(self._http)
        self.teammates = Teammates(self._http)
        self.runs = Runs(self._http)
        self.tasks = Tasks(self._http)
        self.apps = Apps(self._http)
        self.memories = Memories(self._http)
        self.permissions = Permissions(self._http)
        self.users = Users(self._http)
        self.settings = Settings(self._http)
        self.webhooks = Webhooks(self._http)

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self._http._session.close()

    def __enter__(self) -> M8tes:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
