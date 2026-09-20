"""Exercise parsed CLI commands through the real SDK's offline transport."""

from argparse import ArgumentParser
import json
from unittest.mock import patch

import pytest

from m8tes.cli.commands.mate import ChatCommand, TaskCommand
from m8tes.testing import MockM8tes, StreamBuilder, agent_payload, page_payload, run_payload


def parsed(command, argv):
    parser = ArgumentParser()
    command.add_arguments(parser)
    return parser.parse_args(argv)


@pytest.mark.parametrize("agent_id", [None, 7])
def test_task_scopes_lookup_and_run_and_selects_model(agent_id):
    client = MockM8tes()
    if agent_id is not None:
        client.mock.add("GET", "/agents/7?user_id=tenant-a", json=agent_payload(id=7))
    client.mock.add(
        "POST", "/runs/", stream=StreamBuilder().metadata(run_id=42).text("Hello").done()
    )
    command = TaskCommand()
    argv = ([str(agent_id)] if agent_id else []) + [
        "Hello",
        "--user-id",
        "tenant-a",
        "--model",
        "deepseek-v4-1-flash",
        "--output",
        "json",
    ]
    assert command.execute(parsed(command, argv), client) == 0
    body = client.mock.calls[-1].json
    assert body["user_id"] == "tenant-a"
    assert body["model"] == "deepseek-v4-1-flash"
    assert body.get("teammate_id") == agent_id
    assert len(client.mock.calls) == (2 if agent_id else 1)


def test_chat_scopes_selection_and_resume_then_replies_on_same_run():
    client = MockM8tes()
    client.mock.add(
        "GET",
        "/agents/?user_id=tenant-a",
        json=page_payload(agent_payload(id=7, status="enabled")),
    )
    client.mock.add("GET", "/agents/7?user_id=tenant-a", json=agent_payload(id=7))
    client.mock.add("GET", "/runs/42?user_id=tenant-a", json=run_payload(id=42, teammate_id=7))
    client.mock.add(
        "POST", "/runs/42/reply", stream=StreamBuilder().metadata(run_id=42).text("Hello").done()
    )
    command = ChatCommand()
    args = parsed(command, ["--user-id", "tenant-a", "--resume", "42", "--output", "compact"])
    with (
        patch("m8tes.cli.mates.confirm_prompt", return_value=True),
        patch("builtins.input", side_effect=["Hello", "/exit"]),
    ):
        assert command.execute(args, client) == 0
    assert client.mock.calls[-1].path == "/runs/42/reply"
    assert len(client.mock.calls) == 4


def test_new_chat_scopes_run_and_selects_model():
    client = MockM8tes()
    client.mock.add("GET", "/agents/7?user_id=tenant-a", json=agent_payload(id=7))
    client.mock.add(
        "POST", "/runs/", stream=StreamBuilder().metadata(run_id=42).text("Hello").done()
    )
    command = ChatCommand()
    args = parsed(command, ["7", "--user-id", "tenant-a", "--model", "deepseek-v4-1-flash"])
    with patch("builtins.input", side_effect=["Hello", "/exit"]):
        assert command.execute(args, client) == 0
    assert client.mock.calls[-1].json["user_id"] == "tenant-a"
    assert client.mock.calls[-1].json["model"] == "deepseek-v4-1-flash"


def test_json_task_failure_exits_nonzero_without_corrupting_json(capsys):
    client = MockM8tes()
    client.mock.add(
        "POST",
        "/runs/",
        stream=StreamBuilder().metadata(run_id=42).error("Provider unavailable").done(),
    )
    command = TaskCommand()
    args = parsed(command, ["Hello", "--user-id", "tenant-a", "--output", "json"])
    assert command.execute(args, client) == 1
    captured = capsys.readouterr()
    events = [json.loads(line) for line in captured.out.splitlines()]
    assert any(event["type"] == "error" for event in events)
    assert "Agent task failed" in captured.err


