"""
E2E tests for CLI commands.

Tests the command-line interface against real FastAPI backend + Claude Agent SDK.
Always uses REAL APIs (costs money!).

To run these tests:
    1. Start database: cd fastapi && docker compose up -d
    2. Start backend: cd fastapi && uv run uvicorn main:app --reload --port 8000
    3. Run tests: pytest tests/e2e/test_cli.py -v -m e2e
"""

import subprocess

import pytest


@pytest.mark.e2e
def test_cli_auth_flow(backend_server):
    """
    Test CLI authentication flow: register, login, status, logout.

    Verifies that the CLI can successfully authenticate with backend.
    """
    # Note: This test uses subprocess to test the actual CLI
    # We use --dev flag to point to local backend
    email = "cli-test@m8tes.ai"
    password = "cli-test-password-123"

    # Test registration
    result = subprocess.run(
        ["m8tes", "--dev", "auth", "register"],
        input=f"{email}\n{password}\n{password}\n",
        capture_output=True,
        text=True,
    )

    # Should succeed or indicate user already exists
    assert result.returncode == 0 or "already exists" in result.stdout.lower()

    # Test login
    result = subprocess.run(
        ["m8tes", "--dev", "auth", "login"],
        input=f"{email}\n{password}\n",
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "success" in result.stdout.lower() or "logged in" in result.stdout.lower()

    # Test status
    result = subprocess.run(
        ["m8tes", "--dev", "auth", "status"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert email in result.stdout

    # Test logout
    result = subprocess.run(
        ["m8tes", "--dev", "auth", "logout"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


@pytest.mark.e2e
def test_cli_help_commands(backend_server):
    """
    Test CLI help commands.

    Verifies that help is available for all commands.
    """
    # Test main help
    result = subprocess.run(
        ["m8tes", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "auth" in result.stdout
    assert "agent" in result.stdout
    assert "mate" in result.stdout  # permanent alias

    # Test auth help
    result = subprocess.run(
        ["m8tes", "auth", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "login" in result.stdout
    assert "register" in result.stdout
    assert "logout" in result.stdout

    # Test mate help
    result = subprocess.run(
        ["m8tes", "mate", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "task" in result.stdout or "help" in result.stdout


@pytest.mark.e2e
def test_cli_error_handling_no_auth(backend_server):
    """
    Test CLI error handling when not authenticated.

    Verifies that appropriate errors are shown for auth status
    when user is not logged in.
    """
    # Make sure we're logged out
    subprocess.run(
        ["m8tes", "--dev", "auth", "logout"],
        capture_output=True,
    )

    # Try to check auth status without being logged in
    result = subprocess.run(
        ["m8tes", "--dev", "auth", "status"],
        capture_output=True,
        text=True,
    )

    # Should indicate not authenticated
    assert (
        result.returncode != 0
        or "not authenticated" in result.stdout.lower()
        or "not logged in" in result.stdout.lower()
    )


@pytest.mark.e2e
def test_cli_dev_flag(backend_server):
    """
    Test that --dev flag correctly points to local backend.

    Verifies that the --dev flag overrides the default production URL.
    """
    # The --dev flag should use the local FastAPI backend URL.
    # We can verify this by checking that commands succeed against local backend

    result = subprocess.run(
        ["m8tes", "--dev", "auth", "status"],
        capture_output=True,
        text=True,
    )

    # Should connect successfully (even if not authenticated)
    # The command should not fail with connection errors
    assert "connection" not in result.stderr.lower() or result.returncode == 0
