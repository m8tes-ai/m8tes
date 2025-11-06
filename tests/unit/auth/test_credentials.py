"""Unit tests for CredentialManager class."""

from datetime import UTC, datetime, timedelta
import json
from unittest.mock import patch

import pytest

from m8tes.auth.credentials import CredentialManager


@pytest.mark.unit
class TestCredentialManager:
    """Test cases for CredentialManager methods."""

    @pytest.fixture
    def temp_config_dir(self, tmp_path):
        """Create temporary config directory."""
        config_dir = tmp_path / ".m8tes"
        config_dir.mkdir()
        return config_dir

    @pytest.fixture
    def credentials_manager(self, temp_config_dir):
        """Create CredentialManager with temporary config directory."""
        config_file = temp_config_dir / "config.json"

        # Create patches that will be active during the whole test
        config_dir_patch = patch.object(CredentialManager, "CONFIG_DIR", temp_config_dir)
        config_file_patch = patch.object(CredentialManager, "CONFIG_FILE", config_file)
        keyring_patch = patch("m8tes.auth.credentials.KEYRING_AVAILABLE", False)

        # Start all patches
        config_dir_patch.start()
        config_file_patch.start()
        keyring_patch.start()

        try:
            manager = CredentialManager(profile="test")
            yield manager
        finally:
            # Stop all patches
            keyring_patch.stop()
            config_file_patch.stop()
            config_dir_patch.stop()

    @pytest.fixture
    def mock_keyring(self):
        """Mock keyring functionality."""
        with patch("m8tes.auth.credentials.keyring") as mock_kr:
            mock_kr.get_password.return_value = None
            mock_kr.set_password.return_value = None
            mock_kr.delete_password.return_value = None
            yield mock_kr

    def test_save_token_metadata_creates_config_file(self, credentials_manager, temp_config_dir):
        """Test save_token_metadata creates config file with metadata."""
        refresh_token = "refresh_token_123"
        access_exp = "2024-01-01T01:00:00Z"
        refresh_exp = "2024-01-31T00:00:00Z"

        credentials_manager.save_token_metadata(
            refresh_token=refresh_token,
            access_expiration=access_exp,
            refresh_expiration=refresh_exp,
        )

        # Check config file was created with correct content
        config_file = temp_config_dir / "config.json"
        assert config_file.exists()

        config_content = json.loads(config_file.read_text())
        assert config_content["profiles"]["test"]["refresh_token"] == refresh_token
        assert config_content["profiles"]["test"]["access_expires_at"] == access_exp
        assert config_content["profiles"]["test"]["refresh_expires_at"] == refresh_exp

    def test_save_token_metadata_preserves_existing_config(
        self, credentials_manager, temp_config_dir
    ):
        """Test save_token_metadata preserves existing config data."""
        # Create initial config with some data
        config_file = temp_config_dir / "config.json"
        initial_config = {
            "profiles": {
                "test": {"email": "test@example.com", "base_url": "https://api.test.com"},
                "other": {"email": "other@example.com"},
            }
        }
        config_file.write_text(json.dumps(initial_config, indent=2))

        # Save token metadata
        credentials_manager.save_token_metadata(
            refresh_token="refresh_123", access_expiration="2024-01-01T01:00:00Z"
        )

        # Check existing data is preserved
        config_content = json.loads(config_file.read_text())
        assert config_content["profiles"]["test"]["email"] == "test@example.com"
        assert config_content["profiles"]["test"]["base_url"] == "https://api.test.com"
        assert config_content["profiles"]["other"]["email"] == "other@example.com"

        # Check new data is added
        assert config_content["profiles"]["test"]["refresh_token"] == "refresh_123"
        assert config_content["profiles"]["test"]["access_expires_at"] == "2024-01-01T01:00:00Z"

    def test_get_refresh_token_returns_saved_token(self, credentials_manager, temp_config_dir):
        """Test get_refresh_token returns previously saved refresh token."""
        # Create config with refresh token
        config_file = temp_config_dir / "config.json"
        config_data = {"profiles": {"test": {"refresh_token": "saved_refresh_token_123"}}}
        config_file.write_text(json.dumps(config_data))

        # Get refresh token
        result = credentials_manager.get_refresh_token()
        assert result == "saved_refresh_token_123"

    def test_get_refresh_token_returns_none_when_missing(
        self, credentials_manager, temp_config_dir
    ):
        """Test get_refresh_token returns None when token not found."""
        # Create config without refresh token
        config_file = temp_config_dir / "config.json"
        config_data = {"profiles": {"test": {"email": "test@example.com"}}}
        config_file.write_text(json.dumps(config_data))

        # Get refresh token
        result = credentials_manager.get_refresh_token()
        assert result is None

    def test_get_refresh_token_returns_none_when_no_config(self, credentials_manager):
        """Test get_refresh_token returns None when no config file exists."""
        result = credentials_manager.get_refresh_token()
        assert result is None

    def test_get_api_key_allows_api_key_format(self, credentials_manager, temp_config_dir):
        """Stored API keys without JWT format should remain valid."""
        # Prepare config with API key style credential
        config_file = temp_config_dir / "config.json"
        config_data = {"profiles": {"test": {"api_key": "test-api-key"}}}
        config_file.write_text(json.dumps(config_data))

        # Retrieve stored key; should not trigger warnings or deletion
        result = credentials_manager.get_api_key()

        assert result == "test-api-key"
        config_content = json.loads(config_file.read_text())
        assert config_content["profiles"]["test"]["api_key"] == "test-api-key"

    def test_is_access_token_expired_true_when_expired(self, credentials_manager, temp_config_dir):
        """Test is_access_token_expired returns True for expired token."""
        # Create config with expired access token
        expired_time = datetime.now(UTC) - timedelta(minutes=30)
        config_file = temp_config_dir / "config.json"
        config_data = {"profiles": {"test": {"access_expires_at": expired_time.isoformat()}}}
        config_file.write_text(json.dumps(config_data))

        # Check if expired
        result = credentials_manager.is_access_token_expired()
        assert result is True

    def test_is_access_token_expired_false_when_valid(self, credentials_manager, temp_config_dir):
        """Test is_access_token_expired returns False for valid token."""
        # Create config with future expiration
        future_time = datetime.now(UTC) + timedelta(minutes=30)
        config_file = temp_config_dir / "config.json"
        config_data = {"profiles": {"test": {"access_expires_at": future_time.isoformat()}}}
        config_file.write_text(json.dumps(config_data))

        # Check if expired
        result = credentials_manager.is_access_token_expired()
        assert result is False

    def test_is_access_token_expired_true_when_no_expiration(
        self, credentials_manager, temp_config_dir
    ):
        """Test is_access_token_expired returns True when no expiration data."""
        # Create config without expiration
        config_file = temp_config_dir / "config.json"
        config_data = {"profiles": {"test": {"email": "test@example.com"}}}
        config_file.write_text(json.dumps(config_data))

        # Check if expired (should default to True)
        result = credentials_manager.is_access_token_expired()
        assert result is True

    def test_is_access_token_expired_handles_buffer_time(
        self, credentials_manager, temp_config_dir
    ):
        """Test is_access_token_expired considers buffer time."""
        # Create config with token expiring in 2 minutes (within 5-minute buffer)
        near_future = datetime.now(UTC) + timedelta(minutes=2)
        config_file = temp_config_dir / "config.json"
        config_data = {"profiles": {"test": {"access_expires_at": near_future.isoformat()}}}
        config_file.write_text(json.dumps(config_data))

        # Should be considered expired due to buffer
        result = credentials_manager.is_access_token_expired()
        assert result is True

    def test_is_access_token_expired_handles_invalid_date_format(
        self, credentials_manager, temp_config_dir
    ):
        """Test is_access_token_expired handles invalid date format gracefully."""
        # Create config with invalid date format
        config_file = temp_config_dir / "config.json"
        config_data = {"profiles": {"test": {"access_expires_at": "invalid-date-format"}}}
        config_file.write_text(json.dumps(config_data))

        # Should return True (consider expired) when date parsing fails
        result = credentials_manager.is_access_token_expired()
        assert result is True

    def test_save_api_key_with_keyring_available(self, credentials_manager, mock_keyring):
        """Test save_api_key uses keyring when available."""
        # Mock keyring as available
        with patch("m8tes.auth.credentials.KEYRING_AVAILABLE", True):
            result = credentials_manager.save_api_key("test_api_key_123")

        assert result is True
        mock_keyring.set_password.assert_called_once_with(
            "m8tes", "test_api_key", "test_api_key_123"
        )

    def test_save_api_key_with_keyring_unavailable(self, credentials_manager, temp_config_dir):
        """Test save_api_key falls back to config file when keyring unavailable."""
        # Note: credentials_manager fixture already sets KEYRING_AVAILABLE to False
        # so we don't need to patch it again
        result = credentials_manager.save_api_key("test_api_key_123")

        assert result is True

        # Check config file contains API key
        config_file = temp_config_dir / "config.json"
        config_content = json.loads(config_file.read_text())
        assert config_content["profiles"]["test"]["api_key"] == "test_api_key_123"

    def test_get_api_key_from_keyring(self, credentials_manager, mock_keyring):
        """Test get_api_key retrieves from keyring when available."""
        valid_jwt = "header.payload.signature"
        mock_keyring.get_password.return_value = valid_jwt

        with patch("m8tes.auth.credentials.KEYRING_AVAILABLE", True):
            result = credentials_manager.get_api_key()

        assert result == valid_jwt
        mock_keyring.get_password.assert_called_once_with("m8tes", "test_api_key")

    def test_get_api_key_from_config_file(self, credentials_manager, temp_config_dir):
        """Test get_api_key falls back to config file."""
        # Create config with API key
        config_file = temp_config_dir / "config.json"
        valid_jwt = "header.payload.signature"
        config_data = {"profiles": {"test": {"api_key": valid_jwt}}}
        config_file.write_text(json.dumps(config_data))

        # Note: credentials_manager fixture already sets KEYRING_AVAILABLE to False
        result = credentials_manager.get_api_key()

        assert result == valid_jwt

    def test_delete_api_key_from_keyring(self, credentials_manager, mock_keyring):
        """Test delete_api_key removes from keyring."""
        with patch("m8tes.auth.credentials.KEYRING_AVAILABLE", True):
            result = credentials_manager.delete_api_key()

        assert result is True
        mock_keyring.delete_password.assert_called_once_with("m8tes", "test_api_key")

    def test_delete_api_key_from_config_file(self, credentials_manager, temp_config_dir):
        """Test delete_api_key removes from config file."""
        # Create config with API key
        config_file = temp_config_dir / "config.json"
        config_data = {
            "profiles": {"test": {"api_key": "config_api_key_123", "email": "test@example.com"}}
        }
        config_file.write_text(json.dumps(config_data))

        # Note: credentials_manager fixture already sets KEYRING_AVAILABLE to False
        result = credentials_manager.delete_api_key()

        assert result is True

        # Check API key was removed but other data preserved
        config_content = json.loads(config_file.read_text())
        assert "api_key" not in config_content["profiles"]["test"]
        assert config_content["profiles"]["test"]["email"] == "test@example.com"

    def test_clear_profile_removes_all_profile_data(
        self, credentials_manager, temp_config_dir, mock_keyring
    ):
        """Test clear_profile removes all data for the profile."""
        # Setup config with data
        config_file = temp_config_dir / "config.json"
        config_data = {
            "profiles": {
                "test": {
                    "email": "test@example.com",
                    "refresh_token": "refresh_123",
                    "access_expires_at": "2024-01-01T01:00:00Z",
                },
                "other": {"email": "other@example.com"},
            }
        }
        config_file.write_text(json.dumps(config_data))

        # Mock keyring deletion to succeed
        mock_keyring.delete_password.return_value = None

        with patch("m8tes.auth.credentials.KEYRING_AVAILABLE", True):
            result = credentials_manager.clear_profile()

        assert result is True

        # Check profile data was removed from config
        config_content = json.loads(config_file.read_text())
        assert "test" not in config_content["profiles"]
        assert "other" in config_content["profiles"]  # Other profiles preserved

        # Check keyring deletion was attempted
        mock_keyring.delete_password.assert_called_once()

    def test_save_profile_info_updates_config(self, credentials_manager, temp_config_dir):
        """Test save_profile_info updates profile information in config."""
        credentials_manager.save_profile_info(
            email="updated@example.com", base_url="https://api.updated.com"
        )

        # Check config file
        config_file = temp_config_dir / "config.json"
        config_content = json.loads(config_file.read_text())

        assert config_content["profiles"]["test"]["email"] == "updated@example.com"
        assert config_content["profiles"]["test"]["base_url"] == "https://api.updated.com"

    def test_get_profile_info_returns_saved_info(self, credentials_manager, temp_config_dir):
        """Test get_profile_info returns saved profile information."""
        # Setup config with profile info
        config_file = temp_config_dir / "config.json"
        config_data = {
            "profiles": {
                "test": {"email": "saved@example.com", "base_url": "https://api.saved.com"}
            }
        }
        config_file.write_text(json.dumps(config_data))

        result = credentials_manager.get_profile_info()

        assert result["email"] == "saved@example.com"
        assert result["base_url"] == "https://api.saved.com"

    def test_get_profile_info_returns_empty_when_no_profile(self, credentials_manager):
        """Test get_profile_info returns empty dict when no profile exists."""
        result = credentials_manager.get_profile_info()
        assert result == {}
