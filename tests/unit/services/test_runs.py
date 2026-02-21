"""
Unit tests for RunService.

Tests the run operations service that handles creating, retrieving, and
managing agent runs through the m8tes API.
"""

from unittest.mock import Mock

import pytest

from m8tes.exceptions import NetworkError, ValidationError
from m8tes.services.runs import RunService


@pytest.fixture
def mock_http_client():
    """Create a mock HTTP client for testing."""
    return Mock()


@pytest.fixture
def run_service(mock_http_client):
    """Create a RunService instance with mocked HTTP client."""
    return RunService(http_client=mock_http_client)


@pytest.fixture
def sample_run_data():
    """Sample run data returned from API."""
    return {
        "id": 456,
        "instance_id": 123,
        "run_mode": "task",
        "description": "Analyze campaigns",
        "status": "completed",
        "created_at": "2024-01-01T00:00:00Z",
        "completed_at": "2024-01-01T00:05:00Z",
    }


@pytest.mark.unit
class TestRunServiceInitialization:
    """Test RunService initialization."""

    def test_initialization_with_http_client(self, mock_http_client):
        """Test that service initializes with HTTP client."""
        service = RunService(http_client=mock_http_client)
        assert service.http == mock_http_client

    def test_initialization_stores_http_reference(self, mock_http_client):
        """Test that HTTP client reference is stored."""
        service = RunService(http_client=mock_http_client)
        assert hasattr(service, "http")
        assert service.http is mock_http_client


@pytest.mark.unit
class TestCreateRun:
    """Test run creation functionality."""

    def test_create_run_with_required_params(self, run_service, mock_http_client, sample_run_data):
        """Test creating run with only required parameters."""
        mock_http_client.request.return_value = sample_run_data

        run = run_service.create(instance_id=123, run_mode="task")

        # Verify API call
        mock_http_client.request.assert_called_once_with(
            "POST",
            "/api/v1/runs",
            json_data={
                "instance_id": 123,
                "run_mode": "task",
            },
        )

        # Verify returned run
        assert run.id == 456
        assert run.run_mode == "task"

    def test_create_run_with_description(self, run_service, mock_http_client, sample_run_data):
        """Test creating run with optional description."""
        mock_http_client.request.return_value = sample_run_data

        run_service.create(instance_id=123, run_mode="chat", description="Customer inquiry")

        # Verify API call includes description
        call_args = mock_http_client.request.call_args[1]["json_data"]
        assert call_args["description"] == "Customer inquiry"

    def test_create_task_run(self, run_service, mock_http_client, sample_run_data):
        """Test creating a task-type run."""
        mock_http_client.request.return_value = sample_run_data

        run_service.create(instance_id=123, run_mode="task")

        call_args = mock_http_client.request.call_args[1]["json_data"]
        assert call_args["run_mode"] == "task"

    def test_create_chat_run(self, run_service, mock_http_client, sample_run_data):
        """Test creating a chat-type run."""
        sample_run_data["run_mode"] = "chat"
        mock_http_client.request.return_value = sample_run_data

        run_service.create(instance_id=123, run_mode="chat")

        call_args = mock_http_client.request.call_args[1]["json_data"]
        assert call_args["run_mode"] == "chat"

    def test_create_run_returns_run_instance(self, run_service, mock_http_client, sample_run_data):
        """Test that create returns a Run instance."""
        mock_http_client.request.return_value = sample_run_data

        run = run_service.create(instance_id=123, run_mode="task")

        from m8tes.run import Run

        assert isinstance(run, Run)

    def test_create_run_handles_validation_error(self, run_service, mock_http_client):
        """Test that validation errors are properly raised."""
        mock_http_client.request.side_effect = ValidationError("Invalid run_mode")

        with pytest.raises(ValidationError, match="Invalid run_mode"):
            run_service.create(instance_id=123, run_mode="invalid")


@pytest.mark.unit
class TestGetRun:
    """Test run retrieval functionality."""

    def test_get_run_by_id(self, run_service, mock_http_client, sample_run_data):
        """Test retrieving a run by ID."""
        mock_http_client.request.return_value = sample_run_data

        run = run_service.get(456)

        # Verify API call
        mock_http_client.request.assert_called_once_with("GET", "/api/v1/runs/456")

        # Verify returned run
        assert run.id == 456
        assert run.instance_id == 123
        assert run.run_mode == "task"

    def test_get_run_with_different_ids(self, run_service, mock_http_client, sample_run_data):
        """Test retrieving runs with different IDs."""
        mock_http_client.request.return_value = sample_run_data

        # Get first run
        run_service.get(456)
        assert "/runs/456" in str(mock_http_client.request.call_args)

        # Get second run
        run_service.get(789)
        assert "/runs/789" in str(mock_http_client.request.call_args)

    def test_get_run_returns_run_instance(self, run_service, mock_http_client, sample_run_data):
        """Test that get returns a Run instance."""
        mock_http_client.request.return_value = sample_run_data

        run = run_service.get(456)

        from m8tes.run import Run

        assert isinstance(run, Run)

    def test_get_run_not_found(self, run_service, mock_http_client):
        """Test getting a non-existent run raises error."""
        mock_http_client.request.side_effect = NetworkError("Run not found")

        with pytest.raises(NetworkError, match="Run not found"):
            run_service.get(999)


