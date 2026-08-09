"""The Google integration CLI runs on the session transport, not the legacy client.

`cli/main.py` hands every command a **v2** SDK client, so `client.google` (a legacy
aggregate-client property) no longer exists. The CLI now builds `auth/google.py`
itself over `auth/http.py`, whose JWT-session auth is what the /api/v1 OAuth surface
understands. (The Meta twin was deleted outright — the backend's meta-ads endpoints
no longer exist.) These tests pin the wiring (host, credential precedence, one
transport per command) and the structural rule that neither module may reach back
into the legacy client packages.
"""

from argparse import Namespace
import ast
import pathlib
from unittest.mock import MagicMock, Mock, patch

import pytest

from m8tes.cli.google import GoogleIntegrationCLI

PACKAGE_ROOT = pathlib.Path(__file__).resolve().parents[3] / "m8tes"

PORTED_MODULES = (
    PACKAGE_ROOT / "cli" / "google.py",
    PACKAGE_ROOT / "cli" / "commands" / "google.py",
)

# Legacy packages that are being deleted with the legacy aggregate client.
FORBIDDEN_ROOTS = {"m8tes.client", "m8tes.services", "m8tes.http"}


def _imported_modules(path: pathlib.Path) -> set[str]:
    """Absolute module names imported by `path` (relative imports resolved)."""
    tree = ast.parse(path.read_text())
    package_parts = ["m8tes", *path.relative_to(PACKAGE_ROOT).parts[:-1]]
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package_parts[: len(package_parts) - node.level + 1]
                module = ".".join([*base, node.module] if node.module else base)
            else:
                module = node.module or ""
            names.add(module)
            names.update(f"{module}.{alias.name}" for alias in node.names)
    return names


@pytest.mark.parametrize("path", PORTED_MODULES, ids=lambda p: str(p.relative_to(PACKAGE_ROOT)))
def test_ported_modules_never_import_the_legacy_client(path):
    """The four ported modules must not import m8tes.client / services / http."""
    for module in _imported_modules(path):
        for forbidden in FORBIDDEN_ROOTS:
            assert module != forbidden and not module.startswith(f"{forbidden}."), (
                f"{path.name} imports legacy module {module}"
            )


# --------------------------------------------------------------------------- google


@pytest.fixture()
def google_session():
    """Patch the Google CLI's transport seam; yields (AuthCLI, HTTPClient, GoogleAuth)."""
    with (
        patch("m8tes.cli.google.AuthCLI") as auth_cli,
        patch("m8tes.cli.google.SessionHTTPClient") as http_cls,
        patch("m8tes.cli.google.GoogleAuth") as google_auth,
    ):
        auth_cli.return_value.get_valid_api_key.return_value = None
        yield auth_cli, http_cls, google_auth


def test_google_service_rides_session_transport_on_the_bare_host(google_session):
    auth_cli, http_cls, google_auth = google_session
    auth_cli.return_value.get_valid_api_key.return_value = "session-jwt"

    cli = GoogleIntegrationCLI(None, base_url="http://127.0.0.1:8000")
    service = cli.google

    auth_cli.assert_called_once_with(base_url="http://127.0.0.1:8000")
    http_cls.assert_called_once_with(
        base_url="http://127.0.0.1:8000", api_key="session-jwt", profile_bound=True
    )
    google_auth.assert_called_once_with(http_cls.return_value)
    assert service is google_auth.return_value


def test_google_base_url_falls_back_to_env_then_default(google_session, monkeypatch):
    _auth_cli, http_cls, _google_auth = google_session

    monkeypatch.setenv("M8TES_BASE_URL", "https://staging.m8tes.ai")
    _ = GoogleIntegrationCLI(None).google
    assert http_cls.call_args.kwargs["base_url"] == "https://staging.m8tes.ai"

    monkeypatch.delenv("M8TES_BASE_URL")
    _ = GoogleIntegrationCLI(None).google
    assert http_cls.call_args.kwargs["base_url"] == "https://api.m8tes.ai"


def test_google_explicit_key_beats_client_beats_keychain(google_session):
    auth_cli, http_cls, _google_auth = google_session
    auth_cli.return_value.get_valid_api_key.return_value = "session-jwt"

    # An explicit --api-key wins outright — the keychain must not even be consulted,
    # because a macOS keychain prompt can block the whole command.
    _ = GoogleIntegrationCLI(Mock(api_key="m8_from_client"), api_key="m8_from_args").google
    assert http_cls.call_args.kwargs["api_key"] == "m8_from_args"
    auth_cli.assert_not_called()

    _ = GoogleIntegrationCLI(Mock(api_key="m8_from_client")).google
    assert http_cls.call_args.kwargs["api_key"] == "m8_from_client"
    auth_cli.assert_not_called()


