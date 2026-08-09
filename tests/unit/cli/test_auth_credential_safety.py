"""The CLI must never destroy or leak a stored credential on an uncertain outcome.

Pins the #1229 review fixes:
- `get_valid_api_key` deletes the saved key ONLY on a definitive 401/403 from the
  refresh endpoint. Missing expiry metadata, a missing refresh token, a network
  failure, or a 5xx all return the key untouched (deleting on uncertainty logged
  users out on a fresh registration and on any offline moment).
- Registration persists the token's expiry metadata WITH the key, so the very
  next command doesn't read the fresh key as "expired".
- The session transport's refresh middleware acts only for the SAVED profile
  credential — an explicitly supplied key must never trigger a refresh that
  posts the profile's refresh token to this transport's base_url or overwrites
  the explicit key.
"""

from unittest.mock import Mock, patch

import pytest
import requests

from m8tes.auth.http import HTTPClient as SessionHTTPClient
from m8tes.cli.auth import AuthCLI


def _auth_cli_with_creds(
    *, api_key="jwt_saved", expired=True, refresh_token="rt_1"
) -> tuple[AuthCLI, Mock]:
    cli = AuthCLI(base_url="http://127.0.0.1:9")
    creds = Mock()
    creds.get_api_key.return_value = api_key
    creds.is_access_token_expired.return_value = expired
    creds.get_refresh_token.return_value = refresh_token
    cli.credentials = creds
    return cli, creds


class TestGetValidApiKey:
    def test_fresh_token_returned_without_refresh(self):
        cli, creds = _auth_cli_with_creds(expired=False)
        with patch("requests.post") as post:
            assert cli.get_valid_api_key() == "jwt_saved"
        post.assert_not_called()
        creds.delete_api_key.assert_not_called()

    def test_no_refresh_token_returns_key_untouched(self):
        """Missing metadata reads as expired; with no refresh token the key survives."""
        cli, creds = _auth_cli_with_creds(refresh_token=None)
        assert cli.get_valid_api_key() == "jwt_saved"
        creds.delete_api_key.assert_not_called()

    def test_network_failure_returns_key_untouched(self):
        cli, creds = _auth_cli_with_creds()
        with patch("requests.post", side_effect=requests.ConnectionError("offline")):
            assert cli.get_valid_api_key() == "jwt_saved"
        creds.delete_api_key.assert_not_called()

    def test_server_error_returns_key_untouched(self):
        cli, creds = _auth_cli_with_creds()
        with patch("requests.post", return_value=Mock(status_code=503)):
            assert cli.get_valid_api_key() == "jwt_saved"
        creds.delete_api_key.assert_not_called()

    def test_definitive_401_deletes_the_key(self):
        cli, creds = _auth_cli_with_creds()
        response = Mock(status_code=401)
        response.json.return_value = {"error": {"message": "refresh token revoked"}}
        with patch("requests.post", return_value=response):
            assert cli.get_valid_api_key() is None
        creds.delete_api_key.assert_called_once()

    def test_html_401_is_not_evidence_and_keeps_the_key(self):
        """A proxy or wrong service can answer 401 with HTML — that proves nothing
        about the refresh token, so the key must survive."""
        cli, creds = _auth_cli_with_creds()
        response = Mock(status_code=401)
        response.json.side_effect = ValueError("not json")
        with patch("requests.post", return_value=response):
            assert cli.get_valid_api_key() == "jwt_saved"
        creds.delete_api_key.assert_not_called()

    def test_malformed_200_keeps_the_key(self):
        cli, creds = _auth_cli_with_creds()
        response = Mock(status_code=200)
        response.json.side_effect = ValueError("not json")
        with patch("requests.post", return_value=response):
            assert cli.get_valid_api_key() == "jwt_saved"
        creds.delete_api_key.assert_not_called()

    def test_successful_refresh_saves_key_and_metadata(self):
        cli, creds = _auth_cli_with_creds()
        response = Mock(status_code=200)
        response.json.return_value = {
            "api_key": "jwt_new",
            "refresh_token": "rt_2",
            "access_expires_at": "2027-01-01T00:00:00Z",
            "refresh_expires_at": "2027-02-01T00:00:00Z",
        }
        with patch("requests.post", return_value=response):
            assert cli.get_valid_api_key() == "jwt_new"
        creds.save_api_key.assert_called_once_with("jwt_new")
        creds.save_token_metadata.assert_called_once_with(
            refresh_token="rt_2",
            access_expiration="2027-01-01T00:00:00Z",
            refresh_expiration="2027-02-01T00:00:00Z",
        )
        creds.delete_api_key.assert_not_called()