@pytest.mark.unit
class TestListForInstance:
    """Test listing runs for an instance."""

    def test_list_for_instance_default_limit(self, run_service, mock_http_client, sample_run_data):
        """Test listing runs with default limit."""
        mock_http_client.request.return_value = [sample_run_data, sample_run_data]

        runs = run_service.list_for_instance(instance_id=123)

        # Verify API call - uses /api/v1/runs with instance_id query param
        mock_http_client.request.assert_called_once_with(
            "GET",
            "/api/v1/runs",
            params={"instance_id": 123, "limit": 50},
        )

        # Verify returned runs
        assert len(runs) == 2

    def test_list_for_instance_custom_limit(self, run_service, mock_http_client, sample_run_data):
        """Test listing runs with custom limit."""
        mock_http_client.request.return_value = [sample_run_data] * 10

        runs = run_service.list_for_instance(instance_id=123, limit=10)

        # Verify API call with custom limit
        mock_http_client.request.assert_called_once_with(
            "GET",
            "/api/v1/runs",
            params={"instance_id": 123, "limit": 10},
        )

        assert len(runs) == 10

    def test_list_for_instance_empty_result(self, run_service, mock_http_client):
        """Test listing runs when no runs exist."""
        mock_http_client.request.return_value = []

        runs = run_service.list_for_instance(instance_id=123)

        assert runs == []
        assert isinstance(runs, list)

    def test_list_for_instance_returns_run_instances(
        self, run_service, mock_http_client, sample_run_data
    ):
        """Test that list_for_instance returns Run instances."""
        mock_http_client.request.return_value = [sample_run_data] * 3

        runs = run_service.list_for_instance(instance_id=123)

        from m8tes.run import Run

        assert all(isinstance(run, Run) for run in runs)

    def test_list_for_instance_handles_missing_runs_key(self, run_service, mock_http_client):
        """Test listing runs when response is an empty list."""
        mock_http_client.request.return_value = []

        runs = run_service.list_for_instance(instance_id=123)

        # Should return empty list
        assert runs == []


@pytest.mark.unit
class TestListUserRuns:
    """Test listing all runs for current user."""

    def test_list_user_runs_default_limit(self, run_service, mock_http_client, sample_run_data):
        """Test listing user runs with default limit."""
        mock_http_client.request.return_value = [sample_run_data] * 5

        runs = run_service.list_user_runs()

        # Verify API call
        mock_http_client.request.assert_called_once_with(
            "GET",
            "/api/v1/runs",
            params={"limit": 50},
        )

        assert len(runs) == 5

    def test_list_user_runs_custom_limit(self, run_service, mock_http_client, sample_run_data):
        """Test listing user runs with custom limit."""
        mock_http_client.request.return_value = [sample_run_data] * 20

        runs = run_service.list_user_runs(limit=20)

        mock_http_client.request.assert_called_once_with(
            "GET",
            "/api/v1/runs",
            params={"limit": 20},
        )

        assert len(runs) == 20

    def test_list_user_runs_empty(self, run_service, mock_http_client):
        """Test listing user runs when none exist."""
        mock_http_client.request.return_value = []

        runs = run_service.list_user_runs()

        assert runs == []

    def test_list_user_runs_returns_run_instances(
        self, run_service, mock_http_client, sample_run_data
    ):
        """Test that list_user_runs returns Run instances."""
        mock_http_client.request.return_value = [sample_run_data] * 3

        runs = run_service.list_user_runs()

        from m8tes.run import Run

        assert all(isinstance(run, Run) for run in runs)


@pytest.mark.unit
class TestGetConversation:
    """Test getting run conversation."""

    def test_get_conversation_success(self, run_service, mock_http_client):
        """Test retrieving conversation messages for a run."""
        messages = [
            {"role": "user", "content": "Show me my campaigns"},
            {"role": "assistant", "content": "I'll help you with that..."},
        ]
        mock_http_client.request.return_value = {"messages": messages}

        result = run_service.get_conversation(456)

        # Verify API call
        mock_http_client.request.assert_called_once_with("GET", "/api/v1/runs/456/conversation")

        # Verify returned messages
        assert result == messages
        assert len(result) == 2

    def test_get_conversation_empty(self, run_service, mock_http_client):
        """Test getting conversation when no messages exist."""
        mock_http_client.request.return_value = {"messages": []}

        result = run_service.get_conversation(456)

        assert result == []

    def test_get_conversation_missing_key(self, run_service, mock_http_client):
        """Test getting conversation when messages key is missing."""
        mock_http_client.request.return_value = {}

        result = run_service.get_conversation(456)

        assert result == []


