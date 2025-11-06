"""Tests for CLI prompt utilities."""

import builtins

import pytest

from m8tes.cli import prompt as prompt_module


def test_secure_prompt_preserves_whitespace(monkeypatch):
    """Ensure secure_prompt does not strip whitespace from passwords."""

    captured_password = "secret  "

    def fake_getpass(label):
        assert label == "Password: "
        return captured_password

    monkeypatch.setattr(prompt_module, "getpass", fake_getpass)

    result = prompt_module.secure_prompt("Password: ")

    assert result == captured_password


def test_prompt_strips_trailing_whitespace(monkeypatch):
    """Regular prompt should continue trimming user input."""

    monkeypatch.setattr(builtins, "input", lambda label: "  value  ")

    result = prompt_module.prompt("Label: ")

    assert result == "value"


@pytest.mark.parametrize(
    "response, expected",
    [("", False), ("y", True), ("Yes", True), ("n", False), ("No", False)],
)
def test_confirm_prompt_basic(monkeypatch, response, expected):
    """Spot-check confirm prompt behavior."""

    inputs = iter([response])
    monkeypatch.setattr(builtins, "input", lambda _: next(inputs))

    assert prompt_module.confirm_prompt("Proceed?", default=False) is expected
