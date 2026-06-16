"""Tests for the v2 Account resource."""

from unittest.mock import MagicMock

from m8tes._client import M8tes
from m8tes._resources import Account
from m8tes._resources.account import Account as AccountResource


def test_account_namespace():
    client = M8tes(api_key="m8_test", base_url="http://localhost")
    assert isinstance(client.account, Account)


def test_account_delete_calls_endpoint():
    http = MagicMock()
    http.request.return_value.json.return_value = {
        "status": "deletion_requested",
        "grace_period_days": 30,
    }
    result = AccountResource(http).delete()

    http.request.assert_called_once_with("DELETE", "/account")
    assert result["status"] == "deletion_requested"
    assert result["grace_period_days"] == 30


def test_account_export_calls_endpoint():
    http = MagicMock()
    http.request.return_value.json.return_value = {"account": {"email": "a@b.com"}, "teammates": []}
    result = AccountResource(http).export()

    http.request.assert_called_once_with("GET", "/account/export")
    assert result["account"]["email"] == "a@b.com"
