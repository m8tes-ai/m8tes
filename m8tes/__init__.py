"""
m8tes - Python SDK for m8tes.ai

AI teammates that handle paid ads automation.
"""

__version__ = "0.1.0"

from .agent import Agent, Deployment
from .client import M8tes
from .exceptions import (
    AgentError,
    AuthenticationError,
    DeploymentError,
    IntegrationError,
    M8tesError,
    NetworkError,
    OAuthError,
    RateLimitError,
    TimeoutError,
    ValidationError,
)

__all__ = [
    # Core classes
    "Agent",
    "AgentError",
    "AuthenticationError",
    "Deployment",
    "DeploymentError",
    "IntegrationError",
    # Main client
    "M8tes",
    "M8tesError",
    "NetworkError",
    "OAuthError",
    "RateLimitError",
    "TimeoutError",
    "ValidationError",
]
