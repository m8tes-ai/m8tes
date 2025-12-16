"""Unit tests for M8tes client class."""

from unittest.mock import Mock, patch

import pytest

from m8tes import M8tes
from m8tes.exceptions import AuthenticationError, NetworkError, ValidationError
from tests.utils.assertions import assert_valid_agent_id
from tests.utils.mocks import mock_environment_variables


@pytest.mark.unit
class TestM8tesClient:
    """Test cases for M8tes client initialization and configuration."""

    def test_initialization_with_api_key(self, api_key, base_url):
        """Test client initialization with provided API key."""
        client = M8tes(api_key=api_key, base_url=base_url)

        assert client.api_key == api_key
        assert client.base_url == base_url
        assert client.timeout == 30  # default
        assert client._session is not None

    def test_initialization_with_timeout(self, api_key):
        """Test client initialization with custom timeout."""
        timeout = 60
        client = M8tes(api_key=api_key, timeout=timeout)

        assert client.timeout == timeout

    @mock_environment_variables(M8TES_API_KEY="env-api-key")
    @patch("m8tes.auth.credentials.CredentialManager.get_api_key")
    def test_initialization_from_environment(self, mock_get_api_key):
        """Test client initialization using environment variables."""
        # Mock keychain to return None so env var is used
        mock_get_api_key.return_value = None

        client = M8tes()

        assert client.api_key == "env-api-key"
        assert "https://www.m8tes.ai" in client.base_url

    @mock_environment_variables(M8TES_API_KEY="env-key", M8TES_BASE_URL="https://custom.api.com")
    @patch("m8tes.auth.credentials.CredentialManager.get_api_key")
    def test_initialization_from_environment_with_custom_url(self, mock_get_api_key):
        """Test client initialization with custom base URL from environment."""
        # Mock keychain to return None so env var is used
        mock_get_api_key.return_value = None

        client = M8tes()

        assert client.api_key == "env-key"
        assert client.base_url == "https://custom.api.com"

    @patch("m8tes.auth.credentials.CredentialManager.get_api_key")
    def test_initialization_without_api_key_allows_unauthenticated_operations(
        self, mock_get_api_key
    ):
        """Test that client can be initialized without API key for unauthenticated operations."""
        # Mock keychain to return None and no env var
        mock_get_api_key.return_value = None

        # Client should initialize successfully without API key
        client = M8tes()
        assert client.api_key is None

    def test_initialization_with_empty_api_key_stores_empty_string(self):
        """Test that client can be initialized with empty API key."""
        client = M8tes(api_key="")
        assert client.api_key == ""

    def test_session_headers_are_set_correctly(self, authenticated_client):
        """Test that HTTP session has correct headers."""
        session = authenticated_client._session

        assert "Authorization" in session.headers
        assert session.headers["Authorization"].startswith("Bearer ")
        assert session.headers["Content-Type"] == "application/json"
        assert "m8tes-python-sdk" in session.headers["User-Agent"]


