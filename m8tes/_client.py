"""M8tes developer SDK — Stripe-style client for the v2 API."""

from __future__ import annotations

import os

from ._exceptions import AuthenticationError
from ._http import HTTPClient
from ._resources import Apps, Memories, Permissions, Runs, Tasks, Teammates, Webhooks


class M8tes:
    """Developer client for the m8tes v2 API.

    Usage:
        client = M8tes(api_key="m8_...")
        teammate = client.teammates.create(name="Bot", tools=["gmail"])
        for event in client.runs.create(teammate_id=teammate.id, task="Do X"):
            print(event.type, event.raw)
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://m8tes.ai/api/v2",
        timeout: int = 300,
    ):
        api_key = api_key or os.environ.get("M8TES_API_KEY")
        if not api_key:
            raise AuthenticationError(
                "No API key provided. Pass api_key= or set M8TES_API_KEY env var."
            )

        self._http = HTTPClient(api_key=api_key, base_url=base_url, timeout=timeout)
        self.teammates = Teammates(self._http)
        self.runs = Runs(self._http)
        self.tasks = Tasks(self._http)
        self.apps = Apps(self._http)
        self.memories = Memories(self._http)
        self.permissions = Permissions(self._http)
        self.webhooks = Webhooks(self._http)