@pytest.mark.parametrize("resource", ["agent", "task"])
@pytest.mark.parametrize(
    "action", ["create", "list", "get", "update", "enable", "disable", "archive"]
)
def test_scoped_resource_lifecycle(resource, action):
    from m8tes.cli.commands import mate, task
    from m8tes.testing import task_payload

    module = mate if resource == "agent" else task
    command = getattr(module, action.title() + "Command")()
    payload = (agent_payload if resource == "agent" else task_payload)(
        id=7, status="disabled" if action == "enable" else "enabled", user_id="tenant-a"
    )
    path = f"/{resource}s"
    client = MockM8tes()
    argv = ["--user-id", "tenant-a"]
    if action == "create":
        argv += ["--non-interactive", "--name", "Example", "--instructions", "Say hello"]
        argv += ["--tools", "gmail"] if resource == "agent" else ["--agent-id", "8"]
        client.mock.add("POST", path + "/", json=payload)
    elif action == "list":
        client.mock.add("GET", path + "/?user_id=tenant-a", json=page_payload(payload))
    else:
        argv += ["7"]
        client.mock.add("GET", path + "/7?user_id=tenant-a", json=payload)
        if action == "update":
            argv += ["--name", "Renamed"]
            if resource == "agent":
                argv += ["--non-interactive"]
        if action in ("disable", "archive") and resource == "agent":
            argv += ["--force"]
        if action == "archive":
            client.mock.add("DELETE", path + "/7?user_id=tenant-a", status=204)
        elif action != "get":
            method = "POST" if resource == "agent" and action in ("enable", "disable") else "PATCH"
            suffix = "/" + action if method == "POST" else ""
            client.mock.add(method, path + "/7" + suffix + "?user_id=tenant-a", json=payload)
    assert command.execute(parsed(command, argv), client) == 0
    assert client.mock.calls
    if action == "create":
        assert client.mock.calls[-1].json["user_id"] == "tenant-a"
    else:
        assert all(call.params.get("user_id") == "tenant-a" for call in client.mock.calls)


@pytest.mark.parametrize("action", ["get", "list", "list-agent"])
def test_scoped_run_inspection(action):
    from m8tes.cli.commands.run import GetRunCommand, ListRunsCommand, ListTeammateRunsCommand

    command = {
        "get": GetRunCommand,
        "list": ListRunsCommand,
        "list-agent": ListTeammateRunsCommand,
    }[action]()
    client = MockM8tes()
    argv = ["--user-id", "tenant-a"] + ([] if action == "list" else ["7"])
    if action == "get":
        client.mock.add("GET", "/runs/7?user_id=tenant-a", json=run_payload(id=7))
        client.mock.add("GET", "/runs/7/outcome", json={"run_id": 7, "status": "completed"})
    else:
        client.mock.add("GET", "/runs/?user_id=tenant-a", json=page_payload(run_payload(id=7)))
    assert command.execute(parsed(command, argv), client) == 0
    assert client.mock.calls[0].params["user_id"] == "tenant-a"


def test_saved_task_execution_scopes_lookup_and_run():
    from m8tes.cli.commands.task import ExecuteCommand
    from m8tes.testing import task_payload

    client = MockM8tes()
    client.mock.add("GET", "/tasks/7?user_id=tenant-a", json=task_payload(id=7))
    client.mock.add("POST", "/tasks/7/runs", stream=StreamBuilder().text("Hello").done())
    command = ExecuteCommand()
    assert command.execute(parsed(command, ["7", "--user-id", "tenant-a"]), client) == 0
    assert client.mock.calls[-1].json["user_id"] == "tenant-a"


def test_interactive_agent_update_preserves_scope():
    from m8tes.cli.commands.mate import UpdateCommand

    client = MockM8tes()
    client.mock.add("GET", "/agents/7?user_id=tenant-a", json=agent_payload(id=7))
    client.mock.add("PATCH", "/agents/7?user_id=tenant-a", json=agent_payload(id=7))
    command = UpdateCommand()
    with (
        patch("m8tes.cli.mates.prompt", side_effect=["New name", ""]),
        patch("m8tes.cli.mates.confirm_prompt", return_value=True),
    ):
        assert command.execute(parsed(command, ["7", "--user-id", "tenant-a"]), client) == 0
    assert client.mock.calls[-1].json["name"] == "New name"
    assert "instructions" not in client.mock.calls[-1].json


