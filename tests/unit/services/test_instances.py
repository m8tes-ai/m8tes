"""
Unit tests for InstanceService.

Tests the instance operations service that handles creating, retrieving, and
managing agent instances through the m8tes API.
"""

from unittest.mock import Mock

import pytest

from m8tes.exceptions import NetworkError, ValidationError
from m8tes.services.instances import InstanceService


@pytest.fixture
def mock_http_client():
    """Create a mock HTTP client for testing."""
    return Mock()


@pytest.fixture
def instance_service(mock_http_client):
    """Create an InstanceService instance with mocked HTTP client."""
    return InstanceService(http_client=mock_http_client)


@pytest.fixture
def sample_instance_data():
    """Sample instance data returned from API."""
    return {
        "id": 123,
        "name": "Campaign Manager",
        "tools": ["run_gaql_query", "google_ads_search"],
        "instructions": "Manage Google Ads campaigns",
        "agent_type": "marketing",
        "user_instructions": None,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }


@pytest.mark.unit
class TestInstanceServiceInitialization:
    """Test InstanceService initialization."""

    def test_initialization_with_http_client(self, mock_http_client):
        """Test that service initializes with HTTP client."""
        service = InstanceService(http_client=mock_http_client)
        assert service.http == mock_http_client

    def test_initialization_stores_http_reference(self, mock_http_client):
        """Test that HTTP client reference is stored."""
        service = InstanceService(http_client=mock_http_client)
        assert hasattr(service, "http")
        assert service.http is mock_http_client


@pytest.mark.unit
class TestCreateInstance:
    """Test instance creation functionality."""

    def test_create_instance_with_required_params(
        self, instance_service, mock_http_client, sample_instance_data
    ):
        """Test creating instance with only required parameters."""
        mock_http_client.request.return_value = sample_instance_data

        name = "Campaign Manager"
        tools = ["run_gaql_query"]
        instructions = "Manage campaigns"

        instance = instance_service.create(name=name, tools=tools, instructions=instructions)

        # Verify API call
        mock_http_client.request.assert_called_once_with(
            "POST",
            "/api/v1/agents/instances",
            json_data={
                "name": name,
                "tools": tools,
                "instructions": instructions,
                "agent_type": "marketing",
            },
        )

        # Verify returned instance
        assert instance.id == 123
        assert instance.name == "Campaign Manager"

    def test_create_instance_with_all_params(
        self, instance_service, mock_http_client, sample_instance_data
    ):
        """Test creating instance with all optional parameters."""
        mock_http_client.request.return_value = sample_instance_data

        name = "Campaign Manager"
        tools = ["run_gaql_query"]
        instructions = "Manage campaigns"
        agent_type = "analytics"
        user_instructions = "Be concise"

        instance_service.create(
            name=name,
            tools=tools,
            instructions=instructions,
            agent_type=agent_type,
            user_instructions=user_instructions,
        )

        # Verify API call includes all parameters
        mock_http_client.request.assert_called_once_with(
            "POST",
            "/api/v1/agents/instances",
            json_data={
                "name": name,
                "tools": tools,
                "instructions": instructions,
                "agent_type": agent_type,
                "user_instructions": user_instructions,
            },
        )

    def test_create_instance_with_user_instructions_only(
        self, instance_service, mock_http_client, sample_instance_data
    ):
        """Test creating instance with user_instructions."""
        mock_http_client.request.return_value = sample_instance_data

        instance_service.create(
            name="Test",
            tools=["tool1"],
            instructions="Do stuff",
            user_instructions="Be helpful",
        )

        call_args = mock_http_client.request.call_args[1]["json_data"]
        assert "user_instructions" in call_args

    def test_create_instance_returns_instance_object(
        self, instance_service, mock_http_client, sample_instance_data
    ):
        """Test that create returns an AgentInstance instance."""
        mock_http_client.request.return_value = sample_instance_data

        instance = instance_service.create(name="Test", tools=["tool1"], instructions="Test")

        from m8tes.instance import AgentInstance

        assert isinstance(instance, AgentInstance)

    def test_create_instance_handles_validation_error(self, instance_service, mock_http_client):
        """Test that validation errors are properly raised."""
        mock_http_client.request.side_effect = ValidationError("Invalid tools")

        with pytest.raises(ValidationError, match="Invalid tools"):
            instance_service.create(name="Test", tools=["invalid"], instructions="Test")