@pytest.mark.unit
class TestM8tesAgentOperations:
    """Test cases for agent-related operations."""

    def test_create_agent_returns_agent_instance(self, authenticated_client, mock_agent_data):
        """Test that create_agent returns an Agent instance."""
        from unittest.mock import Mock

        tools = ["google_ads_search", "google_ads_negatives"]
        instructions = "Test instructions"

        # Mock the HTTP client's request method
        authenticated_client.agents.http.request = Mock(return_value=mock_agent_data)

        agent = authenticated_client.create_agent(
            tools=tools, instructions=instructions, name="Test Agent"
        )

        assert agent is not None
        assert agent.tools == tools
        assert agent.instructions == instructions
        assert agent.name == "Test Agent"
        assert_valid_agent_id(agent.id)

        # Verify the HTTP request was made correctly
        authenticated_client.agents.http.request.assert_called_once_with(
            "POST",
            "/api/v1/agents",
            json_data={"tools": tools, "instructions": instructions, "name": "Test Agent"},
        )

    def test_create_agent_with_minimal_params(self, authenticated_client, mock_agent_data):
        """Test creating agent with only required parameters."""
        from unittest.mock import Mock

        # Mock the HTTP client's request method
        authenticated_client.agents.http.request = Mock(return_value=mock_agent_data)

        agent = authenticated_client.create_agent(
            tools=["google_ads_search"], instructions="Test instructions"
        )

        # Agent is constructed from mock_agent_data response
        assert agent.tools == mock_agent_data["tools"]
        assert agent.instructions == "Test instructions"
        assert agent.name  # Should have a default name

    def test_get_agent_returns_agent_instance(self, authenticated_client, mock_agent_data):
        """Test that get_agent returns an Agent instance."""
        from unittest.mock import Mock

        agent_id = "agent_123"

        # Mock the HTTP client's request method
        authenticated_client.agents.http.request = Mock(return_value=mock_agent_data)

        agent = authenticated_client.get_agent(agent_id)

        assert agent is not None
        assert agent.id == agent_id

    def test_list_agents_returns_list(self, authenticated_client):
        """Test that list_agents returns a list."""
        from unittest.mock import Mock

        # Mock the HTTP client's request method to return response with agents list
        authenticated_client.agents.http.request = Mock(return_value={"agents": []})

        agents = authenticated_client.list_agents()

        assert isinstance(agents, list)

    def test_list_agents_with_limit(self, authenticated_client):
        """Test that list_agents respects limit parameter."""
        from unittest.mock import Mock

        limit = 5
        # Mock the HTTP client's request method to return response with agents list
        authenticated_client.agents.http.request = Mock(return_value={"agents": []})

        agents = authenticated_client.list_agents(limit=limit)

        assert isinstance(agents, list)


@pytest.mark.unit
class TestM8tesGoogleAuth:
    """Test cases for Google authentication operations."""

    def test_google_auth_property_returns_google_auth_instance(self, authenticated_client):
        """Test that google property returns GoogleAuth instance."""
        google_auth = authenticated_client.google

        assert google_auth is not None
        assert google_auth.client == authenticated_client

    def test_google_start_connect_placeholder(self, authenticated_client):
        """Test Google OAuth start connection placeholder."""
        from unittest.mock import Mock

        redirect_uri = "http://localhost:8000/callback"

        # Mock the HTTP client's post method
        mock_result = {
            "authorization_url": "https://accounts.google.com/oauth/authorize?...",
            "state": "test-state-123",
            "expires_in": 600,
        }
        authenticated_client.integrations.google.http.post = Mock(return_value=mock_result)

        # This tests the current placeholder implementation
        result = authenticated_client.google.start_connect(redirect_uri=redirect_uri)

        assert isinstance(result, dict)

    def test_google_finish_connect_placeholder(self, authenticated_client):
        """Test Google OAuth finish connection placeholder."""
        from unittest.mock import Mock

        code = "test-auth-code"
        state = "test-state"
        redirect_uri = "http://localhost:8000/callback"

        # Mock the HTTP client's post method
        mock_result = {"status": "connected", "account": "test@example.com"}
        authenticated_client.integrations.google.http.post = Mock(return_value=mock_result)

        # This tests the current placeholder implementation
        result = authenticated_client.google.finish_connect(
            code=code, state=state, redirect_uri=redirect_uri
        )

        assert isinstance(result, dict)

    def test_google_list_accessible_customers(self, authenticated_client):
        """Test listing accessible customers without refresh."""
        from unittest.mock import Mock

        mock_response = {"accessible_customers": ["1234567890"], "refreshed": False}
        authenticated_client.integrations.google.http.get = Mock(return_value=mock_response)

        result = authenticated_client.google.list_accessible_customers()

        authenticated_client.integrations.google.http.get.assert_called_once_with(
            "/api/v1/integrations/google-ads/customers",
            params={"refresh": "false"},
        )
        assert result == mock_response

    def test_google_list_accessible_customers_with_refresh(self, authenticated_client):
        """Test listing accessible customers with refresh parameter."""
        from unittest.mock import Mock

        mock_response = {"accessible_customers": ["1234567890"], "refreshed": True}
        authenticated_client.integrations.google.http.get = Mock(return_value=mock_response)

        result = authenticated_client.google.list_accessible_customers(refresh=True)

        authenticated_client.integrations.google.http.get.assert_called_once_with(
            "/api/v1/integrations/google-ads/customers",
            params={"refresh": "true"},
        )
        assert result == mock_response

    def test_google_set_customer_id(self, authenticated_client):
        """Test setting the Google Ads customer ID with integration reference."""
        from unittest.mock import Mock

        mock_response = {"success": True, "customer_id": "1234567890"}
        authenticated_client.integrations.google.http.put = Mock(return_value=mock_response)

        result = authenticated_client.google.set_customer_id("123-456-7890", integration_id=42)

        authenticated_client.integrations.google.http.put.assert_called_once_with(
            "/api/v1/integrations/google-ads/customer-id",
            json_data={"customer_id": "1234567890", "integration_id": 42},
        )
        assert result == mock_response


