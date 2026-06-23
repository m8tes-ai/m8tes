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
from ._auth import get_token, signup, signup_and_wait
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
    RunFailedError,
    ValidationError,
)
from ._resources.auth import Auth
from ._resources.billing import Billing
from ._resources.webhooks import Webhooks
from ._streaming import RunStream
from ._types import (
    AccountSettings,
    ApiKeyCreated,
    ApiKeyInfo,
    ApiKeyRotated,
    App,
    AppConnection,
    AppConnectionInitiation,
    AppConnectionResult,
    AppProvisionResult,
    AppTriggerType,
    AuditLog,
    Balance,
    Bridge,
    BuiltInTool,
    EmailInbox,
    EndUser,
    Lesson,
    LessonList,
    McpServer,
    Memory,
    NamedApiKey,
    PermissionMode,
    PermissionModeResponse,
    PermissionPolicy,
    PermissionRequest,
    Plan,
    Run,
    RunFile,
    SignupResult,
    SyncPage,
    Task,
    Teammate,
    TeammateTemplate,
    TeammateWebhook,
    TokenResult,
    TokenTransaction,
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
    "ApiKeyCreated",
    "ApiKeyInfo",
    "ApiKeyRotated",
    "App",
    "AppConnection",
    "AppConnectionInitiation",
    "AppConnectionResult",
    "AppProvisionResult",
    "AppTriggerType",
    "AuditLog",
    "Auth",
    "AuthenticationError",
    "Balance",
    "Billing",
    "BillingError",
    "Bridge",
    "BuiltInTool",
    "ConflictError",
    "Deployment",
    "DeploymentError",
    "DoneEvent",
    "EmailInbox",
    "EndUser",
    "ErrorEvent",
    "IntegrationError",
    "Lesson",
    "LessonList",
    "M8tes",
    "M8tesError",
    "McpServer",
    "Memory",
    "MetricsEvent",
    "NamedApiKey",
    "NetworkError",
    "NotFoundError",
    "OAuthError",
    "PermissionDeniedError",
    "PermissionMode",
    "PermissionModeResponse",
    "PermissionPolicy",
    "PermissionRequest",
    "Plan",
    "RateLimitError",
    "Run",
    "RunFailedError",
    "RunFile",
    "RunStream",
    "SignupResult",
    "StreamEvent",
    "StreamEventType",
    "SyncPage",
    "Task",
    "Teammate",
    "TeammateTemplate",
    "TeammateWebhook",
    "TextDeltaEvent",
    "TimeoutError",
    "TokenResult",
    "TokenTransaction",
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
    "signup_and_wait",
]
