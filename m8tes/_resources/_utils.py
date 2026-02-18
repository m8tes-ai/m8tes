"""Shared helpers for resource modules."""

from typing import Any


def _build_params(**kwargs: Any) -> dict:
    """Build query params dict, omitting None values and default limit (20)."""
    return {k: v for k, v in kwargs.items() if v is not None and not (k == "limit" and v == 20)}