@pytest.mark.unit
class TestGetInstance:
    """Test instance retrieval functionality."""

    def test_get_instance_by_id(self, instance_service, mock_http_client, sample_instance_data):
        """Test retrieving an instance by ID."""
        mock_http_client.request.return_value = sample_instance_data

        instance = instance_service.get(123)

        # Verify API call
        mock_http_client.request.assert_called_once_with("GET", "/api/v1/agents/instances/123")

        # Verify returned instance
        assert instance.id == 123
        assert instance.name == "Campaign Manager"

    def test_get_instance_with_different_ids(
        self, instance_service, mock_http_client, sample_instance_data
    ):
        """Test retrieving instances with different IDs."""
        mock_http_client.request.return_value = sample_instance_data

        # Get first instance
        instance_service.get(123)
        assert "/instances/123" in str(mock_http_client.request.call_args)

        # Get second instance
        instance_service.get(456)
        assert "/instances/456" in str(mock_http_client.request.call_args)

    def test_get_instance_returns_instance_object(
        self, instance_service, mock_http_client, sample_instance_data
    ):
        """Test that get returns an AgentInstance instance."""
        mock_http_client.request.return_value = sample_instance_data

        instance = instance_service.get(123)

        from m8tes.instance import AgentInstance

        assert isinstance(instance, AgentInstance)

    def test_get_instance_not_found(self, instance_service, mock_http_client):
        """Test getting a non-existent instance raises error."""
        from m8tes.exceptions import NetworkError

        mock_http_client.request.side_effect = NetworkError("Instance not found")

        with pytest.raises(NetworkError, match="Instance not found"):
            instance_service.get(999)


@pytest.mark.unit
class TestListInstances:
    """Test instance listing functionality."""

    def test_list_instances_default(self, instance_service, mock_http_client, sample_instance_data):
        """Test listing instances with default parameters."""
        # API returns a list directly, not a dict with "instances" key
        mock_http_client.request.return_value = [sample_instance_data, sample_instance_data]

        instances = instance_service.list()

        # Verify API call
        mock_http_client.request.assert_called_once_with(
            "GET",
            "/api/v1/agents/instances",
            params={"include_disabled": "false", "include_archived": "false"},
        )

        # Verify returned instances
        assert len(instances) == 2
        assert all(inst.id == 123 for inst in instances)

    def test_list_instances_include_archived(
        self, instance_service, mock_http_client, sample_instance_data
    ):
        """Test listing instances including archived ones."""
        # API returns a list directly, not a dict with "instances" key
        mock_http_client.request.return_value = [sample_instance_data]

        instance_service.list(include_archived=True)

        # Verify API call includes archived
        mock_http_client.request.assert_called_once_with(
            "GET",
            "/api/v1/agents/instances",
            params={"include_disabled": "false", "include_archived": "true"},
        )

    def test_list_instances_empty_result(self, instance_service, mock_http_client):
        """Test listing instances when no instances exist."""
        # API returns a list directly, not a dict with "instances" key
        mock_http_client.request.return_value = []

        instances = instance_service.list()

        assert instances == []
        assert isinstance(instances, list)

    def test_list_instances_returns_instance_objects(
        self, instance_service, mock_http_client, sample_instance_data
    ):
        """Test that list returns AgentInstance instances."""
        # API returns a list directly, not a dict with "instances" key
        mock_http_client.request.return_value = [sample_instance_data, sample_instance_data]

        instances = instance_service.list()

        from m8tes.instance import AgentInstance

        assert all(isinstance(inst, AgentInstance) for inst in instances)

    def test_list_instances_without_credentials(self, instance_service, mock_http_client):
        """Test list raises AuthenticationError when no credentials provided."""
        from m8tes.exceptions import AuthenticationError

        mock_http_client.request.side_effect = AuthenticationError(
            "Not authenticated. Please login first with 'm8tes auth login' or set "
            "M8TES_API_KEY environment variable.",
            code="no_credentials",
        )

        with pytest.raises(AuthenticationError, match="Not authenticated"):
            instance_service.list()


