"""Shared helpers for resource modules."""

from typing import Any


def _build_params(**kwargs: Any) -> dict:
    """Build query params dict, omitting None values and default limit (20)."""
    return {k: v for k, v in kwargs.items() if v is not None and not (k == "limit" and v == 20)}


def _resolve_agent_id(teammate_id: int | None, agent_id: int | None) -> int | None:
    """agent_id is the canonical name; teammate_id is the permanent legacy alias.

    Both map to the same wire field (teammate_id). Passing conflicting values is
    an error rather than a silent pick.
    """
    if agent_id is not None and teammate_id is not None and agent_id != teammate_id:
        raise ValueError("Pass agent_id or teammate_id, not both")
    return teammate_id if teammate_id is not None else agent_id
