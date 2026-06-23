"""Teammates resource — CRUD for agent personas."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .._types import EmailInbox, FetchmailInbox, SyncPage, Teammate, TeammateWebhook
from ._utils import _build_params

_list = list  # preserve builtin; shadowed by .list() method

# Sentinel distinguishing "not provided" from an explicit None. Needed for
# fields where the v2 PATCH contract makes null meaningful (model: null clears
# the teammate back to the platform default).
_UNSET: Any = object()

if TYPE_CHECKING:
    from .._http import HTTPClient


class Teammates:
    """client.teammates — agent persona CRUD."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def create(
        self,
        *,
        name: str | None = None,
        tools: list[str] | None = None,
        instructions: str | None = None,
        role: str | None = None,
        goals: str | None = None,
        enable_memory: bool | None = None,
        enable_history: bool | None = None,
        enable_task_setup_tools: bool | None = None,
        enable_feedback: bool | None = None,
        user_id: str | None = None,
        metadata: dict | None = None,
        allowed_senders: list[str] | None = None,
        inbound_imessage_enabled: bool = False,
        imessage_chat_guid: str | None = None,
        bridge_id: int | None = None,
        allowed_imessage_senders: list[str] | None = None,
        inbound_slack_enabled: bool = False,
        slack_slug: str | None = None,
        allowed_slack_senders: list[str] | None = None,
        email_inbox: bool = False,
        webhook: bool = False,
        default_permission_mode: str | None = None,
        model: str | None = None,
        from_template: str | None = None,
    ) -> Teammate:
        """Create a teammate.

        Two modes:
        - Custom: provide name, instructions, tools, etc.
        - Templated: provide ``from_template="ppc-manager"`` to enable a pre-built
          persona. Improvements we ship to the template flow through automatically
          on subsequent reads, unless you customize the field via ``update()``
          (which routes through per-field overrides). Only ``user_id`` and
          ``metadata`` may co-exist with ``from_template``; other fields raise
          400 ``from_template_conflict``.
        """
        body: dict = {}
        if name is not None:
            body["name"] = name
        if tools is not None:
            body["tools"] = tools
        if instructions is not None:
            body["instructions"] = instructions
        if role is not None:
            body["role"] = role
        if goals is not None:
            body["goals"] = goals
        if enable_memory is not None:
            body["enable_memory"] = enable_memory
        if enable_history is not None:
            body["enable_history"] = enable_history
        if enable_task_setup_tools is not None:
            body["enable_task_setup_tools"] = enable_task_setup_tools
        if enable_feedback is not None:
            body["enable_feedback"] = enable_feedback
        if user_id is not None:
            body["user_id"] = user_id
        if metadata is not None:
            body["metadata"] = metadata
        if allowed_senders is not None:
            body["allowed_senders"] = allowed_senders
        if inbound_imessage_enabled:
            body["inbound_imessage_enabled"] = True
        if imessage_chat_guid is not None:
            body["imessage_chat_guid"] = imessage_chat_guid
        if bridge_id is not None:
            body["bridge_id"] = bridge_id
        if allowed_imessage_senders is not None:
            body["allowed_imessage_senders"] = allowed_imessage_senders
        if inbound_slack_enabled:
            body["inbound_slack_enabled"] = True
        if slack_slug is not None:
            body["slack_slug"] = slack_slug
        if allowed_slack_senders is not None:
            body["allowed_slack_senders"] = allowed_slack_senders
        if email_inbox:
            body["email_inbox"] = True
        if webhook:
            body["webhook"] = True
        if default_permission_mode is not None:
            body["default_permission_mode"] = default_permission_mode
        if model is not None:
            body["model"] = model
        if from_template is not None:
            body["from_template"] = from_template
        resp = self._http.request("POST", "/teammates/", json=body)
        return Teammate.from_dict(resp.json())

    def list(
        self,
        *,
        user_id: str | None = None,
        limit: int = 20,
        starting_after: int | None = None,
    ) -> SyncPage[Teammate]:
        params = _build_params(user_id=user_id, limit=limit, starting_after=starting_after)
        resp = self._http.request("GET", "/teammates/", params=params)
        body = resp.json()

        def _fetch_next(**kw: object) -> SyncPage[Teammate]:
            return self.list(user_id=user_id, **kw)  # type: ignore[arg-type]

        return SyncPage(
            data=[Teammate.from_dict(d) for d in body["data"]],
            has_more=body["has_more"],
            _fetch_next=_fetch_next,
        )

    def get(self, teammate_id: int) -> Teammate:
        resp = self._http.request("GET", f"/teammates/{teammate_id}")
        return Teammate.from_dict(resp.json())

    def update(
        self,
        teammate_id: int,
        *,
        name: str | None = None,
        instructions: str | None = None,
        tools: _list[str] | None = None,
        role: str | None = None,
        goals: str | None = None,
        metadata: dict | None = None,
        allowed_senders: _list[str] | None = None,
        inbound_imessage_enabled: bool | None = None,
        imessage_chat_guid: str | None = None,
        bridge_id: int | None = None,
        allowed_imessage_senders: _list[str] | None = None,
        inbound_slack_enabled: bool | None = None,
        slack_slug: str | None = None,
        allowed_slack_senders: _list[str] | None = None,
        default_permission_mode: str | None = None,
        model: str | None = _UNSET,
        enable_memory: bool | None = _UNSET,
        enable_history: bool | None = _UNSET,
        enable_task_setup_tools: bool | None = _UNSET,
        enable_feedback: bool | None = _UNSET,
    ) -> Teammate:
        """Update a teammate (PATCH semantics — omitted fields stay unchanged).

        ``model`` is special: passing ``model=None`` explicitly CLEARS the
        teammate back to the platform default (sends JSON null), while omitting
        it leaves the model unchanged. This mirrors the v2 contract, where null
        is a meaningful model state — deliberately unlike
        ``default_permission_mode``, where None means leave-unchanged.

        The four ``enable_*`` built-in tool defaults follow the same null-is-
        meaningful rule: pass ``enable_memory=None`` to reset that toggle back to
        the platform default (inherit), pass True/False to pin it, or omit to
        leave it unchanged.
        """
        body: dict = {}
        if name is not None:
            body["name"] = name
        if instructions is not None:
            body["instructions"] = instructions
        if tools is not None:
            body["tools"] = tools
        if role is not None:
            body["role"] = role
        if goals is not None:
            body["goals"] = goals
        if metadata is not None:
            body["metadata"] = metadata
        if allowed_senders is not None:
            body["allowed_senders"] = allowed_senders
        if inbound_imessage_enabled is not None:
            body["inbound_imessage_enabled"] = inbound_imessage_enabled
        if imessage_chat_guid is not None:
            body["imessage_chat_guid"] = imessage_chat_guid
        if bridge_id is not None:
            body["bridge_id"] = bridge_id
        if allowed_imessage_senders is not None:
            body["allowed_imessage_senders"] = allowed_imessage_senders
        if inbound_slack_enabled is not None:
            body["inbound_slack_enabled"] = inbound_slack_enabled
        if slack_slug is not None:
            body["slack_slug"] = slack_slug
        if allowed_slack_senders is not None:
            body["allowed_slack_senders"] = allowed_slack_senders
        if default_permission_mode is not None:
            body["default_permission_mode"] = default_permission_mode
        if model is not _UNSET:
            body["model"] = model  # explicit None -> JSON null -> clears to default
        # Explicit None -> JSON null -> resets the toggle to the platform default.
        if enable_memory is not _UNSET:
            body["enable_memory"] = enable_memory
        if enable_history is not _UNSET:
            body["enable_history"] = enable_history
        if enable_task_setup_tools is not _UNSET:
            body["enable_task_setup_tools"] = enable_task_setup_tools
        if enable_feedback is not _UNSET:
            body["enable_feedback"] = enable_feedback
        resp = self._http.request("PATCH", f"/teammates/{teammate_id}", json=body)
        return Teammate.from_dict(resp.json())

    def delete(self, teammate_id: int) -> None:
        self._http.request("DELETE", f"/teammates/{teammate_id}")

    def reset(self, teammate_id: int, *, fields: _list[str] | None = None) -> _list[str]:
        """Clear customer overrides on a template-linked teammate.

        Templated teammates store user customizations in an overrides JSON; this
        clears the named keys (or all of them when ``fields`` is None), letting
        future template updates flow through to the reset fields again. On
        non-templated teammates returns an empty list (no overrides to clear).

        Returns the list of fields actually reset.

        `list` is shadowed by the ``.list()`` method on this class; ``_list`` is
        the module-level alias for ``builtins.list`` (see top of file).
        """
        body: dict = {}
        if fields is not None:
            body["fields"] = fields
        resp = self._http.request("POST", f"/teammates/{teammate_id}/reset", json=body)
        return _list(resp.json().get("reset_fields", []))

    def enable_webhook(self, teammate_id: int) -> TeammateWebhook:
        """Enable webhook trigger on a teammate. Returns the webhook URL (shown once)."""
        resp = self._http.request("POST", f"/teammates/{teammate_id}/webhook")
        return TeammateWebhook.from_dict(resp.json())

    def disable_webhook(self, teammate_id: int) -> None:
        """Disable webhook trigger on a teammate."""
        self._http.request("DELETE", f"/teammates/{teammate_id}/webhook")

    def enable_email_inbox(self, teammate_id: int) -> EmailInbox:
        """Enable email inbox on a teammate. Returns the email address."""
        resp = self._http.request("POST", f"/teammates/{teammate_id}/email-inbox")
        return EmailInbox.from_dict(resp.json())

    def disable_email_inbox(self, teammate_id: int) -> None:
        """Disable email inbox on a teammate."""
        self._http.request("DELETE", f"/teammates/{teammate_id}/email-inbox")

    def enable_fetchmail(self, teammate_id: int) -> FetchmailInbox:
        """Enable read-only email inbox on a teammate. Returns the email address."""
        resp = self._http.request("POST", f"/teammates/{teammate_id}/fetchmail")
        return FetchmailInbox.from_dict(resp.json())

    def disable_fetchmail(self, teammate_id: int) -> None:
        """Disable read-only email inbox on a teammate."""
        self._http.request("DELETE", f"/teammates/{teammate_id}/fetchmail")
