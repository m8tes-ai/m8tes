"""Tests for CLI helpers that bridge to the v2 SDK client."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from m8tes._exceptions import AuthenticationError
from m8tes.cli.v2 import (
    create_v2_client,
    get_v2_api_key,
    normalize_v2_base_url,
    v2_client_from_args,
)


class TestNormalizeV2BaseUrl:
    """Base URL normalization should produce v2-compatible endpoints."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            (None, None),
            ("https://m8tes.ai", "https://m8tes.ai/api/v2"),
            ("https://m8tes.ai/api", "https://m8tes.ai/api/v2"),
            ("https://m8tes.ai/api/v1", "https://m8tes.ai/api/v2"),
            ("https://m8tes.ai/api/v2", "https://m8tes.ai/api/v2"),
            ("https://m8tes.ai/v2", "https://m8tes.ai/v2"),
        ],
    )
    def test_normalize_v2_base_url(self, raw, expected):
        """Known URL shapes should normalize deterministically."""
        assert normalize_v2_base_url(raw) == expected


class TestGetV2ApiKey:
    """API key resolution should follow CLI args, then client, then saved auth."""

    @patch("m8tes.cli.v2.AuthCLI")
    def test_prefers_explicit_arg(self, mock_auth_cli):
        """An explicit --api-key should win over all other sources."""
        args = SimpleNamespace(api_key="m8_arg_key", base_url="https://m8tes.ai")
        client = SimpleNamespace(api_key="m8_client_key")

        assert get_v2_api_key(args, client) == "m8_arg_key"
        mock_auth_cli.assert_not_called()

    @patch("m8tes.cli.v2.AuthCLI")
    def test_falls_back_to_client_key(self, mock_auth_cli):
        """Legacy CLI client credentials should be reused when available."""
        args = SimpleNamespace(api_key=None, base_url="https://m8tes.ai")
        client = SimpleNamespace(api_key="m8_client_key")

        assert get_v2_api_key(args, client) == "m8_client_key"
        mock_auth_cli.assert_not_called()

    @patch("m8tes.cli.v2.AuthCLI")
    def test_falls_back_to_saved_credentials(self, mock_auth_cli):
        """Saved credentials should be used when args and client omit the key."""
        args = SimpleNamespace(api_key=None, base_url="https://m8tes.ai")
        mock_auth_cli.return_value.get_valid_api_key.return_value = "m8_saved_key"

        assert get_v2_api_key(args) == "m8_saved_key"
        mock_auth_cli.return_value.get_valid_api_key.assert_called_once_with()


class TestCreateV2Client:
    """Client construction should normalize base URLs and enforce auth."""

    @patch("m8tes.cli.v2.V2Client")
    def test_env_base_url_is_normalized_too(self, mock_client_class, monkeypatch):
        """A bare-host M8TES_BASE_URL (the session-auth convention) must reach the
        v2 client as a /api/v2 URL — consumed raw it sends /tasks/ to the host root."""
        monkeypatch.setenv("M8TES_BASE_URL", "http://127.0.0.1:8000")
        args = SimpleNamespace(api_key="m8_test_key", base_url=None)

        create_v2_client(args)

        assert mock_client_class.call_args.kwargs["base_url"] == "http://127.0.0.1:8000/api/v2"

    @patch("m8tes.cli.v2.V2Client")
    def test_uses_args_and_normalizes_v1_base_url(self, mock_client_class):
        """A v1-style base URL should be converted before constructing the v2 client."""
        args = SimpleNamespace(api_key="m8_test_key", base_url="https://m8tes.ai/api/v1")

        create_v2_client(args)

        mock_client_class.assert_called_once_with(
            api_key="m8_test_key",
            base_url="https://m8tes.ai/api/v2",
        )

    @patch("m8tes.cli.v2.V2Client")
    def test_uses_legacy_client_base_url_when_args_omit_it(self, mock_client_class):
        """Commands should inherit the base URL from the existing CLI client when needed."""
        args = SimpleNamespace(api_key=None, base_url=None)
        client = SimpleNamespace(api_key="m8_test_key", base_url="https://staging.m8tes.ai/api")

        create_v2_client(args, client)

        mock_client_class.assert_called_once_with(
            api_key="m8_test_key",
            base_url="https://staging.m8tes.ai/api/v2",
        )

    def test_raises_when_no_api_key_is_available(self):
        """The bridge should fail clearly when no credentials can be resolved."""
        args = SimpleNamespace(api_key=None, base_url=None)

        with patch("m8tes.cli.v2.AuthCLI") as mock_auth_cli:
            mock_auth_cli.return_value.get_valid_api_key.return_value = None

            with pytest.raises(AuthenticationError, match="Authentication required"):
                create_v2_client(args)


class TestMainCreateClient:
    """cli/main.py builds the CLI's v2 client with the same URL discipline."""

    @patch("m8tes.cli.main.M8tes")
    def test_records_credential_provenance_for_the_session_surface(self, mock_client_class):
        """A key resolved from the credential store is marked; an explicit one is not.
        cli/google.py reads this to decide whether the session transport may run the
        profile's refresh dance (re-deriving it downstream costs a keychain read)."""
        from m8tes.cli.main import create_client

        with patch("m8tes.cli.auth.AuthCLI") as auth_cli:
            auth_cli.return_value.get_valid_api_key.return_value = "jwt_saved"
            client = create_client(api_key=None, base_url=None)
        assert client.api_key_from_profile is True

        client = create_client(api_key="m8_explicit", base_url=None)
        assert client.api_key_from_profile is False

    @patch("m8tes.cli.main.M8tes")
    def test_env_base_url_is_normalized(self, mock_client_class, monkeypatch):
        from m8tes.cli.main import create_client

        monkeypatch.setenv("M8TES_BASE_URL", "http://127.0.0.1:8000")
        create_client(api_key="m8_test_key", base_url=None)

        assert mock_client_class.call_args.kwargs["base_url"] == "http://127.0.0.1:8000/api/v2"


class TestV2ClientFromArgs:
    """The context manager should always close the underlying SDK client."""

    @patch("m8tes.cli.v2.create_v2_client")
    def test_closes_client_on_exit(self, mock_create_v2_client):
        """Command helpers should not leak open HTTP clients."""
        mock_client = Mock()
        mock_create_v2_client.return_value = mock_client
        args = SimpleNamespace(api_key="m8_test_key", base_url="https://m8tes.ai")

        with v2_client_from_args(args) as client:
            assert client is mock_client

        mock_client.close.assert_called_once_with()
