"""
m8tes - Python SDK for m8tes.ai

Developer SDK for building AI teammates.
"""

__version__ = "0.2.0"

# ── v2 Developer SDK (primary) ───────────────────────────────────────
from ._client import M8tes
from ._exceptions import (
    APIError,
    AuthenticationError,
    M8tesError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)
from ._streaming import RunStream
from ._types import App, PermissionPolicy, Run, SyncPage, Task, Teammate, Trigger

# ── Legacy exports (used by CLI) ─────────────────────────────────────
from .agent import Agent, Deployment
from .exceptions import (
    AgentError,
    DeploymentError,
    IntegrationError,
    M8tesError as _LegacyM8tesError,
    NetworkError,
    OAuthError,
    TimeoutError,
)

__all__ = [
    # v2 SDK
    "M8tes",
    "M8tesError",
    "APIError",
    "AuthenticationError",
    "NotFoundError",
    "RateLimitError",
    "ValidationError",
    "RunStream",
    "SyncPage",
    "Teammate",
    "Run",
    "Task",
    "Trigger",
    "App",
    "PermissionPolicy",
    # Legacy (CLI)
    "Agent",
    "AgentError",
    "Deployment",
    "DeploymentError",
    "IntegrationError",
    "NetworkError",
    "OAuthError",
    "TimeoutError",
]