@pytest.mark.unit
class TestUpdateInstance:
    """Test instance update functionality."""

    def test_update_instance_name_only(
        self, instance_service, mock_http_client, sample_instance_data
    ):
        """Test updating only the instance name."""
        mock_http_client.request.return_value = sample_instance_data

        instance_service.update(instance_id=123, name="New Name")

        # Verify API call
        mock_http_client.request.assert_called_once_with(
            "PATCH",
            "/api/v1/agents/instances/123",
            json_data={"name": "New Name"},
        )

    def test_update_instance_instructions_only(
        self, instance_service, mock_http_client, sample_instance_data
    ):
        """Test updating only the instance instructions."""
        mock_http_client.request.return_value = sample_instance_data
        new_instructions = "Updated instructions"

        instance_service.update(instance_id=123, instructions=new_instructions)

        # Verify API call
        mock_http_client.request.assert_called_once_with(
            "PATCH",
            "/api/v1/agents/instances/123",
            json_data={"instructions": new_instructions},
        )

    def test_update_instance_both_fields(
        self, instance_service, mock_http_client, sample_instance_data
    ):
        """Test updating both name and instructions."""
        mock_http_client.request.return_value = sample_instance_data
        new_instructions = "Updated instructions"

        instance_service.update(instance_id=123, name="New Name", instructions=new_instructions)

        # Verify API call includes both fields
        call_args = mock_http_client.request.call_args[1]["json_data"]
        assert call_args["name"] == "New Name"
        assert call_args["instructions"] == new_instructions

    def test_update_instance_no_fields_raises_error(self, instance_service):
        """Test that updating with no fields raises ValueError."""
        with pytest.raises(ValueError, match="At least one field must be provided"):
            instance_service.update(instance_id=123)

    def test_update_instance_returns_instance_object(
        self, instance_service, mock_http_client, sample_instance_data
    ):
        """Test that update returns an AgentInstance instance."""
        mock_http_client.request.return_value = sample_instance_data

        instance = instance_service.update(instance_id=123, name="New Name")

        from m8tes.instance import AgentInstance

        assert isinstance(instance, AgentInstance)


@pytest.mark.unit
class TestArchiveInstance:
    """Test instance archiving functionality."""

    def test_archive_instance_success(self, instance_service, mock_http_client):
        """Test archiving an instance."""
        # Mock 204 NO_CONTENT response (HTTP client returns {"success": True})
        mock_http_client.request.return_value = {"success": True}

        result = instance_service.archive(instance_id=123)

        # Verify API call
        mock_http_client.request.assert_called_once_with("DELETE", "/api/v1/agents/instances/123")

        # Verify returns True
        assert result is True

    def test_archive_instance_with_different_ids(self, instance_service, mock_http_client):
        """Test archiving instances with different IDs."""
        # Mock 204 NO_CONTENT response
        mock_http_client.request.return_value = {"success": True}

        instance_service.archive(123)
        assert "/instances/123" in str(mock_http_client.request.call_args)

        instance_service.archive(456)
        assert "/instances/456" in str(mock_http_client.request.call_args)

    def test_archive_instance_handles_error(self, instance_service, mock_http_client):
        """Test that archiving errors are properly raised."""
        mock_http_client.request.side_effect = NetworkError("Archive failed")

        with pytest.raises(NetworkError, match="Archive failed"):
            instance_service.archive(123)


@pytest.mark.unit
class TestInstanceServiceIntegration:
    """Integration-style tests for InstanceService workflows."""

    def test_create_and_get_instance_workflow(
        self, instance_service, mock_http_client, sample_instance_data
    ):
        """Test creating an instance then retrieving it."""
        # Mock creation
        mock_http_client.request.return_value = sample_instance_data

        created_instance = instance_service.create(
            name="Test", tools=["tool1"], instructions="Test"
        )

        # Mock retrieval
        retrieved_instance = instance_service.get(created_instance.id)

        assert created_instance.id == retrieved_instance.id
        assert mock_http_client.request.call_count == 2

    def test_create_update_workflow(self, instance_service, mock_http_client, sample_instance_data):
        """Test creating then updating an instance."""
        # Create
        mock_http_client.request.return_value = sample_instance_data
        instance = instance_service.create(name="Original", tools=["tool1"], instructions="Test")

        # Update
        instance_service.update(instance_id=instance.id, name="Updated")

        assert mock_http_client.request.call_count == 2
        # Verify update call
        assert mock_http_client.request.call_args_list[1][0][0] == "PATCH"

    def test_list_then_archive_workflow(
        self, instance_service, mock_http_client, sample_instance_data
    ):
        """Test listing instances then archiving one."""
        # List - API returns a list directly, not a dict with "instances" key
        # Archive - API returns success dict
        mock_http_client.request.side_effect = [
            [sample_instance_data],  # List response
            {"success": True},  # Archive response
        ]
        instances = instance_service.list()

        # Archive first instance
        result = instance_service.archive(instances[0].id)

        assert result is True
        assert mock_http_client.request.call_count == 2