@pytest.mark.unit
class TestGetUsage:
    """Test getting run usage statistics."""

    def test_get_usage_success(self, run_service, mock_http_client):
        """Test retrieving usage statistics for a run."""
        usage_data = {
            "prompt_tokens": 150,
            "completion_tokens": 75,
            "total_tokens": 225,
            "estimated_cost": 0.005,
        }
        mock_http_client.request.return_value = usage_data

        result = run_service.get_usage(456)

        # Verify API call
        mock_http_client.request.assert_called_once_with("GET", "/api/v1/runs/456/usage")

        # Verify returned usage data
        assert result == usage_data
        assert result["total_tokens"] == 225

    def test_get_usage_different_runs(self, run_service, mock_http_client):
        """Test getting usage for different run IDs."""
        mock_http_client.request.return_value = {"total_tokens": 100}

        run_service.get_usage(456)
        assert "/runs/456/usage" in str(mock_http_client.request.call_args)

        run_service.get_usage(789)
        assert "/runs/789/usage" in str(mock_http_client.request.call_args)


@pytest.mark.unit
class TestGetToolExecutions:
    """Test getting tool execution history."""

    def test_get_tool_executions_success(self, run_service, mock_http_client):
        """Test retrieving tool execution history for a run."""
        executions = [
            {
                "tool_name": "run_gaql_query",
                "arguments": {"query": "SELECT..."},
                "result": {"rows": [{"campaign": {"name": "Test"}}]},
                "timestamp": "2024-01-01T00:01:00Z",
            }
        ]
        mock_http_client.request.return_value = {"executions": executions}

        result = run_service.get_tool_executions(456)

        # Verify API call
        mock_http_client.request.assert_called_once_with("GET", "/api/v1/runs/456/tools")

        # Verify returned executions
        assert result == executions
        assert len(result) == 1

    def test_get_tool_executions_empty(self, run_service, mock_http_client):
        """Test getting tool executions when none exist."""
        mock_http_client.request.return_value = {"executions": []}

        result = run_service.get_tool_executions(456)

        assert result == []

    def test_get_tool_executions_missing_key(self, run_service, mock_http_client):
        """Test getting tool executions when key is missing."""
        mock_http_client.request.return_value = {}

        result = run_service.get_tool_executions(456)

        assert result == []


@pytest.mark.unit
class TestGetDetails:
    """Test getting comprehensive run details."""

    def test_get_details_success(self, run_service, mock_http_client):
        """Test retrieving comprehensive run details."""
        details = {
            "run": {
                "id": 456,
                "status": "completed",
            },
            "conversation": [{"role": "user", "content": "Hello"}],
            "usage": {"total_tokens": 100},
            "tool_executions": [{"tool_name": "run_gaql_query"}],
        }
        mock_http_client.request.return_value = details

        result = run_service.get_details(456)

        # Verify API call
        mock_http_client.request.assert_called_once_with("GET", "/api/v1/runs/456/details")

        # Verify returned details
        assert result == details
        assert "conversation" in result
        assert "usage" in result
        assert "tool_executions" in result

    def test_get_details_different_runs(self, run_service, mock_http_client):
        """Test getting details for different run IDs."""
        mock_http_client.request.return_value = {}

        run_service.get_details(456)
        assert "/runs/456/details" in str(mock_http_client.request.call_args)

        run_service.get_details(789)
        assert "/runs/789/details" in str(mock_http_client.request.call_args)


@pytest.mark.unit
class TestRunServiceIntegration:
    """Integration-style tests for RunService workflows."""

    def test_create_and_get_run_workflow(self, run_service, mock_http_client, sample_run_data):
        """Test creating a run then retrieving it."""
        # Mock creation
        mock_http_client.request.return_value = sample_run_data

        created_run = run_service.create(instance_id=123, run_mode="task")

        # Mock retrieval
        retrieved_run = run_service.get(created_run.id)

        assert created_run.id == retrieved_run.id
        assert mock_http_client.request.call_count == 2

    def test_create_then_get_conversation_workflow(
        self, run_service, mock_http_client, sample_run_data
    ):
        """Test creating a run then getting its conversation."""
        # Create
        mock_http_client.request.return_value = sample_run_data
        run = run_service.create(instance_id=123, run_mode="chat")

        # Get conversation
        mock_http_client.request.return_value = {"messages": [{"role": "user", "content": "Hello"}]}
        conversation = run_service.get_conversation(run.id)

        assert len(conversation) == 1
        assert mock_http_client.request.call_count == 2

    def test_create_then_get_usage_workflow(self, run_service, mock_http_client, sample_run_data):
        """Test creating a run then getting its usage."""
        # Create
        mock_http_client.request.return_value = sample_run_data
        run = run_service.create(instance_id=123, run_mode="task")

        # Get usage
        mock_http_client.request.return_value = {"total_tokens": 500}
        usage = run_service.get_usage(run.id)

        assert usage["total_tokens"] == 500
        assert mock_http_client.request.call_count == 2
