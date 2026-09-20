"""Exercise CLI composition before commands receive their already-built client."""

from argparse import Namespace
from unittest.mock import patch

import pytest

from m8tes.cli.main import _real_main, create_client
from m8tes.cli.v2 import create_v2_client
from m8tes.testing import MockM8tes


@pytest.mark.parametrize("entrypoint", ["main", "bridge"])
@pytest.mark.parametrize("explicit", [None, "m8_explicit"])
def test_environment_key_beats_saved_login_without_refresh(entrypoint, explicit, monkeypatch):
    monkeypatch.setenv("M8TES_API_KEY", "m8_environment")
    auth_symbol = "m8tes.cli.auth.AuthCLI" if entrypoint == "main" else "m8tes.cli.v2.AuthCLI"
    with patch(auth_symbol) as auth:
        auth.return_value.get_valid_api_key.return_value = "jwt_saved"
        client = (
            create_client(api_key=explicit)
            if entrypoint == "main"
            else create_v2_client(Namespace(api_key=explicit, base_url=None))
        )
        try:
            assert client.api_key == (explicit or "m8_environment")
            assert client.api_key_from_profile is False
            auth.assert_not_called()
        finally:
            client.close()


def test_json_missing_credentials_diagnostic_never_enters_stdout(monkeypatch, capsys):
    monkeypatch.delenv("M8TES_API_KEY", raising=False)
    with patch("m8tes.cli.auth.AuthCLI") as auth, pytest.raises(SystemExit) as error:
        auth.return_value.get_valid_api_key.return_value = None
        _real_main(["agent", "task", "Hello", "--user-id", "tenant-a", "--output", "json"])
    assert error.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "No API key" in captured.err


def test_json_unexpected_failure_diagnostic_never_enters_stdout(capsys):
    client = MockM8tes()
    with (
        patch("m8tes.cli.main.create_client", return_value=client),
        patch.object(client.runs, "create", side_effect=RuntimeError("transport failed")),
    ):
        assert (
            _real_main(["agent", "task", "Hello", "--user-id", "tenant-a", "--output", "json"]) == 1
        )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "transport failed" in captured.err
