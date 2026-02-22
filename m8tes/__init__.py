"""
m8tes - Python SDK for m8tes.ai

Developer SDK for building AI teammates.
"""

__version__ = "1.0.0"

# ── v2 Developer SDK (primary) ───────────────────────────────────────
from ._client import M8tes
from ._exceptions import (
    APIError,
    AuthenticationError,
    ConflictError,
    M8tesError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ValidationError,
)
from ._resources.webhooks import Webhooks
from ._streaming import RunStream
from ._types import (
    App,
    AppConnection,
    Memory,
    PermissionPolicy,
    PermissionRequest,
    Run,
    RunFile,
    SyncPage,
    Task,
    Teammate,
    TeammateWebhook,
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
from .streaming import (
    DoneEvent,
    ErrorEvent,
    MetricsEvent,
    StreamEvent,
    StreamEventType,
    TextDeltaEvent,
    ToolCallDeltaEvent,
    ToolCallStartEvent,
    ToolResultEndEvent,
)

__all__ = [
    "APIError",
    "Agent",
    "AgentError",
    "App",
    "AppConnection",
    "AuthenticationError",
    "ConflictError",
    "Deployment",
    "DeploymentError",
    "DoneEvent",
    "ErrorEvent",
    "IntegrationError",
    "M8tes",
    "M8tesError",
    "Memory",
    "MetricsEvent",
    "NetworkError",
    "NotFoundError",
    "OAuthError",
    "PermissionDeniedError",
    "PermissionPolicy",
    "PermissionRequest",
    "RateLimitError",
    "Run",
    "RunFile",
    "RunStream",
    "StreamEvent",
    "StreamEventType",
    "SyncPage",
    "Task",
    "Teammate",
    "TeammateWebhook",
    "TextDeltaEvent",
    "TimeoutError",
    "ToolCallDeltaEvent",
    "ToolCallStartEvent",
    "ToolResultEndEvent",
    "Trigger",
    "ValidationError",
    "Webhook",
    "WebhookDelivery",
    "Webhooks",
]
