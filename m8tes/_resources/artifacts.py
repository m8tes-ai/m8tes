"""Artifacts resource — durable, shareable copies of what a run produced."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._http import seg
from .._types import Artifact, ArtifactShare, SyncPage
from ._utils import _build_params

if TYPE_CHECKING:
    from .._http import HTTPClient


class Artifacts:
    """client.artifacts — promote run files, read them back, share them publicly."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def create(self, *, run_id: int, filename: str) -> Artifact:
        """Promote a run output file (e.g. ``latest-report.md``) into a durable artifact.

        Idempotent per (run, filename) — repeat calls return the same artifact.
        """
        response = self._http.request(
            "POST", "/artifacts", json={"run_id": run_id, "filename": filename}
        )
        return Artifact.from_dict(response.json())

    def list(
        self,
        *,
        run_id: int | None = None,
        agent_id: int | None = None,
        user_id: str | None = None,
        limit: int | None = None,
        starting_after: int | None = None,
    ) -> SyncPage[Artifact]:
        """List artifacts, newest first. Filter by run or agent."""
        response = self._http.request(
            "GET",
            "/artifacts",
            params=_build_params(
                run_id=run_id,
                agent_id=agent_id,
                user_id=user_id,
                limit=limit,
                starting_after=starting_after,
            ),
        )
        body = response.json()

        def _fetch_next(**kw: object) -> SyncPage[Artifact]:
            return self.list(run_id=run_id, agent_id=agent_id, user_id=user_id, limit=limit, **kw)  # type: ignore[arg-type]

        return SyncPage(
            data=[Artifact.from_dict(item) for item in body["data"]],
            has_more=body["has_more"],
            next_starting_after=body.get("next_starting_after"),
            _fetch_next=_fetch_next,
        )

    def get(self, artifact_id: int, *, user_id: str | None = None) -> Artifact:
        """Read one artifact's metadata."""
        response = self._http.request(
            "GET", f"/artifacts/{seg(artifact_id)}", params=_build_params(user_id=user_id)
        )
        return Artifact.from_dict(response.json())

    def download(self, artifact_id: int, *, user_id: str | None = None) -> bytes:
        """Download the artifact's raw bytes."""
        response = self._http.request(
            "GET",
            f"/artifacts/{seg(artifact_id)}/content",
            params=_build_params(user_id=user_id),
        )
        return response.content

    def delete(self, artifact_id: int, *, user_id: str | None = None) -> None:
        """Delete an artifact. Its public link (if any) dies with it."""
        self._http.request(
            "DELETE", f"/artifacts/{seg(artifact_id)}", params=_build_params(user_id=user_id)
        )

    def share(self, artifact_id: int, *, user_id: str | None = None) -> ArtifactShare:
        """Create a public read-only link. Idempotent; revoke with :meth:`unshare`."""
        response = self._http.request(
            "POST", f"/artifacts/{seg(artifact_id)}/share", params=_build_params(user_id=user_id)
        )
        return ArtifactShare.from_dict(response.json())

    def unshare(self, artifact_id: int, *, user_id: str | None = None) -> None:
        """Revoke the public link. The old URL 404s immediately."""
        self._http.request(
            "DELETE",
            f"/artifacts/{seg(artifact_id)}/share",
            params=_build_params(user_id=user_id),
        )
