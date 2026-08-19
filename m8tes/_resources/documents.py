"""Documents resource — manage persistent company and agent context."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from .._http import seg
from .._types import Document, DocumentDetail, SyncPage
from ._utils import _build_params

if TYPE_CHECKING:
    from .._http import HTTPClient


class Documents:
    """client.documents — list, read, rename, summarize, and delete documents."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def list(
        self,
        *,
        scope: Literal["company", "teammate"],
        agent_id: int | None = None,
        user_id: str | None = None,
    ) -> SyncPage[Document]:
        """List company documents or one agent's documents."""
        if scope == "teammate" and agent_id is None:
            raise ValueError("agent_id is required when scope='teammate'.")
        if scope == "company" and agent_id is not None:
            raise ValueError("agent_id is not valid when scope='company'.")
        response = self._http.request(
            "GET",
            "/documents",
            params=_build_params(scope=scope, agent_id=agent_id, user_id=user_id),
        )
        body = response.json()
        return SyncPage(
            data=[Document.from_dict(item) for item in body["data"]],
            has_more=body["has_more"],
        )

    def get(self, document_id: int, *, user_id: str | None = None) -> DocumentDetail:
        """Read one document's full content by ID."""
        response = self._http.request(
            "GET",
            f"/documents/{seg(document_id)}",
            params=_build_params(user_id=user_id),
        )
        return DocumentDetail.from_dict(response.json())

    def update(
        self,
        document_id: int,
        *,
        name: str | None = None,
        summary: str | None = None,
        user_id: str | None = None,
    ) -> Document:
        """Rename a document, update its summary, or both."""
        if name is None and summary is None:
            raise ValueError("Pass name, summary, or both.")
        body = _build_params(name=name, summary=summary)
        response = self._http.request(
            "PATCH",
            f"/documents/{seg(document_id)}",
            params=_build_params(user_id=user_id),
            json=body,
        )
        return Document.from_dict(response.json())

    def delete(self, document_id: int, *, user_id: str | None = None) -> None:
        """Delete one document in exactly the given end-user scope."""
        self._http.request(
            "DELETE",
            f"/documents/{seg(document_id)}",
            params=_build_params(user_id=user_id),
        )