@pytest.mark.unit
class TestM8tesMetaAuth:
    """Test cases for Meta Ads authentication helpers."""

    def test_meta_auth_property_returns_meta_auth_instance(self, authenticated_client):
        """Meta property should yield MetaAuth bound to client."""
        meta_auth = authenticated_client.meta

        assert meta_auth is not None
        assert meta_auth.client == authenticated_client

    def test_meta_start_connect(self, authenticated_client):
        """Meta start_connect forwards payload to backend."""
        from unittest.mock import Mock

        mock_response = {
            "authorization_url": "https://facebook.com/oauth",
            "state": "state-123",
            "expires_in": 600,
        }

        meta_auth = authenticated_client.meta
        meta_auth.http.post = Mock(return_value=mock_response)

        result = meta_auth.start_connect(redirect_uri="https://localhost:8080/callback")

        assert result["authorization_url"] == mock_response["authorization_url"]
        meta_auth.http.post.assert_called_once_with(
            "/api/v1/integrations/meta-ads/auth/init",
            json_data={"redirect_uri": "https://localhost:8080/callback"},
        )

    def test_meta_finish_connect(self, authenticated_client):
        """Meta finish_connect should include optional fields when provided."""
        from unittest.mock import Mock

        meta_auth = authenticated_client.meta
        meta_auth.http.post = Mock(return_value={"success": True, "integration_id": 9})

        result = meta_auth.finish_connect(
            code="auth-code",
            state="state-123",
            redirect_uri="https://localhost:8080/callback",
            email="sdk@example.com",
        )

        assert result["success"] is True
        meta_auth.http.post.assert_called_once_with(
            "/api/v1/integrations/meta-ads/auth/callback",
            json_data={
                "code": "auth-code",
                "state": "state-123",
                "redirect_uri": "https://localhost:8080/callback",
                "email": "sdk@example.com",
            },
        )

    def test_meta_get_status(self, authenticated_client):
        """Meta status helper should query backend endpoint."""
        from unittest.mock import Mock

        meta_auth = authenticated_client.meta
        meta_auth.http.get = Mock(return_value={"has_integration": False})

        status = meta_auth.get_status()

        assert status["has_integration"] is False
        meta_auth.http.get.assert_called_once_with("/api/v1/integrations/meta-ads/status")

    def test_meta_disconnect(self, authenticated_client):
        """Meta disconnect helper should call DELETE endpoint."""
        from unittest.mock import Mock

        meta_auth = authenticated_client.meta
        meta_auth.http.delete = Mock(return_value={"success": True})

        response = meta_auth.disconnect()

        assert response["success"] is True
        meta_auth.http.delete.assert_called_once_with("/api/v1/integrations/meta-ads")


