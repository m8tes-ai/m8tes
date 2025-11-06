"""
Unit tests for AgentService.

Tests the agent operations service that handles creating, retrieving, and
listing agents through the m8tes API.
"""

from unittest.mock import Mock

import pytest

from m8tes.exceptions import AuthenticationError, NetworkError, ValidationError
from m8tes.services.agents import AgentService


@pytest.fixture
def mock_http_client():
    """Create a mock HTTP client for testing."""
    client = Mock()
    return client


@pytest.fixture
def agent_service(mock_http_client):
    """Create an AgentService instance with mocked HTTP client."""
    return AgentService(http_client=mock_http_client)


@pytest.fixture
def sample_agent_data():
    """Sample agent data returned from API."""
    return {
        "id": "agent_123",
        "name": "Test Agent",
        "tools": ["google_ads_search", "google_ads_negatives"],
        "instructions": "Test instructions",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }


@pytest.mark.unit
class TestAgentServiceInitialization:
    """Test AgentService initialization."""

    def test_initialization_with_http_client(self, mock_http_client):
        """Test that service initializes with HTTP client."""
        service = AgentService(http_client=mock_http_client)
        assert service.http == mock_http_client

    def test_initialization_stores_http_reference(self, mock_http_client):
        """Test that HTTP client reference is stored."""
        service = AgentService(http_client=mock_http_client)
        assert hasattr(service, "http")
        assert service.http is mock_http_client


@pytest.mark.unit
class TestCreateAgent:
    """Test agent creation functionality."""

    def test_create_agent_with_required_params(
        self, agent_service, mock_http_client, sample_agent_data
    ):
        """Test creating agent with only required parameters."""
        mock_http_client.request.return_value = sample_agent_data

        tools = ["google_ads_search"]
        instructions = "Test instructions"

        agent = agent_service.create_agent(tools=tools, instructions=instructions)

        # Verify API call
        mock_http_client.request.assert_called_once_with(
            "POST",
            "/api/v1/agents",
            json_data={
                "tools": tools,
                "instructions": instructions,
            },
        )

        # Verify returned agent
        assert agent.id == "agent_123"
        assert agent.tools == ["google_ads_search", "google_ads_negatives"]

    def test_create_agent_with_name(self, agent_service, mock_http_client, sample_agent_data):
        """Test creating agent with optional name parameter."""
        mock_http_client.request.return_value = sample_agent_data

        tools = ["google_ads_search"]
        instructions = "Test instructions"
        name = "My Test Agent"

        agent = agent_service.create_agent(tools=tools, instructions=instructions, name=name)

        # Verify API call includes name
        mock_http_client.request.assert_called_once_with(
            "POST",
            "/api/v1/agents",
            json_data={
                "tools": tools,
                "instructions": instructions,
                "name": name,
            },
        )

        assert agent.id == "agent_123"

    def test_create_agent_with_multiple_tools(
        self, agent_service, mock_http_client, sample_agent_data
    ):
        """Test creating agent with multiple tools."""
        mock_http_client.request.return_value = sample_agent_data

        tools = ["google_ads_search", "google_ads_negatives", "google_ads_budgets"]
        instructions = "Manage campaigns"

        agent_service.create_agent(tools=tools, instructions=instructions)

        mock_http_client.request.assert_called_once()
        call_args = mock_http_client.request.call_args
        assert call_args[1]["json_data"]["tools"] == tools

    def test_create_agent_returns_agent_instance(
        self, agent_service, mock_http_client, sample_agent_data
    ):
        """Test that create_agent returns an Agent instance."""
        mock_http_client.request.return_value = sample_agent_data

        agent = agent_service.create_agent(tools=["google_ads_search"], instructions="Test")

        from m8tes.agent import Agent

        assert isinstance(agent, Agent)

    def test_create_agent_handles_validation_error(self, agent_service, mock_http_client):
        """Test that validation errors are properly raised."""
        mock_http_client.request.side_effect = ValidationError("Invalid tools")

        with pytest.raises(ValidationError, match="Invalid tools"):
            agent_service.create_agent(tools=["invalid_tool"], instructions="Test")

    def test_create_agent_handles_auth_error(self, agent_service, mock_http_client):
        """Test that authentication errors are properly raised."""
        mock_http_client.request.side_effect = AuthenticationError("Unauthorized")

        with pytest.raises(AuthenticationError, match="Unauthorized"):
            agent_service.create_agent(tools=["google_ads_search"], instructions="Test")


