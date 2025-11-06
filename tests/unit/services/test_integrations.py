"""
Unit tests for IntegrationService.

Tests the integration service that provides access to Google and Meta
authentication helpers.
"""

from unittest.mock import Mock

import pytest

from m8tes.auth.google import GoogleAuth
from m8tes.auth.meta import MetaAuth
from m8tes.services.integrations import IntegrationService


@pytest.fixture
def mock_http_client():
    """Create a mock HTTP client for testing."""
    return Mock()


@pytest.fixture
def integration_service(mock_http_client):
    """Create an IntegrationService instance with mocked HTTP client."""
    return IntegrationService(http_client=mock_http_client)


@pytest.mark.unit
class TestIntegrationServiceInitialization:
    """Test IntegrationService initialization."""

    def test_initialization_with_http_client(self, mock_http_client):
        """Test that service initializes with HTTP client."""
        service = IntegrationService(http_client=mock_http_client)
        assert service.http == mock_http_client

    def test_initialization_creates_google_auth(self, mock_http_client):
        """Test that GoogleAuth is created during initialization."""
        service = IntegrationService(http_client=mock_http_client)
        assert hasattr(service, "_google")
        assert isinstance(service._google, GoogleAuth)

    def test_initialization_creates_meta_auth(self, mock_http_client):
        """Test that MetaAuth is created during initialization."""
        service = IntegrationService(http_client=mock_http_client)
        assert hasattr(service, "_meta")
        assert isinstance(service._meta, MetaAuth)

    def test_initialization_with_client_parameter(self, mock_http_client):
        """Test initialization with optional client parameter."""
        mock_client = Mock()
        service = IntegrationService(http_client=mock_http_client, client=mock_client)
        assert service.http == mock_http_client


@pytest.mark.unit
class TestGoogleProperty:
    """Test Google integration property."""

    def test_google_property_returns_google_auth(self, integration_service):
        """Test that google property returns GoogleAuth instance."""
        google = integration_service.google
        assert isinstance(google, GoogleAuth)

    def test_google_property_returns_same_instance(self, integration_service):
        """Test that google property returns the same instance each time."""
        google1 = integration_service.google
        google2 = integration_service.google
        assert google1 is google2

    def test_google_property_has_http_client(self, integration_service, mock_http_client):
        """Test that GoogleAuth instance has access to HTTP client."""
        google = integration_service.google
        assert hasattr(google, "http")


@pytest.mark.unit
class TestMetaProperty:
    """Test Meta integration property."""

    def test_meta_property_returns_meta_auth(self, integration_service):
        """Test that meta property returns MetaAuth instance."""
        meta = integration_service.meta
        assert isinstance(meta, MetaAuth)

    def test_meta_property_returns_same_instance(self, integration_service):
        """Test that meta property returns the same instance each time."""
        meta1 = integration_service.meta
        meta2 = integration_service.meta
        assert meta1 is meta2

    def test_meta_property_has_http_client(self, integration_service, mock_http_client):
        """Test that MetaAuth instance has access to HTTP client."""
        meta = integration_service.meta
        assert hasattr(meta, "http")


@pytest.mark.unit
class TestIntegrationServiceIntegration:
    """Integration-style tests for IntegrationService."""

    def test_both_integrations_use_same_http_client(self, integration_service, mock_http_client):
        """Test that both Google and Meta use the same HTTP client."""
        google = integration_service.google
        meta = integration_service.meta

        assert google.http is mock_http_client
        assert meta.http is mock_http_client
        assert google.http is meta.http

    def test_service_provides_access_to_both_integrations(self, integration_service):
        """Test that service provides access to both integrations."""
        # Should be able to access both
        google = integration_service.google
        meta = integration_service.meta

        assert google is not None
        assert meta is not None
        assert isinstance(google, GoogleAuth)
        assert isinstance(meta, MetaAuth)
