from unittest.mock import MagicMock, patch

import pytest

from m8tes.cli.google import GoogleIntegrationCLI


@pytest.fixture()
def google_cli():
    return GoogleIntegrationCLI(client=MagicMock())


def test_existing_customer_retained_when_accessible(google_cli):
    status = {
        "customer_id": "123-456-7890",
        "accessible_customers": ["123-456-7890", "999-999-9999"],
    }

    with (
        patch.object(google_cli, "_prompt_customer_choice") as prompt_choice,
        patch.object(google_cli, "_set_customer_id") as set_customer,
        patch.object(google_cli, "_get_accessible_customers") as get_customers,
    ):
        selected = google_cli._ensure_customer_selection(status=status)

    assert selected == "1234567890"
    prompt_choice.assert_not_called()
    set_customer.assert_not_called()
    get_customers.assert_not_called()


def test_stale_customer_triggers_selection_prompt(google_cli):
    status = {
        "customer_id": "974-100-3352",
        "accessible_customers": ["6179730754", "5284151431", "6197468292"],
    }
    result = {
        "integration_id": 42,
        "accessible_customers": ["6179730754", "5284151431", "6197468292"],
    }

    with (
        patch.object(
            google_cli, "_prompt_customer_choice", return_value="6179730754"
        ) as prompt_choice,
        patch.object(google_cli, "_set_customer_id", return_value="6179730754") as set_customer,
        patch.object(google_cli, "_get_accessible_customers") as get_customers,
        patch("builtins.print") as mock_print,
    ):
        selected = google_cli._ensure_customer_selection(status=status, result=result)

    assert selected == "6179730754"
    prompt_choice.assert_called_once_with(["6179730754", "5284151431", "6197468292"])
    set_customer.assert_called_once_with("6179730754", integration_id=42)
    get_customers.assert_not_called()

    printed_messages = [
        "".join(str(arg) for arg in call.args) for call in mock_print.call_args_list
    ]
    assert any("stored Google Ads customer no longer appears" in msg for msg in printed_messages)


def test_customer_selection_shows_helpful_hint(google_cli):
    """Test that customer selection displays helpful hint about finding account names."""
    customers = ["1234567890", "9876543210"]

    with (
        patch("builtins.input", return_value="1"),  # User selects first customer
        patch("builtins.print") as mock_print,
    ):
        selected = google_cli._prompt_customer_choice(customers)

    assert selected == "1234567890"

    # Verify the helpful hint was printed
    printed_messages = [
        "".join(str(arg) for arg in call.args) for call in mock_print.call_args_list
    ]

    # Check for tip about finding account names in Google Ads
    assert any(
        "tip" in msg.lower()
        and "google ads" in msg.lower()
        and ("account" in msg.lower() or "name" in msg.lower())
        for msg in printed_messages
    ), "Helpful hint about finding account names should be displayed"