@pytest.mark.unit
class TestM8tesErrorHandling:
    """Test cases for error handling in client requests."""

    def test_request_method_handles_timeout(self, authenticated_client):
        """Test that _request method handles timeout errors."""
        with patch.object(authenticated_client._session, "request") as mock_request:
            mock_request.side_effect = Exception("Connection timeout")

            # This will be tested once actual _request implementation is added
            # Currently placeholder implementations don't use _request
            pass

    def test_session_retry_configuration(self, authenticated_client):
        """Test that session has retry configuration."""
        session = authenticated_client._session

        # Check that session has adapters with retry configuration
        assert "http://" in session.adapters
        assert "https://" in session.adapters

        # Adapters should have retry configuration
        http_adapter = session.adapters["http://"]
        https_adapter = session.adapters["https://"]

        assert http_adapter.max_retries is not None
        assert https_adapter.max_retries is not None


@pytest.mark.unit
class TestM8tesRequestMethod:
    """Test cases for the internal _request method."""

    @patch("m8tes.http.client.HTTPClient._ensure_valid_token")
    @patch("requests.Session.request")
    def test_request_success(self, mock_request, mock_ensure_token, authenticated_client):
        """Test successful request handling."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success", "data": {}}
        # Mock headers.get to return appropriate values
        mock_response.headers.get.side_effect = lambda key, default="": {
            "Content-Type": "application/json",
            "Server": "m8tes-api",
        }.get(key, default)
        mock_request.return_value = mock_response

        result = authenticated_client._request("GET", "/test")

        assert result == {"status": "success", "data": {}}
        mock_request.assert_called_once()

    @patch("requests.Session.request")
    def test_request_authentication_error(self, mock_request, authenticated_client):
        """Test 401 authentication error handling."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.headers.get.side_effect = lambda key, default="": {
            "Content-Type": "application/json",
            "Server": "m8tes-api",
        }.get(key, default)
        mock_request.return_value = mock_response

        with pytest.raises(AuthenticationError, match="Invalid API key"):
            authenticated_client._request("GET", "/test")

    @patch("requests.Session.request")
    def test_request_validation_error(self, mock_request, authenticated_client):
        """Test 400 validation error handling."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": "validation_error", "message": "Invalid input"}
        mock_response.headers.get.side_effect = lambda key, default="": {
            "Content-Type": "application/json",
            "Server": "m8tes-api",
        }.get(key, default)
        mock_request.return_value = mock_response

        with pytest.raises(ValidationError, match="Invalid input"):
            authenticated_client._request("POST", "/test")

    @patch("requests.Session.request")
    def test_request_network_error(self, mock_request, authenticated_client):
        """Test 500 server error handling."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.headers.get.side_effect = lambda key, default="": {
            "Content-Type": "application/json",
            "Server": "m8tes-api",
        }.get(key, default)
        mock_request.return_value = mock_response

        with pytest.raises(NetworkError, match="Server error"):
            authenticated_client._request("GET", "/test")


@pytest.mark.integration
class TestM8tesIntegration:
    """Integration tests requiring external services (mocked)."""

    @pytest.mark.slow
    def test_full_agent_workflow(self, authenticated_client, mock_agent_data):
        """Test complete agent creation and usage workflow."""
        from unittest.mock import Mock

        import responses

        # Mock agent creation
        authenticated_client.agents.http.request = Mock(return_value=mock_agent_data)

        # Create agent
        agent = authenticated_client.create_agent(
            tools=["google_ads_search"], instructions="Optimize campaigns"
        )

        assert agent is not None
        assert_valid_agent_id(agent.id)

        # Test agent run - mock the HTTP streaming response
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

        # Test deployment - should raise NotImplementedError
        with pytest.raises(NotImplementedError):
            agent.deploy(schedule="daily")


