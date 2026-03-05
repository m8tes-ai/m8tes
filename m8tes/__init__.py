"""
m8tes - Python SDK for m8tes.ai

Developer SDK for building AI teammates.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("m8tes")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"

# ── v2 Developer SDK (primary) ───────────────────────────────────────
from ._auth import get_token, signup
from ._client import M8tes
from ._exceptions import (
    APIError,
    AuthenticationError,
    BillingError,
    ConflictError,
    M8tesError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ValidationError,
)
from ._resources.auth import Auth
from ._resources.webhooks import Webhooks
from ._streaming import RunStream
from ._types import (
    AccountSettings,
    App,
    AppConnection,
    AppConnectionInitiation,
    AppConnectionResult,
    AppTriggerType,
    AuditLog,
    EmailInbox,
    EndUser,
    Memory,
    PermissionMode,
    PermissionModeResponse,
    PermissionPolicy,
    PermissionRequest,
    Run,
    RunFile,
    SignupResult,
    SyncPage,
    Task,
    Teammate,
    TeammateWebhook,
    TokenResult,
    Trigger,
    Usage,
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
    "AccountSettings",
    "Agent",
    "AgentError",
    "App",
    "AppConnection",
    "AppConnectionInitiation",
    "AppConnectionResult",
    "AppTriggerType",
    "AuditLog",
    "Auth",
    "AuthenticationError",
    "BillingError",
    "ConflictError",
    "Deployment",
    "DeploymentError",
    "DoneEvent",
    "EmailInbox",
    "EndUser",
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
    "PermissionMode",
    "PermissionModeResponse",
    "PermissionPolicy",
    "PermissionRequest",
    "RateLimitError",
    "Run",
    "RunFile",
    "RunStream",
    "SignupResult",
    "StreamEvent",
    "StreamEventType",
    "SyncPage",
    "Task",
    "Teammate",
    "TeammateWebhook",
    "TextDeltaEvent",
    "TimeoutError",
    "TokenResult",
    "ToolCallDeltaEvent",
    "ToolCallStartEvent",
    "ToolResultEndEvent",
    "Trigger",
    "Usage",
    "ValidationError",
    "Webhook",
    "WebhookDelivery",
    "Webhooks",
    "get_token",
    "signup",
]
