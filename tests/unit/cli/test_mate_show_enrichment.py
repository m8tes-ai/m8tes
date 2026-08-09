"""`mate show` renders Tools from the real v2 agent payload.

Ported from the v1 enrichment guard (post-#586). The v2 Teammate carries no
run_count, so the "Total Runs" line is gone entirely; this pins that Tools
render from the payload and an empty toolset prints "None" instead of crashing.
"""

from unittest.mock import Mock

from m8tes._types import Teammate
from m8tes.cli.mates import MateCLI


def _cli_with_agent(payload: dict) -> MateCLI:
    client = Mock()
    client.agents.get.return_value = Teammate.from_dict(payload)
    return MateCLI(client)


def test_show_renders_tools(capsys):
    cli = _cli_with_agent(
        {
            "id": 42,
            "name": "PPC Mate",
            "status": "enabled",
            "tools": ["google", "slack"],
            "created_at": "2026-07-01T00:00:00Z",
        }
    )
    cli.get_interactive("42")
    out = capsys.readouterr().out
    assert "Tools: google, slack" in out
    assert "Status: enabled" in out


def test_show_renders_none_for_empty_tools(capsys):
    cli = _cli_with_agent(
        {
            "id": 42,
            "name": "PPC Mate",
            "status": "enabled",
            "tools": [],
            "created_at": "2026-07-01T00:00:00Z",
        }
    )
    cli.get_interactive("42")
    out = capsys.readouterr().out
    assert "Tools: None" in out
    assert "Total Runs" not in out  # dropped with v2 — Teammate has no run_count