@pytest.mark.unit
class TestHTTPClientRetryStrategy:
    """
    Phase 4 Edge Case Tests: HTTP Client Retry Strategy

    Verifies that the retry strategy is correctly configured:
    - Safe methods (GET, HEAD, OPTIONS) are retried
    - Non-idempotent methods (POST) are NOT retried (Bug #13 fixed)
    """

    def test_retry_strategy_excludes_post(self, authenticated_client):
        """
        Bug #13 Fixed: POST is NOT included in retry methods.

        POST requests should not be automatically retried since POST is
        not idempotent. Retrying a POST request (e.g., task creation) could
        cause duplicate task creation on transient failures.
        """
        session = authenticated_client._session
        adapter = session.get_adapter("https://")

        # Check the retry configuration
        retry_config = adapter.max_retries
        allowed_methods = retry_config.allowed_methods

        # POST should NOT be in allowed methods (Bug #13 fix)
        assert "POST" not in allowed_methods, "POST should not be retried automatically"

    def test_retry_strategy_safe_methods_included(self, authenticated_client):
        """Safe methods (GET, HEAD, OPTIONS) should be retried."""
        session = authenticated_client._session
        adapter = session.get_adapter("https://")
        allowed_methods = adapter.max_retries.allowed_methods

        # These safe methods should definitely be retried
        assert "GET" in allowed_methods
        assert "HEAD" in allowed_methods
        assert "OPTIONS" in allowed_methods

    def test_retry_strategy_status_codes(self, authenticated_client):
        """Verify retry is configured for correct status codes."""
        session = authenticated_client._session
        adapter = session.get_adapter("https://")

        status_forcelist = adapter.max_retries.status_forcelist

        # Should retry on server errors and rate limits
        assert 429 in status_forcelist  # Rate limited
        assert 500 in status_forcelist  # Internal server error
        assert 502 in status_forcelist  # Bad gateway
        assert 503 in status_forcelist  # Service unavailable
        assert 504 in status_forcelist  # Gateway timeout

        # Should NOT retry on client errors
        assert 400 not in status_forcelist
        assert 401 not in status_forcelist
        assert 403 not in status_forcelist
        assert 404 not in status_forcelist

    def test_retry_backoff_factor(self, authenticated_client):
        """Verify backoff factor is configured."""
        session = authenticated_client._session
        adapter = session.get_adapter("https://")

        backoff_factor = adapter.max_retries.backoff_factor

        # Should have reasonable backoff
        assert backoff_factor >= 0.5, "Backoff should be at least 0.5 seconds"


@pytest.mark.unit
class TestHTTPClientTimeout:
    """Tests for HTTP client timeout configuration."""

    def test_default_timeout(self):
        """Default timeout should be 30 seconds."""
        client = M8tes(api_key="test-key")
        assert client.timeout == 30

    def test_custom_timeout(self):
        """Custom timeout should be respected."""
        client = M8tes(api_key="test-key", timeout=120)
        assert client.timeout == 120

    def test_zero_timeout_allowed(self):
        """Zero timeout (no timeout) should be allowed."""
        client = M8tes(api_key="test-key", timeout=0)
        assert client.timeout == 0


@pytest.mark.unit
class TestAPIKeyValidation:
    """Tests for API key edge cases."""

    def test_empty_string_api_key(self):
        """Empty string API key should be stored."""
        client = M8tes(api_key="")
        assert client.api_key == ""

    def test_whitespace_only_api_key(self):
        """Whitespace-only API key should be stored as-is."""
        client = M8tes(api_key="   ")
        assert client.api_key == "   "

    def test_api_key_with_special_characters(self):
        """API key with special characters should work."""
        special_key = "sk_test_abc123!@#$%^&*()"
        client = M8tes(api_key=special_key)
        assert client.api_key == special_key
