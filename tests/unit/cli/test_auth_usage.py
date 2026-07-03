"""`m8tes auth usage` must render the wire format without crashing.

The v2 usage payload sends cost_used/cost_limit as decimal STRINGS (exact
money). Formatting them with `:.2f` directly raised "Unknown format code 'f'
for object of type 'str'" — caught live in the 2026-07-01 DX e2e.
"""

from argparse import Namespace
from contextlib import contextmanager
from unittest.mock import Mock, patch

from m8tes._types import Usage
from m8tes.cli.commands.auth import UsageCommand


def _usage() -> Usage:
    return Usage(
        plan="trial",
        runs_used=2,
        runs_limit=5,
        cost_used="0.311611",
        cost_limit="20.0",
        period_end="2026-07-31T20:38:40",
        subscription_status=None,
    )


def test_usage_formats_decimal_string_costs(capsys):
    v2_client = Mock()
    v2_client.auth.get_usage.return_value = _usage()

    @contextmanager
    def fake_client(_args, _client=None):
        yield v2_client

    with patch("m8tes.cli.commands.auth.v2_client_from_args", fake_client):
        assert UsageCommand().execute(Namespace(), None) == 0

    out = capsys.readouterr().out
    assert "Cost: $0.31 / $20.00" in out
    assert "Runs: 2 / 5" in out
