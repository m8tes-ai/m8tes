"""Failure paths must exit non-zero.

The CLI contract is: interactive helpers raise on fatal errors, the command
layer prints (or relies on the helper's richer message) and returns 1. These
tests pin the contract for every command whose helper used to swallow the
error and let the command return 0 — which silently broke scripting/CI
(`m8tes mate list && deploy` would proceed on auth failure).
"""

from argparse import Namespace
from unittest.mock import Mock

from m8tes.cli.commands.auth import LoginCommand, RegisterCommand
from m8tes.cli.commands.mate import (
    ArchiveCommand as MateArchiveCommand,
    DisableCommand as MateDisableCommand,
    EnableCommand as MateEnableCommand,
    GetCommand as MateGetCommand,
    ListCommand as MateListCommand,
    UpdateCommand as MateUpdateCommand,
)
from m8tes.cli.commands.task import (
    ArchiveCommand as TaskArchiveCommand,
    DisableCommand as TaskDisableCommand,
    EnableCommand as TaskEnableCommand,
    ExecuteCommand as TaskExecuteCommand,
    GetCommand as TaskGetCommand,
    ListCommand as TaskListCommand,
    UpdateCommand as TaskUpdateCommand,
)
from m8tes.exceptions import AuthenticationError, NetworkError


def _client_raising(attr_path: str, exc: Exception) -> Mock:
    """Build a mock client whose `client.<attr_path>` raises exc."""
    client = Mock()
    obj = client
    *parents, leaf = attr_path.split(".")
    for name in parents:
        obj = getattr(obj, name)
    getattr(obj, leaf).side_effect = exc
    return client


class TestMateCommandExitCodes:
    def test_list_auth_failure_exits_1(self):
        client = _client_raising("instances.list", AuthenticationError("Invalid API key"))
        assert MateListCommand().execute(Namespace(), client) == 1

    def test_get_auth_failure_exits_1(self):
        client = _client_raising("instances.get", AuthenticationError("Invalid API key"))
        assert MateGetCommand().execute(Namespace(mate_id="1"), client) == 1

    def test_get_non_numeric_id_exits_1(self):
        assert MateGetCommand().execute(Namespace(mate_id="abc"), Mock()) == 1

    def test_update_network_failure_exits_1(self):
        client = _client_raising("instances.get", NetworkError("connection refused"))
        args = Namespace(mate_id="1", non_interactive=True, name="x")
        assert MateUpdateCommand().execute(args, client) == 1

    def test_enable_failure_exits_1(self):
        client = _client_raising("instances.get", NetworkError("connection refused"))
        assert MateEnableCommand().execute(Namespace(mate_id="1"), client) == 1

    def test_disable_failure_exits_1(self):
        client = _client_raising("instances.get", NetworkError("connection refused"))
        assert MateDisableCommand().execute(Namespace(mate_id="1", force=True), client) == 1

    def test_archive_failure_exits_1(self):
        client = _client_raising("instances.get", NetworkError("connection refused"))
        assert MateArchiveCommand().execute(Namespace(mate_id="1", force=True), client) == 1


class TestTaskCommandExitCodes:
    def test_list_auth_failure_exits_1(self):
        client = _client_raising("tasks.list", AuthenticationError("Invalid API key"))
        assert TaskListCommand().execute(Namespace(), client) == 1

    def test_get_failure_exits_1(self):
        client = _client_raising("tasks.get", NetworkError("connection refused"))
        assert TaskGetCommand().execute(Namespace(task_id="1"), client) == 1

    def test_get_non_numeric_id_exits_1(self):
        assert TaskGetCommand().execute(Namespace(task_id="abc"), Mock()) == 1

    def test_execute_failure_exits_1(self):
        client = _client_raising("tasks.get", NetworkError("connection refused"))
        assert TaskExecuteCommand().execute(Namespace(task_id="1"), client) == 1

    def test_update_failure_exits_1(self):
        client = _client_raising("tasks.update", NetworkError("connection refused"))
        assert TaskUpdateCommand().execute(Namespace(task_id="1", name="x"), client) == 1

    def test_enable_failure_exits_1(self):
        client = _client_raising("tasks.enable", NetworkError("connection refused"))
        assert TaskEnableCommand().execute(Namespace(task_id="1"), client) == 1

    def test_disable_failure_exits_1(self):
        client = _client_raising("tasks.disable", NetworkError("connection refused"))
        assert TaskDisableCommand().execute(Namespace(task_id="1"), client) == 1

    def test_archive_failure_exits_1(self):
        client = _client_raising("tasks.archive", NetworkError("connection refused"))
        assert TaskArchiveCommand().execute(Namespace(task_id="1"), client) == 1

    def test_archive_returning_false_exits_1(self):
        client = Mock()
        client.tasks.archive.return_value = False
        assert TaskArchiveCommand().execute(Namespace(task_id="1"), client) == 1


class TestAuthCommandExitCodes:
    def test_login_failure_exits_1(self, monkeypatch):
        from m8tes.cli import auth as auth_module

        monkeypatch.setattr(
            auth_module.AuthCLI,
            "login_interactive",
            lambda self, save_token=True: (_ for _ in ()).throw(
                AuthenticationError("bad credentials")
            ),
        )
        assert LoginCommand().execute(Namespace(), None) == 1

    def test_register_failure_exits_1(self, monkeypatch):
        from m8tes.cli import auth as auth_module

        monkeypatch.setattr(
            auth_module.AuthCLI,
            "register_interactive",
            lambda self: (_ for _ in ()).throw(NetworkError("connection refused")),
        )
        assert RegisterCommand().execute(Namespace(), None) == 1