@pytest.mark.unit
class TestGetAgent:
    """Test agent retrieval functionality."""

    def test_get_agent_by_id(self, agent_service, mock_http_client, sample_agent_data):
        """Test retrieving an agent by ID."""
        mock_http_client.request.return_value = sample_agent_data

        agent = agent_service.get_agent("agent_123")

        # Verify API call
        mock_http_client.request.assert_called_once_with("GET", "/api/v1/agents/agent_123")

        # Verify returned agent
        assert agent.id == "agent_123"
        assert agent.name == "Test Agent"

    def test_get_agent_returns_agent_instance(
        self, agent_service, mock_http_client, sample_agent_data
    ):
        """Test that get_agent returns an Agent instance."""
        mock_http_client.request.return_value = sample_agent_data

        agent = agent_service.get_agent("agent_123")

        from m8tes.agent import Agent

        assert isinstance(agent, Agent)

    def test_get_agent_with_different_ids(self, agent_service, mock_http_client, sample_agent_data):
        """Test retrieving agents with different IDs."""
        mock_http_client.request.return_value = sample_agent_data

        # Get first agent
        agent_service.get_agent("agent_123")
        assert "/api/v1/agents/agent_123" in str(mock_http_client.request.call_args)

        # Get second agent
        agent_service.get_agent("agent_456")
        assert "/api/v1/agents/agent_456" in str(mock_http_client.request.call_args)

    def test_get_agent_not_found(self, agent_service, mock_http_client):
        """Test getting a non-existent agent raises error."""
        from m8tes.exceptions import AgentError

        mock_http_client.request.side_effect = AgentError("Agent not found", code="NOT_FOUND")

        with pytest.raises(AgentError, match="Agent not found"):
            agent_service.get_agent("nonexistent")

    def test_get_agent_handles_network_error(self, agent_service, mock_http_client):
        """Test that network errors are properly raised."""
        mock_http_client.request.side_effect = NetworkError("Connection failed")

        with pytest.raises(NetworkError, match="Connection failed"):
            agent_service.get_agent("agent_123")


@pytest.mark.unit
class TestListAgents:
    """Test agent listing functionality."""

    def test_list_agents_default_limit(self, agent_service, mock_http_client, sample_agent_data):
        """Test listing agents with default limit."""
        mock_http_client.request.return_value = {"agents": [sample_agent_data, sample_agent_data]}

        agents = agent_service.list_agents()

        # Verify API call with default limit
        mock_http_client.request.assert_called_once_with(
            "GET", "/api/v1/agents", params={"limit": 10}
        )

        # Verify returned agents
        assert len(agents) == 2
        assert all(agent.id == "agent_123" for agent in agents)

    def test_list_agents_custom_limit(self, agent_service, mock_http_client, sample_agent_data):
        """Test listing agents with custom limit."""
        mock_http_client.request.return_value = {"agents": [sample_agent_data] * 5}

        agents = agent_service.list_agents(limit=5)

        # Verify API call with custom limit
        mock_http_client.request.assert_called_once_with(
            "GET", "/api/v1/agents", params={"limit": 5}
        )

        assert len(agents) == 5

    def test_list_agents_empty_result(self, agent_service, mock_http_client):
        """Test listing agents when no agents exist."""
        mock_http_client.request.return_value = {"agents": []}

        agents = agent_service.list_agents()

        assert agents == []
        assert isinstance(agents, list)

    def test_list_agents_returns_agent_instances(
        self, agent_service, mock_http_client, sample_agent_data
    ):
        """Test that list_agents returns Agent instances."""
        mock_http_client.request.return_value = {"agents": [sample_agent_data, sample_agent_data]}

        agents = agent_service.list_agents()

        from m8tes.agent import Agent

        assert all(isinstance(agent, Agent) for agent in agents)

    def test_list_agents_with_large_limit(self, agent_service, mock_http_client, sample_agent_data):
        """Test listing agents with large limit value."""
        mock_http_client.request.return_value = {"agents": [sample_agent_data] * 100}

        agents = agent_service.list_agents(limit=100)

        mock_http_client.request.assert_called_once_with(
            "GET", "/api/v1/agents", params={"limit": 100}
        )

        assert len(agents) == 100

    def test_list_agents_handles_missing_agents_key(self, agent_service, mock_http_client):
        """Test listing agents when response doesn't have 'agents' key."""
        mock_http_client.request.return_value = {}

        agents = agent_service.list_agents()

        # Should return empty list when key is missing
        assert agents == []

    def test_list_agents_handles_auth_error(self, agent_service, mock_http_client):
        """Test that authentication errors are properly raised."""
        mock_http_client.request.side_effect = AuthenticationError("Unauthorized")

        with pytest.raises(AuthenticationError, match="Unauthorized"):
            agent_service.list_agents()


@pytest.mark.unit
class TestAgentServiceIntegration:
    """Integration-style tests for AgentService workflows."""

    def test_create_and_get_agent_workflow(
        self, agent_service, mock_http_client, sample_agent_data
    ):
        """Test creating an agent then retrieving it."""
        # Mock creation
        mock_http_client.request.return_value = sample_agent_data

        created_agent = agent_service.create_agent(tools=["google_ads_search"], instructions="Test")

        # Mock retrieval
        retrieved_agent = agent_service.get_agent(created_agent.id)

        assert created_agent.id == retrieved_agent.id
        assert mock_http_client.request.call_count == 2

    def test_list_after_create_workflow(self, agent_service, mock_http_client, sample_agent_data):
        """Test listing agents after creating one."""
        # Create agent
        mock_http_client.request.return_value = sample_agent_data
        agent_service.create_agent(tools=["google_ads_search"], instructions="Test")

        # List agents
        mock_http_client.request.return_value = {"agents": [sample_agent_data]}
        agents = agent_service.list_agents()

        assert len(agents) == 1
        assert agents[0].id == "agent_123"