class TestRegisterPersistsTokenMetadata:
    @patch("m8tes.cli.auth.prompt")
    @patch("m8tes.cli.auth.prompt_email")
    @patch("m8tes.cli.auth.prompt_password_confirm")
    def test_register_saves_expiry_metadata_with_the_key(self, pw, email, name):
        email.return_value = "new@m8tes.dev"
        pw.return_value = "password123"
        name.side_effect = ["New"]

        cli = AuthCLI(base_url="http://127.0.0.1:9")
        service = Mock()
        service.register_user.return_value = {
            "user": {"id": 1, "email": "new@m8tes.dev"},
            "api_key": "jwt_reg",
            "refresh_token": "rt_reg",
            "access_expires_at": "2027-01-01T00:00:00Z",
            "refresh_expires_at": "2027-02-01T00:00:00Z",
        }
        cli._session_service = Mock(return_value=service)
        cli.credentials = Mock()
        cli.credentials.save_api_key.return_value = True
        cli.credentials.is_keyring_available = True
        cli.get_current_account_info = Mock(return_value=None)

        cli.register_interactive()

        cli.credentials.save_token_metadata.assert_called_once_with(
            refresh_token="rt_reg",
            access_expiration="2027-01-01T00:00:00Z",
            refresh_expiration="2027-02-01T00:00:00Z",
        )


class TestBaseUrlShapesWorkOnBothSurfaces:
    """M8TES_BASE_URL is documented as a /api/v2 URL for the SDK, and CLI users set
    a bare host — BOTH shapes must work on the session surface and the v2 surface."""

    def test_platform_url_strips_a_v2_suffix(self, monkeypatch):
        monkeypatch.setenv("M8TES_BASE_URL", "http://127.0.0.1:8000/api/v2")
        assert AuthCLI()._platform_url() == "http://127.0.0.1:8000"

    def test_platform_url_keeps_a_bare_host(self, monkeypatch):
        monkeypatch.setenv("M8TES_BASE_URL", "http://127.0.0.1:8000")
        assert AuthCLI()._platform_url() == "http://127.0.0.1:8000"

    def test_platform_url_strips_a_bare_v2_suffix(self, monkeypatch):
        """normalize_v2_base_url accepts host/v2 — so the session side must strip it."""
        monkeypatch.setenv("M8TES_BASE_URL", "http://127.0.0.1:8000/v2/")
        assert AuthCLI()._platform_url() == "http://127.0.0.1:8000"

    def test_google_platform_url_strips_a_bare_v2_suffix(self, monkeypatch):
        from m8tes.cli.google import GoogleIntegrationCLI

        monkeypatch.setenv("M8TES_BASE_URL", "http://127.0.0.1:8000/v2")
        assert GoogleIntegrationCLI(None)._platform_url() == "http://127.0.0.1:8000"

    def test_google_platform_url_strips_a_v2_suffix(self, monkeypatch):
        from m8tes.cli.google import GoogleIntegrationCLI

        monkeypatch.setenv("M8TES_BASE_URL", "http://127.0.0.1:8000/api/v2")
        assert GoogleIntegrationCLI(None)._platform_url() == "http://127.0.0.1:8000"

    def test_probe_normalizes_a_bare_env_host_for_the_v2_client(self, monkeypatch):
        monkeypatch.setenv("M8TES_BASE_URL", "http://127.0.0.1:8000")
        with patch("m8tes._client.M8tes") as v2_cls:
            v2_cls.return_value.auth.is_verified.return_value = True
            AuthCLI()._probe_v2_key("m8_x")
        assert v2_cls.call_args.kwargs["base_url"] == "http://127.0.0.1:8000/api/v2"


class TestLogoutRevokesTheActiveCredential:
    def test_explicit_client_key_wins_over_saved(self, capsys):
        """`m8tes --api-key X auth logout` must revoke X, not the saved session."""
        cli = AuthCLI(client=Mock(api_key="jwt_explicit"), base_url="http://127.0.0.1:9")
        cli.credentials = Mock()
        cli.credentials.get_api_key.return_value = "jwt_saved"
        cli.credentials.clear_profile.return_value = True
        cli._session_service = Mock()
        cli._session_service.return_value.logout.return_value = True

        cli.logout_interactive()

        cli._session_service.assert_called_once_with(api_key="jwt_explicit", profile_bound=False)
        assert "✅ Token invalidated on server" in capsys.readouterr().out

    def test_saved_key_used_when_no_client_key(self):
        cli = AuthCLI(client=None, base_url="http://127.0.0.1:9")
        cli.credentials = Mock()
        cli.credentials.get_api_key.return_value = "jwt_saved"
        cli.credentials.clear_profile.return_value = True
        cli._session_service = Mock()
        cli._session_service.return_value.logout.return_value = True

        cli.logout_interactive()

        cli._session_service.assert_called_once_with(api_key="jwt_saved", profile_bound=True)


