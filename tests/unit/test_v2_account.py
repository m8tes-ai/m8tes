"""Tests for the v2 Account resource."""

from unittest.mock import MagicMock

import pytest

from m8tes._client import M8tes
from m8tes._exceptions import ValidationError
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


def test_account_revoke_sessions_calls_endpoint():
    """Wire test: the method must POST the route, with no body and no scoping.

    Revocation is always account-wide (`token_version` is the only lever), so a `user_id`
    here would imply a per-end-user revocation the API cannot do.
    """
    http = MagicMock()
    http.request.return_value.json.return_value = {"sessions_revoked": True}

    result = AccountResource(http).revoke_sessions()

    http.request.assert_called_once_with("POST", "/account/sessions/revoke")
    assert result["sessions_revoked"] is True


def test_account_add_reply_address_posts_the_address():
    """Wire test: one POST with the address in the body, no scoping.

    The list is the account's own, so a `user_id` here would imply a per-end-user list the
    API does not have.
    """
    http = MagicMock()
    http.request.return_value.json.return_value = {
        "status": "confirmation_sent",
        "email": "jacob@example.com",
    }

    result = AccountResource(http).add_reply_address("jacob@example.com")

    http.request.assert_called_once_with(
        "POST", "/account/reply-addresses", json={"email": "jacob@example.com"}
    )
    assert result["status"] == "confirmation_sent"


def test_account_list_reply_addresses_calls_endpoint():
    http = MagicMock()
    http.request.return_value.json.return_value = {
        "data": [{"id": 3, "email": "jacob@example.com", "verified_at": "2026-11-10T12:00:00"}],
        "has_more": False,
    }

    result = AccountResource(http).list_reply_addresses()

    http.request.assert_called_once_with("GET", "/account/reply-addresses")
    assert result["data"][0]["id"] == 3


def test_account_remove_reply_address_deletes_by_id():
    http = MagicMock()

    assert AccountResource(http).remove_reply_address(3) is None

    http.request.assert_called_once_with("DELETE", "/account/reply-addresses/3")


def test_account_remove_reply_address_cannot_be_steered_to_another_path():
    """The id is one path segment (the shared `seg` guard): a separator is refused, never sent."""
    http = MagicMock()

    with pytest.raises(ValidationError):
        AccountResource(http).remove_reply_address("../sessions/revoke")  # type: ignore[arg-type]

    http.request.assert_not_called()