@pytest.mark.unit
class TestAutoDetectInstance:
    """Test instance auto-detection functionality."""

    def test_auto_detect_with_last_used(
        self, instance_service, mock_http_client, sample_instance_data
    ):
        """Test auto-detect returns most recently used instance."""
        # Mock API response with reason=last_used
        response_data = {
            "agent": sample_instance_data,
            "reason": "last_used",
            "last_used_at": "2024-01-15T10:30:00Z",
        }
        mock_http_client.request.return_value = response_data

        instance, metadata = instance_service.auto_detect()

        # Verify API call
        mock_http_client.request.assert_called_once_with(
            "GET", "/api/v1/agents/instances/auto-detect"
        )

        # Verify returned instance
        from m8tes.instance import AgentInstance

        assert isinstance(instance, AgentInstance)
        assert instance.id == 123
        assert instance.name == "Campaign Manager"

        # Verify metadata
        assert metadata["reason"] == "last_used"
        assert metadata["last_used_at"] == "2024-01-15T10:30:00Z"

    def test_auto_detect_with_last_created(
        self, instance_service, mock_http_client, sample_instance_data
    ):
        """Test auto-detect falls back to last created when no runs exist."""
        # Mock API response with reason=last_created
        response_data = {
            "agent": sample_instance_data,
            "reason": "last_created",
            "last_used_at": None,
        }
        mock_http_client.request.return_value = response_data

        instance, metadata = instance_service.auto_detect()

        # Verify returned instance
        assert instance.id == 123

        # Verify metadata
        assert metadata["reason"] == "last_created"
        assert metadata["last_used_at"] is None

    def test_auto_detect_returns_correct_tuple(
        self, instance_service, mock_http_client, sample_instance_data
    ):
        """Test that auto_detect returns (instance, metadata) tuple."""
        response_data = {
            "agent": sample_instance_data,
            "reason": "last_used",
            "last_used_at": "2024-01-15T10:30:00Z",
        }
        mock_http_client.request.return_value = response_data

        result = instance_service.auto_detect()

        # Verify tuple structure
        assert isinstance(result, tuple)
        assert len(result) == 2

        instance, metadata = result
        from m8tes.instance import AgentInstance

        assert isinstance(instance, AgentInstance)
        assert isinstance(metadata, dict)

    def test_auto_detect_no_enabled_agents(self, instance_service, mock_http_client):
        """Test auto-detect raises error when no enabled agents exist."""
        from m8tes.exceptions import ValidationError

        mock_http_client.request.side_effect = ValidationError("No enabled agents found")

        with pytest.raises(ValidationError, match="No enabled agents found"):
            instance_service.auto_detect()

    def test_auto_detect_metadata_structure(
        self, instance_service, mock_http_client, sample_instance_data
    ):
        """Test that metadata contains all expected fields."""
        response_data = {
            "agent": sample_instance_data,
            "reason": "last_used",
            "last_used_at": "2024-01-15T10:30:00Z",
        }
        mock_http_client.request.return_value = response_data

        instance, metadata = instance_service.auto_detect()

        # Verify metadata keys
        assert "reason" in metadata
        assert "last_used_at" in metadata
        assert metadata["reason"] in ["last_used", "last_created"]

    def test_auto_detect_without_credentials(self, instance_service, mock_http_client):
        """Test auto-detect raises AuthenticationError when no credentials provided."""
        from m8tes.exceptions import AuthenticationError

        mock_http_client.request.side_effect = AuthenticationError(
            "Not authenticated. Please login first with 'm8tes auth login' or set "
            "M8TES_API_KEY environment variable.",
            code="no_credentials",
        )

        with pytest.raises(AuthenticationError, match="Not authenticated"):
            instance_service.auto_detect()
