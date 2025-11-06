"""Unit tests for Agent class."""

import pytest

from m8tes.agent import Agent, Deployment
from m8tes.exceptions import AgentError
from tests.utils.assertions import (
    assert_event_structure,
    assert_valid_agent_id,
)
from tests.utils.factories import SDKDataFactory


@pytest.mark.unit
class TestAgent:
    """Test cases for Agent class."""

    def test_agent_initialization(self, authenticated_client, mock_agent_data):
        """Test agent initialization with data."""
        agent = Agent(agent_service=authenticated_client.agents, data=mock_agent_data)

        assert agent.agent_service == authenticated_client.agents
        assert agent.id == mock_agent_data["id"]
        assert agent.name == mock_agent_data["name"]
        assert agent.tools == mock_agent_data["tools"]
        assert agent.instructions == mock_agent_data["instructions"]

    def test_agent_initialization_with_minimal_data(self, authenticated_client):
        """Test agent initialization with minimal data."""
        minimal_data = {
            "id": "agent_123",
            "name": "Test Agent",
            "tools": ["google_ads_search"],
            "instructions": "Test instructions",
        }

        agent = Agent(agent_service=authenticated_client.agents, data=minimal_data)

        assert agent.id == "agent_123"
        assert agent.name == "Test Agent"
        assert agent.tools == ["google_ads_search"]
        assert agent.instructions == "Test instructions"

    @pytest.fixture
    def mock_stream_response(self):
        """Mock SSE stream response."""
        return [
            'data: {"type": "start", "timestamp": "2024-01-01T00:00:00Z"}',
            'data: {"type": "thought", "content": "Processing...", "timestamp": "2024-01-01T00:00:01Z"}',  # noqa: E501
            'data: {"type": "complete", "timestamp": "2024-01-01T00:00:02Z"}',
        ]

    def test_agent_run_yields_events(self, mock_agent, mock_stream_response):
        """Test that agent.run() yields events."""

        import responses

        # Mock the streaming endpoint
        with responses.RequestsMock() as rsps:
            # Mock the streaming response
            mock_response_body = "\n".join(mock_stream_response) + "\n"
            rsps.add(
                responses.POST,
                f"https://api.test.m8tes.ai/api/v1/agents/{mock_agent.id}/run",
                body=mock_response_body,
                status=200,
                headers={"Content-Type": "text/event-stream"},
            )

            events = list(mock_agent.run())

            assert len(events) == 3
            assert events[0]["type"] == "start"
            assert events[1]["type"] == "thought"
            assert events[2]["type"] == "complete"
            for event in events:
                assert_event_structure(event, ["type", "timestamp"])

    def test_agent_run_event_types(self, mock_agent, mock_stream_response):
        """Test that agent.run() yields expected event types."""
        import responses

        with responses.RequestsMock() as rsps:
            mock_response_body = "\n".join(mock_stream_response) + "\n"
            rsps.add(
                responses.POST,
                f"https://api.test.m8tes.ai/api/v1/agents/{mock_agent.id}/run",
                body=mock_response_body,
                status=200,
                headers={"Content-Type": "text/event-stream"},
            )

            events = list(mock_agent.run())
            event_types = [event["type"] for event in events]

            assert "start" in event_types
            assert "complete" in event_types

    def test_agent_run_without_id_raises_error(self, authenticated_client):
        """Test that agent.run() raises error when agent has no ID."""
        agent_data = {"name": "Test Agent", "tools": [], "instructions": "Test"}
        agent = Agent(agent_service=authenticated_client.agents, data=agent_data)

        with pytest.raises(AgentError, match="Cannot run agent without an ID"):
            list(agent.run())

    def test_agent_run_with_input_data(self, mock_agent, mock_stream_response):
        """Test agent.run() with input data parameter."""
        import responses

        with responses.RequestsMock() as rsps:
            mock_response_body = "\n".join(mock_stream_response) + "\n"
            rsps.add(
                responses.POST,
                f"https://api.test.m8tes.ai/api/v1/agents/{mock_agent.id}/run",
                body=mock_response_body,
                status=200,
                headers={"Content-Type": "text/event-stream"},
            )

            input_data = {"custom_param": "value"}
            events = list(mock_agent.run(input_data=input_data))

            assert len(events) == 3

    def test_agent_run_with_streaming_disabled(self, mock_agent):
        """Test agent.run() with streaming disabled."""
        from unittest.mock import Mock

        # Mock the HTTP client request method
        mock_response = {"type": "complete", "result": "success"}
        mock_agent.agent_service.http.request = Mock(return_value=mock_response)

        events = list(mock_agent.run(stream=False))

        assert len(events) == 1
        assert events[0] == mock_response

        # Verify the HTTP client was called correctly
        mock_agent.agent_service.http.request.assert_called_once_with(
            "POST", f"/api/v1/agents/{mock_agent.id}/run", json_data={"stream": False}
        )

    def test_agent_deploy_returns_deployment(self, mock_agent):
        """Test that agent.deploy() raises NotImplementedError."""
        with pytest.raises(
            NotImplementedError, match="Deployment functionality is not yet available"
        ):
            mock_agent.deploy(schedule="daily")

    def test_agent_deploy_with_webhook(self, mock_agent):
        """Test agent deployment with webhook URL raises NotImplementedError."""
        webhook_url = "https://example.com/webhook"
        with pytest.raises(
            NotImplementedError, match="Deployment functionality is not yet available"
        ):
            mock_agent.deploy(schedule="hourly", webhook_url=webhook_url, name="Webhook Deployment")

    def test_agent_deploy_without_id_raises_error(self, authenticated_client):
        """Test that agent.deploy() raises error when agent has no ID."""
        agent_data = {"name": "Test Agent", "tools": [], "instructions": "Test"}
        agent = Agent(agent_service=authenticated_client.agents, data=agent_data)

        with pytest.raises(AgentError, match="Cannot deploy agent without an ID"):
            agent.deploy()

    def test_agent_update_returns_self(self, mock_agent):
        """Test that agent.update() raises NotImplementedError."""
        new_name = "Updated Agent"
        with pytest.raises(
            NotImplementedError, match="Agent update functionality is not yet available"
        ):
            mock_agent.update(name=new_name)

    def test_agent_update_tools(self, mock_agent):
        """Test updating agent tools raises NotImplementedError."""
        new_tools = ["google_ads_search", "facebook_ads_insights"]
        with pytest.raises(
            NotImplementedError, match="Agent update functionality is not yet available"
        ):
            mock_agent.update(tools=new_tools)

    def test_agent_update_instructions(self, mock_agent):
        """Test updating agent instructions raises NotImplementedError."""
        new_instructions = "Updated instructions"
        with pytest.raises(
            NotImplementedError, match="Agent update functionality is not yet available"
        ):
            mock_agent.update(instructions=new_instructions)

    def test_agent_delete_returns_true(self, mock_agent):
        """Test that agent.delete() raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="Agent deletion is not yet available"):
            mock_agent.delete()

    def test_agent_delete_without_id_raises_error(self, authenticated_client):
        """Test that agent.delete() raises error when agent has no ID."""
        agent_data = {"name": "Test Agent", "tools": [], "instructions": "Test"}
        agent = Agent(agent_service=authenticated_client.agents, data=agent_data)

        with pytest.raises(AgentError, match="Cannot delete agent without an ID"):
            agent.delete()

    def test_agent_repr(self, mock_agent):
        """Test agent string representation."""
        repr_str = repr(mock_agent)

        assert "Agent" in repr_str
        assert mock_agent.id in repr_str
        assert mock_agent.name in repr_str


@pytest.mark.unit
class TestDeployment:
    """Test cases for Deployment class."""

    def test_deployment_initialization(self, authenticated_client, mock_deployment_data):
        """Test deployment initialization with data."""
        deployment = Deployment(
            agent_service=authenticated_client.agents, data=mock_deployment_data
        )

        assert deployment.agent_service == authenticated_client.agents
        assert deployment.id == mock_deployment_data["id"]
        assert deployment.agent_id == mock_deployment_data["agent_id"]
        assert deployment.name == mock_deployment_data["name"]
        assert deployment.schedule == mock_deployment_data["schedule"]
        assert deployment.status == mock_deployment_data["status"]

    def test_deployment_pause_returns_true(self, authenticated_client, mock_deployment_data):
        """Test that deployment.pause() raises NotImplementedError."""
        deployment = Deployment(
            agent_service=authenticated_client.agents, data=mock_deployment_data
        )

        with pytest.raises(
            NotImplementedError, match="Deployment pause functionality is not yet available"
        ):
            deployment.pause()

    def test_deployment_resume_returns_true(self, authenticated_client, mock_deployment_data):
        """Test that deployment.resume() raises NotImplementedError."""
        deployment = Deployment(
            agent_service=authenticated_client.agents, data=mock_deployment_data
        )
        deployment.status = "inactive"

        with pytest.raises(
            NotImplementedError, match="Deployment resume functionality is not yet available"
        ):
            deployment.resume()

    def test_deployment_delete_returns_true(self, authenticated_client, mock_deployment_data):
        """Test that deployment.delete() raises NotImplementedError."""
        deployment = Deployment(
            agent_service=authenticated_client.agents, data=mock_deployment_data
        )

        with pytest.raises(NotImplementedError, match="Deployment deletion is not yet available"):
            deployment.delete()

    def test_deployment_get_runs_returns_list(self, authenticated_client, mock_deployment_data):
        """Test that deployment.get_runs() raises NotImplementedError."""
        deployment = Deployment(
            agent_service=authenticated_client.agents, data=mock_deployment_data
        )

        with pytest.raises(
            NotImplementedError, match="Deployment run history is not yet available"
        ):
            deployment.get_runs()

    def test_deployment_get_runs_with_limit(self, authenticated_client, mock_deployment_data):
        """Test deployment.get_runs() with limit parameter raises NotImplementedError."""
        deployment = Deployment(
            agent_service=authenticated_client.agents, data=mock_deployment_data
        )

        with pytest.raises(
            NotImplementedError, match="Deployment run history is not yet available"
        ):
            deployment.get_runs(limit=5)

    def test_deployment_repr(self, authenticated_client, mock_deployment_data):
        """Test deployment string representation."""
        deployment = Deployment(
            agent_service=authenticated_client.agents, data=mock_deployment_data
        )
        repr_str = repr(deployment)

        assert "Deployment" in repr_str
        assert deployment.id in repr_str
        assert deployment.agent_id in repr_str
        assert deployment.status in repr_str


@pytest.mark.unit
class TestAgentFactoryIntegration:
    """Test Agent with test data factories."""

    def test_agent_with_factory_data(self, authenticated_client):
        """Test agent creation using data factory."""
        agent_data = SDKDataFactory.create_agent_data(
            name="Factory Agent",
            tools=["google_ads_search", "facebook_ads_insights"],
            instructions="Factory instructions",
        )

        agent = Agent(agent_service=authenticated_client.agents, data=agent_data)

        assert agent.name == "Factory Agent"
        assert agent.tools == ["google_ads_search", "facebook_ads_insights"]
        assert agent.instructions == "Factory instructions"
        assert_valid_agent_id(agent.id)

    def test_deployment_with_factory_data(self, authenticated_client):
        """Test deployment creation using data factory."""
        deployment_data = SDKDataFactory.create_deployment_data(
            name="Factory Deployment", schedule="0 9 * * *"
        )

        deployment = Deployment(agent_service=authenticated_client.agents, data=deployment_data)

        assert deployment.name == "Factory Deployment"
        assert deployment.schedule == "0 9 * * *"


@pytest.mark.integration
class TestAgentIntegration:
    """Integration tests for Agent functionality."""

    @pytest.mark.slow
    def test_agent_full_lifecycle(self, authenticated_client):
        """Test complete agent lifecycle (mocked)."""
        import responses

        # Create agent data
        agent_data = SDKDataFactory.create_agent_data()
        agent = Agent(agent_service=authenticated_client.agents, data=agent_data)

        # Test run with mocked response
        with responses.RequestsMock() as rsps:
            mock_stream_response = [
                'data: {"type": "start", "timestamp": "2024-01-01T00:00:00Z"}',
                'data: {"type": "complete", "timestamp": "2024-01-01T00:00:01Z"}',
            ]
            mock_response_body = "\n".join(mock_stream_response) + "\n"
            rsps.add(
                responses.POST,
                f"https://api.test.m8tes.ai/api/v1/agents/{agent.id}/run",
                body=mock_response_body,
                status=200,
                headers={"Content-Type": "text/event-stream"},
            )

            events = list(agent.run())
            assert len(events) == 2

        # Test deploy - should raise NotImplementedError
        with pytest.raises(NotImplementedError):
            agent.deploy(schedule="daily")

        # Test update - should raise NotImplementedError
        with pytest.raises(NotImplementedError):
            agent.update(name="Updated Name")
