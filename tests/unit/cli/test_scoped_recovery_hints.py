"""Recovery commands must remain usable in the caller's strict tenant scope."""

from argparse import ArgumentParser
import shlex
from unittest.mock import patch

import pytest

from m8tes._exceptions import NotFoundError
from m8tes.cli.commands.run import GetRunCommand, RetryRunCommand
from m8tes.cli.mates import MateCLI
from m8tes.testing import MockM8tes, agent_payload, page_payload, run_payload

TENANT = "customer's team; $(echo unsafe)"


def command_tokens(output, prefix):
    line = next(line for line in output.splitlines() if prefix in line)
    return shlex.split(line[line.index("m8tes ") :])


def assert_scope(tokens, tenant):
    if tenant is None:
        assert "--user-id" not in tokens
    else:
        assert "--user-id" in tokens, "Recovery command dropped the tenant scope"
        assert tokens[tokens.index("--user-id") + 1] == tenant


@pytest.mark.parametrize("tenant", [None, TENANT])
@pytest.mark.parametrize("action", ["select", "list", "archive"])
def test_agent_recovery_commands_keep_scope(action, tenant, capsys):
    client = MockM8tes()
    scope = {"user_id": tenant} if tenant is not None else {}
    cli = MateCLI(client, **scope)
    if action == "archive":
        with (
            patch.object(client.agents, "get", side_effect=NotFoundError("Not found")),
            pytest.raises(NotFoundError),
        ):
            cli.archive_interactive("7", force=True)
        prefix = "m8tes agent list"
    else:
        client.mock.add("GET", "/agents/", json=page_payload())
        if action == "select":
            assert cli.select_or_confirm_mate(None, **scope) is None
        else:
            cli.list_interactive(**scope)
        prefix = "m8tes agent create"
    output = capsys.readouterr().out
    assert_scope(command_tokens(output, prefix), tenant)
    if action == "list":
        assert_scope(command_tokens(output, "m8tes agent list"), tenant)


@pytest.mark.parametrize("tenant", [None, TENANT])
def test_retry_watch_command_uses_returned_scope(tenant, capsys):
    client = MockM8tes()
    client.mock.add(
        "POST", "/runs/7/retry", json=run_payload(id=42, retry_of_run_id=7, user_id=tenant)
    )
    command = RetryRunCommand()
    parser = ArgumentParser()
    command.add_arguments(parser)
    assert command.execute(parser.parse_args(["7"]), client) == 0
    tokens = command_tokens(capsys.readouterr().out, "m8tes run get")
    assert tokens[:4] == ["m8tes", "run", "get", "42"]
    assert_scope(tokens, tenant)
    # Follow the printed command through the parser and SDK, as a caller would.
    client.mock.add("GET", "/runs/42", json=run_payload(id=42, user_id=tenant))
    client.mock.add("GET", "/runs/42/outcome", json={"run_id": 42, "status": "completed"})
    followup = GetRunCommand()
    followup_parser = ArgumentParser()
    followup.add_arguments(followup_parser)
    assert followup.execute(followup_parser.parse_args(tokens[3:]), client) == 0
    assert client.mock.calls[-2].params.get("user_id") == tenant


@pytest.mark.parametrize("tenant", [None, TENANT])
def test_interrupted_chat_recovery_command_keeps_scope(tenant, capsys):
    class PreMetadataInterrupt:
        run_id = None

        def __iter__(self):
            raise KeyboardInterrupt

    client = MockM8tes()
    client.mock.add("GET", "/agents/7", json=agent_payload(id=7, user_id=tenant))
    with (
        patch.object(client.runs, "create", return_value=PreMetadataInterrupt()),
        patch("builtins.input", side_effect=["Hello", "/exit"]),
    ):
        MateCLI(client).chat_interactive("7", user_id=tenant)
    assert_scope(command_tokens(capsys.readouterr().out, "m8tes run list"), tenant)