def test_google_builds_one_transport_for_the_whole_command(google_session):
    _auth_cli, http_cls, _google_auth = google_session

    cli = GoogleIntegrationCLI(None)
    first, second = cli.google, cli.google
    cli.current_user()

    assert first is second
    assert http_cls.call_count == 1


@pytest.mark.parametrize(
    ("payload", "expected"),
    [({"user": {"id": 7}}, {"id": 7}), ({"id": 9}, {"id": 9})],
)
def test_google_current_user_unwraps_the_user_envelope(google_session, payload, expected):
    _auth_cli, http_cls, _google_auth = google_session
    http_cls.return_value.get.return_value = payload

    assert GoogleIntegrationCLI(None).current_user() == expected
    http_cls.return_value.get.assert_called_once_with("/api/v1/auth/me")


def test_google_streamlined_flow_gets_a_session_backed_adapter(google_session):
    _auth_cli, http_cls, google_auth = google_session
    http_cls.return_value.get.return_value = {"user": {"id": 11}}

    cli = GoogleIntegrationCLI(None)
    with patch("m8tes.cli.google.run_streamlined_oauth_flow") as flow:
        flow.return_value = {"integration_id": 1}
        result = cli._try_local_server_flow(8080, True)

    assert result == {"integration_id": 1}
    adapter = flow.call_args.kwargs["client"]
    assert flow.call_args.kwargs == {"client": adapter, "port": 8080, "auto_browser": True}
    assert adapter.google is google_auth.return_value
    assert adapter.get_current_user() == {"id": 11}


def test_google_status_reads_the_session_service(capsys):
    cli = GoogleIntegrationCLI(None)
    cli._google = Mock()
    cli._google.get_status.return_value = {
        "has_integration": True,
        "integration_id": 42,
        "customer_id": "123-456-7890",
    }

    cli.show_status()

    out = capsys.readouterr().out
    cli._google.get_status.assert_called_once_with()
    assert "✅ Status: Connected" in out
    assert "Integration ID: 42" in out
    assert "Customer ID: 123-456-7890" in out


def test_google_disconnect_uses_the_session_service(capsys):
    cli = GoogleIntegrationCLI(None)
    cli._google = Mock()
    cli._google.get_status.return_value = {"has_integration": True, "integration_id": 42}
    cli._google.disconnect.return_value = {"message": "Removed", "deleted_at": "2026-08-08"}

    with patch("builtins.input", return_value="y"):
        cli.disconnect_interactive()

    out = capsys.readouterr().out
    cli._google.disconnect.assert_called_once_with()
    assert "✅ Google Ads Integration Removed" in out
    assert "✅ Removed" in out
    assert "✅ Deleted at: 2026-08-08" in out


def test_google_customer_selection_uses_the_session_service():
    cli = GoogleIntegrationCLI(None)
    cli._google = Mock()
    cli._google.list_accessible_customers.return_value = {
        "accessible_customers": ["1234567890"],
        "refreshed": True,
    }
    cli._google.set_customer_id.return_value = {"customer_id": "1234567890"}

    assert cli._get_accessible_customers(refresh=True) == (["1234567890"], True)
    cli._google.list_accessible_customers.assert_called_once_with(refresh=True)

    assert cli._set_customer_id("123-456-7890", integration_id=42) == "1234567890"
    cli._google.set_customer_id.assert_called_once_with("1234567890", integration_id=42)


# ------------------------------------------------------------------- command layers


def test_google_commands_hand_the_cli_its_url_and_key():
    from m8tes.cli.commands.google import (
        ConnectCommand,
        DisconnectCommand,
        StatusCommand,
    )

    args = Namespace(
        base_url="http://127.0.0.1:8000",
        api_key="m8_cli",
        redirect_uri="http://localhost:8080/callback",
        no_browser=True,
        manual=True,
        port=8080,
    )

    for command in (ConnectCommand(), StatusCommand(), DisconnectCommand()):
        with patch("m8tes.cli.google.GoogleIntegrationCLI") as cli_cls:
            client = MagicMock()
            assert command.execute(args, client) == 0
            cli_cls.assert_called_once_with(
                client, base_url="http://127.0.0.1:8000", api_key="m8_cli"
            )


def test_integration_commands_survive_bare_args():
    """`args` without --base-url/--api-key must not explode (see test_cli_commands)."""
    from m8tes.cli.commands.google import StatusCommand as GoogleStatus

    for command, target in ((GoogleStatus(), "m8tes.cli.google.GoogleIntegrationCLI"),):
        with patch(target) as cli_cls:
            client = MagicMock()
            assert command.execute(Namespace(), client) == 0
            cli_cls.assert_called_once_with(client, base_url=None, api_key=None)
