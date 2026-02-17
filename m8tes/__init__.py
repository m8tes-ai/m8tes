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
from ._types import (
    App,
    AppConnection,
    Memory,
    PermissionPolicy,
    PermissionRequest,
    Run,
    SyncPage,
    Task,
    Teammate,
    Trigger,
    Webhook,
    WebhookDelivery,
)

# ── Legacy exports (used by CLI) ─────────────────────────────────────
from .agent import Agent, Deployment
from .exceptions import (
    AgentError,
    DeploymentError,
    IntegrationError,
    NetworkError,
    OAuthError,
    TimeoutError,
)

__all__ = [
    "APIError",
    "Agent",
    "AgentError",
    "App",
    "AppConnection",
    "AuthenticationError",
    "Deployment",
    "DeploymentError",
    "IntegrationError",
    "M8tes",
    "M8tesError",
    "Memory",
    "NetworkError",
    "NotFoundError",
    "OAuthError",
    "PermissionPolicy",
    "PermissionRequest",
    "RateLimitError",
    "Run",
    "RunStream",
    "SyncPage",
    "Task",
    "Teammate",
    "TimeoutError",
    "Trigger",
    "ValidationError",
    "Webhook",
    "WebhookDelivery",
]
