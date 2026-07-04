"""`mate show` renders real Tools + Total Runs from the enriched v1 by-id payload.

Regression guard for the post-#586 gap: the by-id endpoint used to serialize a
schema-default `run_count: 0` / `tools: []`, so `mate show` printed "Tools: None"
and "Total Runs: 0" for active mates. The server now enriches every
AgentInstanceResponse endpoint; this pins the CLI side of the contract.
"""

from unittest.mock import Mock

from m8tes.cli.mates import MateCLI
from m8tes.instance import AgentInstance


def _cli_with_instance(payload: dict) -> MateCLI:
    client = Mock()
    client.instances.get.return_value = AgentInstance(Mock(), payload)
    return MateCLI(client)


def test_show_renders_enriched_tools_and_run_count(capsys):
    cli = _cli_with_instance(
        {
            "id": 42,
            "name": "PPC Mate",
            "status": "enabled",
            "tools": ["google", "slack"],
            "run_count": 7,
            "created_at": "2026-07-01T00:00:00Z",
        }
    )
    cli.get_interactive("42")
    out = capsys.readouterr().out
    assert "Tools: google, slack" in out
    assert "Total Runs: 7" in out


def test_show_hides_runs_line_when_api_omits_run_count(capsys):
    """Older servers omit run_count — the CLI must hide the line, not invent 0."""
    cli = _cli_with_instance(
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
    assert "Total Runs" not in out
    assert "Tools: None" in out