class TestSessionTransportRefreshBinding:
    def _transport(self, api_key: str, *, profile_bound: bool = False) -> SessionHTTPClient:
        return SessionHTTPClient(
            base_url="http://127.0.0.1:9", api_key=api_key, profile_bound=profile_bound
        )

    def test_explicit_key_never_triggers_profile_refresh(self):
        """An unbound key must not post the profile's refresh token anywhere."""
        http = self._transport("jwt_explicit")
        creds = Mock()
        with patch("m8tes.auth.credentials.CredentialManager", return_value=creds):
            assert http._try_refresh_token() is False
            http._ensure_valid_token()
        creds.get_refresh_token.assert_not_called()
        creds.is_access_token_expired.assert_not_called()

    def test_default_is_unbound_so_a_forgetful_caller_fails_safe(self):
        """Constructed with no flag at all, the transport must NOT refresh — a
        caller who forgets the kwarg must not leak the profile's refresh token."""
        http = SessionHTTPClient(base_url="http://127.0.0.1:9", api_key="jwt_whatever")
        assert http.profile_bound is False
        assert http._refresh_is_bound_to_this_credential() is False

    def test_unbound_transport_never_reads_the_credential_store(self):
        """Binding is decided at construction: a per-request credential read put a
        blocking keychain call on the hot path of every session request (it hung
        `m8tes google status` and survived SIGTERM)."""
        http = self._transport("jwt_explicit")
        with patch("m8tes.auth.credentials.CredentialManager") as manager:
            http._ensure_valid_token()
            http._refresh_is_bound_to_this_credential()
        manager.assert_not_called()

    def test_bound_transport_reads_no_store_to_decide_either(self):
        http = self._transport("jwt_saved", profile_bound=True)
        with patch("m8tes.auth.credentials.CredentialManager") as manager:
            assert http._refresh_is_bound_to_this_credential() is True
        manager.assert_not_called()

    def test_saved_key_still_refreshes(self):
        http = self._transport("jwt_saved", profile_bound=True)
        creds = Mock()
        creds.get_api_key.return_value = "jwt_saved"  # store still holds our key
        creds.get_refresh_token.return_value = None  # bound, but nothing to refresh
        with patch("m8tes.auth.credentials.CredentialManager", return_value=creds):
            assert http._try_refresh_token() is False
        creds.get_refresh_token.assert_called_once()

    def test_binding_follows_the_value_not_a_stale_flag(self):
        """A swapped-in key must not inherit the old key's refresh permission —
        a boolean snapshot would stay True after set_api_key()."""
        http = self._transport("jwt_saved", profile_bound=True)
        assert http.profile_bound is True

        http.set_api_key("jwt_someone_else")
        assert http.profile_bound is False
        assert http._refresh_is_bound_to_this_credential() is False

        http.set_api_key("jwt_refreshed", profile_bound=True)
        assert http.profile_bound is True

        # Even a direct attribute swap (bypassing set_api_key) must unbind —
        # binding is the VALUE match, not a "was bound once" flag.
        http.api_key = "jwt_smuggled_in"
        assert http.profile_bound is False
        assert http._refresh_is_bound_to_this_credential() is False

    def test_a_successful_refresh_stays_bound_for_the_next_expiry(self):
        """The refreshed key IS the profile credential (it is saved), so a second
        expiry inside the same command must still be able to refresh."""
        http = self._transport("jwt_saved", profile_bound=True)
        creds = Mock()
        creds.get_api_key.return_value = "jwt_saved"
        creds.get_refresh_token.return_value = "rt_1"
        response = Mock(status_code=200)
        response.json.return_value = {"api_key": "jwt_rotated"}
        with (
            patch("m8tes.auth.credentials.CredentialManager", return_value=creds),
            patch.object(http._session, "request", return_value=response),
        ):
            assert http._try_refresh_token() is True

        assert http.api_key == "jwt_rotated"
        assert http.profile_bound is True

    def test_a_failed_refresh_latches_so_the_store_is_read_once(self):
        """Missing expiry metadata reads as 'expired', so an un-refreshable bound
        credential re-entered the refresh path on EVERY request — and the store
        re-confirm there is a keychain read, i.e. the hang, back per request."""
        http = self._transport("jwt_saved", profile_bound=True)
        creds = Mock()
        creds.get_api_key.return_value = "jwt_saved"
        creds.is_access_token_expired.return_value = True
        creds.get_refresh_token.return_value = None  # nothing to refresh with
        with patch("m8tes.auth.credentials.CredentialManager", return_value=creds):
            http._ensure_valid_token()
            http._ensure_valid_token()
            http._ensure_valid_token()
        assert creds.get_api_key.call_count == 1

    def test_the_latch_holds_across_real_requests_including_401_retries(self):
        """Request-level proof: the 401 retry calls _try_refresh_token directly, so a
        caller-side-only latch let every 401 re-read the credential store."""

        http = self._transport("jwt_saved", profile_bound=True)
        creds = Mock()
        creds.get_api_key.return_value = "jwt_saved"
        creds.is_access_token_expired.return_value = True
        creds.get_refresh_token.return_value = None

        unauthorized = Mock(status_code=401, headers={"Content-Type": "application/json"})
        unauthorized.json.return_value = {"detail": "expired"}
        with (
            patch("m8tes.auth.credentials.CredentialManager", return_value=creds),
            patch.object(http._session, "request", return_value=unauthorized),
        ):
            for _ in range(3):
                with pytest.raises(Exception):  # noqa: B017 - AuthenticationError
                    http.request("GET", "/api/v1/auth/me")
        assert creds.get_api_key.call_count == 1

    def test_a_new_credential_clears_the_latch(self):
        """A fresh key deserves a fresh attempt — the latch is per credential,
        not a permanent 'never refresh again' on this transport."""
        http = self._transport("jwt_saved", profile_bound=True)
        creds = Mock()
        creds.get_api_key.return_value = "jwt_saved"
        creds.is_access_token_expired.return_value = True
        creds.get_refresh_token.return_value = None
        with patch("m8tes.auth.credentials.CredentialManager", return_value=creds):
            http._ensure_valid_token()
            assert http._refresh_failed is True

            creds.get_api_key.return_value = "jwt_rotated"
            http.set_api_key("jwt_rotated", profile_bound=True)
            assert http._refresh_failed is False
            http._ensure_valid_token()
        assert creds.get_api_key.call_count == 2

    def test_refresh_reconfirms_against_the_store_before_spending_the_token(self):
        """If the profile was replaced since construction, its refresh token belongs
        to another account — don't spend it."""
        http = self._transport("jwt_saved", profile_bound=True)
        creds = Mock()
        creds.get_api_key.return_value = "jwt_a_different_profile"
        with patch("m8tes.auth.credentials.CredentialManager", return_value=creds):
            assert http._try_refresh_token() is False
        creds.get_refresh_token.assert_not_called()

    def test_google_saved_key_via_the_cli_client_stays_bound(self):
        """The normal path: no --api-key, so main.py resolved the key from the
        store and marked its provenance — google must keep refresh here."""
        from m8tes.cli.google import GoogleIntegrationCLI

        client = Mock(api_key="jwt_saved", api_key_from_profile=True)
        with (
            patch("m8tes.cli.google.SessionHTTPClient") as http_cls,
            patch("m8tes.cli.google.AuthCLI") as auth_cli,
        ):
            GoogleIntegrationCLI(client)._session_http()
        auth_cli.assert_not_called()
        assert http_cls.call_args.kwargs["profile_bound"] is True

    def test_google_env_key_via_the_cli_client_stays_unbound(self):
        """M8TES_API_KEY reaches the client too, and it is NOT the profile key."""
        from m8tes.cli.google import GoogleIntegrationCLI

        client = Mock(api_key="m8_from_env", api_key_from_profile=False)
        with (
            patch("m8tes.cli.google.SessionHTTPClient") as http_cls,
            patch("m8tes.cli.google.AuthCLI"),
        ):
            GoogleIntegrationCLI(client)._session_http()
        assert http_cls.call_args.kwargs["profile_bound"] is False

    def test_google_explicit_key_builds_an_unbound_transport(self):
        """The regression in the flesh: google's transport must not be profile-bound
        when the key came from --api-key, or every request hits the keychain."""
        from m8tes.cli.google import GoogleIntegrationCLI

        with (
            patch("m8tes.cli.google.SessionHTTPClient") as http_cls,
            patch("m8tes.cli.google.AuthCLI") as auth_cli,
        ):
            GoogleIntegrationCLI(None, api_key="m8_explicit")._session_http()
        auth_cli.assert_not_called()
        assert http_cls.call_args.kwargs["profile_bound"] is False

    def test_google_keychain_fallback_builds_a_bound_transport(self):
        from m8tes.cli.google import GoogleIntegrationCLI

        with (
            patch("m8tes.cli.google.SessionHTTPClient") as http_cls,
            patch("m8tes.cli.google.AuthCLI") as auth_cli,
        ):
            auth_cli.return_value.get_valid_api_key.return_value = "jwt_saved"
            GoogleIntegrationCLI(None)._session_http()
        assert http_cls.call_args.kwargs["profile_bound"] is True
