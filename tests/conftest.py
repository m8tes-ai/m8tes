"""
Root pytest configuration and fixtures for m8tes SDK.

Provides common fixtures and test utilities for the SDK test suite.
"""

import os
from pathlib import Path
import sys

import pytest
import responses

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session")
def test_data_dir():
    """Path to test data directory."""
    return Path(__file__).parent / "data"


@pytest.fixture
def sample_data():
    """Sample test data for general use."""
    return {
        "test_string": "hello world",
        "test_number": 42,
        "test_list": [1, 2, 3],
        "test_dict": {"key": "value"},
    }


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    return {
        "TESTING": True,
        "API_KEY": "test-api-key",
        "BASE_URL": "https://api.test.m8tes.ai",
        "TIMEOUT": 30,
    }


@pytest.fixture
def api_key():
    """Test API key."""
    return "test-api-key-12345"


@pytest.fixture
def base_url():
    """Test base URL."""
    return "https://api.test.m8tes.ai"


@pytest.fixture
def mock_agent_data():
    """Mock agent data for testing."""
    return {
        "id": "agent_123",
        "name": "Test Agent",
        "tools": ["google_ads_search", "google_ads_negatives"],
        "instructions": "Test instructions",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }


@pytest.fixture
def mock_deployment_data():
    """Mock deployment data for testing."""
    return {
        "id": "deploy_123",
        "agent_id": "agent_123",
        "name": "Test Deployment",
        "schedule": "daily",
        "webhook_url": None,
        "status": "active",
        "created_at": "2024-01-01T00:00:00Z",
    }


@pytest.fixture
def mock_run_events():
    """Mock streaming run events for testing."""
    return [
        {"type": "start", "agent_id": "agent_123", "timestamp": "2024-01-01T00:00:00Z"},
        {
            "type": "thought",
            "content": "Analyzing Google Ads account...",
            "timestamp": "2024-01-01T00:00:01Z",
        },
        {
            "type": "action",
            "tool": "google_ads_search",
            "action": "get_search_terms",
            "timestamp": "2024-01-01T00:00:02Z",
        },
        {
            "type": "result",
            "content": "Found 10 irrelevant search terms. Adding as negative keywords...",
            "timestamp": "2024-01-01T00:00:03Z",
        },
        {
            "type": "complete",
            "summary": "Successfully added 10 negative keywords",
            "timestamp": "2024-01-01T00:00:04Z",
        },
    ]


@pytest.fixture(autouse=True)
def clean_environment():
    """Clean environment variables before each test."""
    original_env = os.environ.copy()

    # Remove m8tes environment variables
    for key in list(os.environ.keys()):
        if key.startswith("M8TES_"):
            del os.environ[key]

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_requests():
    """Mock HTTP requests using responses library."""
    with responses.RequestsMock() as rsps:
        yield rsps


@pytest.fixture
def authenticated_client(api_key, base_url):
    """Create an authenticated M8tes client for testing."""
    from m8tes import M8tes

    return M8tes(api_key=api_key, base_url=base_url)


@pytest.fixture
def mock_agent(authenticated_client, mock_agent_data):
    """Create a mock agent instance for testing."""
    from m8tes.agent import Agent

    return Agent(agent_service=authenticated_client.agents, data=mock_agent_data)
