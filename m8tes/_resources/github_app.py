"""GitHub App resource — m8tes Code account install for coding agents.

Account-scoped only (not per end-user). Browser callback stays on the platform;
use ``install_url()`` then ``claim(ticket=…)`` when the redirect returns a ticket.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._types import GitHubAppStatus, GitHubRepository, SyncPage

if TYPE_CHECKING:
    from .._http import HTTPClient


class GitHubApp:
    """client.github_app — connect GitHub for coding agents."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def status(self) -> GitHubAppStatus:
        """Connection state for this account's GitHub App install."""
        return GitHubAppStatus.from_dict(self._http.request("GET", "/github-app/status").json())

    def install_url(self) -> str:
        """URL to open in a browser to install the App (selected repositories only)."""
        return str(self._http.request("GET", "/github-app/install-url").json()["install_url"])

    def claim(self, *, ticket: str) -> str:
        """Bind an install named by a claim ticket. Returns a status slug."""
        return str(
            self._http.request("POST", "/github-app/claim", json={"ticket": ticket}).json()[
                "status"
            ]
        )

    def list_repos(self) -> SyncPage[GitHubRepository]:
        """Repositories the account install can reach."""
        body = self._http.request("GET", "/github-app/repos").json()
        return SyncPage(
            data=[GitHubRepository.from_dict(d) for d in body["data"]],
            has_more=body.get("has_more", False),
            next_starting_after=body.get("next_starting_after"),
        )

    def disconnect(self) -> None:
        """Disconnect GitHub and drop every agent repo binding."""
        self._http.request("DELETE", "/github-app")