@pytest.mark.parametrize("resource", ["agent", "task"])
def test_creation_next_step_commands_keep_shell_quoted_scope(resource, capsys):
    import shlex

    from m8tes.cli.commands import mate, task
    from m8tes.testing import task_payload

    # Tenant IDs are opaque strings, not necessarily shell-safe identifiers.
    tenant = "customer's account"
    client = MockM8tes()
    payload = (agent_payload if resource == "agent" else task_payload)(id=7, user_id=tenant)
    client.mock.add("POST", f"/{resource}s/", json=payload)
    command = (mate if resource == "agent" else task).CreateCommand()
    argv = [
        "--user-id",
        tenant,
        "--non-interactive",
        "--name",
        "Example",
        "--instructions",
        "Say hello",
    ]
    argv += ["--tools", "gmail"] if resource == "agent" else ["--agent-id", "8"]
    assert command.execute(parsed(command, argv), client) == 0
    commands = [
        shlex.split(line.strip())
        for line in capsys.readouterr().out.splitlines()
        if line.strip().startswith("m8tes ") and "--help" not in line
    ]
    assert commands
    for args in commands:
        assert "--user-id" in args
        assert args[args.index("--user-id") + 1] == tenant


def test_create_agent_without_integrations():
    from m8tes.cli.commands.mate import CreateCommand

    client = MockM8tes()
    client.mock.add("POST", "/agents/", json=agent_payload(id=7, tools=[]))
    command = CreateCommand()
    args = parsed(
        command,
        [
            "--non-interactive",
            "--name",
            "Hello",
            "--instructions",
            "Say hello",
            "--user-id",
            "tenant-a",
        ],
    )
    assert command.execute(args, client) == 0
    assert client.mock.calls[-1].json["tools"] == []


def test_interactive_create_accepts_current_app_ids():
    from m8tes.cli.commands.mate import CreateCommand

    client = MockM8tes()
    client.mock.add("POST", "/agents/", json=agent_payload(id=7, tools=["gmail", "slack"]))
    command = CreateCommand()
    with (
        patch("m8tes.cli.mates.prompt", side_effect=["", "Example", "gmail, slack, gmail", ""]),
        patch("builtins.input", side_effect=["Say hello", "", ""]),
        patch("m8tes.cli.mates.confirm_prompt", return_value=True),
    ):
        assert command.execute(parsed(command, ["--user-id", "tenant-a"]), client) == 0
    assert client.mock.calls[-1].json["tools"] == ["gmail", "slack"]
    assert client.mock.calls[-1].json["user_id"] == "tenant-a"


def test_json_debug_keeps_only_events_on_stdout(capsys):
    client = MockM8tes()
    client.mock.add("POST", "/runs/", stream=StreamBuilder().text("Hello").done())
    command = TaskCommand()
    assert (
        command.execute(
            parsed(command, ["Hello", "--user-id", "tenant-a", "--output", "json", "--debug"]),
            client,
        )
        == 0
    )
    captured = capsys.readouterr()
    assert [json.loads(line) for line in captured.out.splitlines()]
    assert "[DEBUG]" in captured.err


def test_json_auth_failure_keeps_stdout_empty(capsys):
    client = MockM8tes()
    client.mock.add(
        "POST",
        "/runs/",
        status=401,
        json={"error": {"message": "Invalid API key", "type": "authentication_error"}},
    )
    command = TaskCommand()
    assert (
        command.execute(
            parsed(command, ["Hello", "--user-id", "tenant-a", "--output", "json"]), client
        )
        == 1
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Authentication failed" in captured.err


def test_interactive_task_creation_keeps_scope_from_selection_through_write():
    from m8tes.cli.commands.task import CreateCommand
    from m8tes.testing import task_payload

    client = MockM8tes()
    client.mock.add("GET", "/agents/?user_id=tenant-a", json=page_payload(agent_payload(id=7)))
    client.mock.add("POST", "/tasks/", json=task_payload(id=8, user_id="tenant-a"))
    command = CreateCommand()
    with (
        patch("m8tes.cli.prompt.prompt", side_effect=["7", "recap", "", ""]),
        patch("m8tes.cli.prompt.confirm_prompt", return_value=True),
        patch("builtins.input", side_effect=["Say hello", "", ""]),
    ):
        assert command.execute(parsed(command, ["--user-id", "tenant-a"]), client) == 0
    assert client.mock.calls[-1].json["user_id"] == "tenant-a"
    assert client.mock.calls[-1].json["teammate_id"] == 7
