"""TaskCLI runs on the v2 SDK client.

Pins the mapping the port had to get right — v2 keyword names (`agent_id`,
`teammate_id`), `SyncPage.data`, `tasks.run(...)` for execution, `tasks.delete`
for archive, and the status toggle riding `tasks.update(status=...)` (the v2
field added alongside this port).

The client is mocked: these are contract tests over the call the CLI makes, not
over HTTP. A structural guard at the bottom keeps both modules off the legacy
v1 client for good.
"""

import ast
from pathlib import Path
from unittest.mock import Mock

import pytest

from m8tes._exceptions import RunFailedError
from m8tes._types import SyncPage, Task, Teammate
from m8tes.cli.tasks import TaskCLI


def _task(**overrides) -> Task:
    data = {
        "id": 42,
        "teammate_id": 7,
        "name": "weekly recap",
        "instructions": "Summarize the week",
        "expected_output": "A short report",
        "goals": "Keep the team current",
        "status": "enabled",
        "created_at": "2026-08-01T10:00:00Z",
    }
    data.update(overrides)
    return Task.from_dict(data)


def _agent(**overrides) -> Teammate:
    data = {"id": 7, "name": "Ops Mate", "role": "Operator", "status": "enabled"}
    data.update(overrides)
    return Teammate.from_dict(data)


def _client(tasks=(), agents=()) -> Mock:
    client = Mock()
    client.tasks.list.return_value = SyncPage(data=list(tasks), has_more=False)
    client.agents.list.return_value = SyncPage(data=list(agents), has_more=False)
    return client


class TestCreate:
    def test_create_non_interactive_uses_v2_agent_id(self, capsys):
        client = _client()
        client.tasks.create.return_value = _task(id=99, name="cut wasted ad spend")

        TaskCLI(client).create_non_interactive(
            mate_id="7",
            name="cut wasted ad spend",
            instructions="Pause the losers",
            expected_output="A report",
            goals="Lower CPA",
        )

        client.tasks.create.assert_called_once_with(
            agent_id=7,
            name="cut wasted ad spend",
            instructions="Pause the losers",
            expected_output="A report",
            goals="Lower CPA",
        )
        out = capsys.readouterr().out
        assert "✅ Task created successfully!" in out
        assert "ID: 99" in out
        assert "m8tes task execute 99" in out

    def test_create_non_interactive_rejects_non_numeric_mate_id(self):
        client = _client()

        with pytest.raises(Exception, match="Teammate ID must be a number"):
            TaskCLI(client).create_non_interactive(mate_id="abc", name="x", instructions="y")

        client.tasks.create.assert_not_called()

    def test_create_interactive_lists_v2_agents_then_creates(self, monkeypatch, capsys):
        client = _client(agents=[_agent(id=7, name="Ops Mate")])
        client.tasks.create.return_value = _task(id=99)

        answers = iter(["7", "recap", "", ""])
        monkeypatch.setattr("m8tes.cli.prompt.prompt", lambda *a, **k: next(answers))
        monkeypatch.setattr("m8tes.cli.prompt.confirm_prompt", lambda *a, **k: True)
        monkeypatch.setattr("builtins.input", iter(["Do the thing", "", ""]).__next__)

        TaskCLI(client).create_interactive()

        client.agents.list.assert_called_once_with()
        client.tasks.create.assert_called_once_with(
            agent_id=7,
            name="recap",
            instructions="Do the thing",
            expected_output=None,
            goals=None,
        )
        assert "7: Ops Mate" in capsys.readouterr().out

    def test_create_interactive_stops_when_no_agents(self, capsys):
        client = _client(agents=[])

        TaskCLI(client).create_interactive()

        client.tasks.create.assert_not_called()
        assert "❌ No agents available. Create an agent first." in capsys.readouterr().out


class TestList:
    def test_list_pages_v2_and_prints_teammate_id(self, capsys):
        client = _client(tasks=[_task(id=42, teammate_id=7)])

        TaskCLI(client).list_interactive()

        client.tasks.list.assert_called_once_with(agent_id=None, include_archived=False)
        out = capsys.readouterr().out
        assert "✅ weekly recap" in out
        assert "ID: 42" in out
        assert "Agent: 7" in out

    def test_list_passes_agent_id_filter(self):
        client = _client(tasks=[])

        TaskCLI(client).list_interactive(mate_id="7")

        client.tasks.list.assert_called_once_with(agent_id=7, include_archived=False)

    def test_list_hides_disabled_tasks_by_default(self, capsys):
        client = _client(tasks=[_task(id=1, name="on"), _task(id=2, name="off", status="disabled")])

        TaskCLI(client).list_interactive()

        out = capsys.readouterr().out
        assert "on" in out
        assert "off" not in out

    def test_list_include_disabled_shows_them(self, capsys):
        client = _client(tasks=[_task(id=2, name="off", status="disabled")])

        TaskCLI(client).list_interactive(include_disabled=True)

        assert "off" in capsys.readouterr().out

    def test_list_status_filter_selects_only_that_status(self, capsys):
        client = _client(tasks=[_task(id=1, name="on"), _task(id=2, name="off", status="disabled")])

        TaskCLI(client).list_interactive(status="disabled")

        out = capsys.readouterr().out
        assert "off" in out
        assert "on\n" not in out

    def test_include_archived_passes_the_query_param(self):
        client = _client(tasks=[])

        TaskCLI(client).list_interactive(include_archived=True)

        assert client.tasks.list.call_args.kwargs["include_archived"] is True

        TaskCLI(client).list_interactive()

        assert client.tasks.list.call_args.kwargs["include_archived"] is False

    def test_list_empty_prints_hint(self, capsys):
        TaskCLI(_client(tasks=[])).list_interactive()

        assert "No tasks found." in capsys.readouterr().out


class TestGet:
    def test_get_reads_v2_task(self, capsys):
        client = _client()
        client.tasks.get.return_value = _task(id=42, teammate_id=7)

        TaskCLI(client).get_interactive("42")

        client.tasks.get.assert_called_once_with(42)
        out = capsys.readouterr().out
        assert "ID: 42" in out
        assert "Agent: 7" in out
        assert "Expected output: A short report" in out


class TestExecute:
    def _display(self, monkeypatch, *, has_errors=False, errors=()):
        display = Mock()
        display.accumulator.has_errors.return_value = has_errors
        display.accumulator.get_errors.return_value = list(errors)
        monkeypatch.setattr("m8tes.cli.display.create_display", lambda fmt: display)
        return display

    def test_execute_streams_the_v2_run(self, monkeypatch, capsys):
        display = self._display(monkeypatch)
        client = _client()
        client.tasks.get.return_value = _task(id=42, name="weekly recap")
        client.tasks.run.return_value = iter(["event-1", "event-2"])

        TaskCLI(client).execute_interactive("42")

        client.tasks.run.assert_called_once_with(42, stream=True)
        assert display.on_event.call_count == 2
        out = capsys.readouterr().out
        assert "🎯 Executing task: weekly recap" in out
        assert "✅ Task completed" in out

    def test_execute_raises_when_the_run_emitted_errors(self, monkeypatch, capsys):
        self._display(monkeypatch, has_errors=True, errors=["credential expired"])
        client = _client()
        client.tasks.get.return_value = _task(id=42)
        client.tasks.run.return_value = iter([])

        with pytest.raises(RunFailedError) as exc:
            TaskCLI(client).execute_interactive("42")

        assert exc.value.details["errors"] == ["credential expired"]
        assert "credential expired" in capsys.readouterr().out


class TestUpdate:
    def test_update_calls_v2_update(self, capsys):
        client = _client()
        client.tasks.update.return_value = _task(id=42, name="new name")

        TaskCLI(client).update_interactive("42", name="new name", goals="ship it")

        client.tasks.update.assert_called_once_with(
            42, name="new name", instructions=None, expected_output=None, goals="ship it"
        )
        out = capsys.readouterr().out
        assert "✅ Task updated successfully!" in out
        assert "Name: new name" in out
        assert "Goals: Updated" in out


class TestArchive:
    def test_archive_calls_v2_delete(self, capsys):
        client = _client()

        TaskCLI(client).archive_interactive("42")

        client.tasks.delete.assert_called_once_with(42)
        assert "✅ Task archived successfully!" in capsys.readouterr().out


class TestStatusToggle:
    """enable/disable ride the v2 PATCH status field (added alongside this port)."""

    @pytest.mark.parametrize(
        ("action", "status", "banner"),
        [("enable", "enabled", "✅ Task enabled!"), ("disable", "disabled", "⏸️  Task disabled!")],
    )
    def test_enable_disable_patch_status(self, action, status, banner, capsys):
        client = _client()
        client.tasks.update.return_value = _task(id=42, status=status)

        getattr(TaskCLI(client), f"{action}_interactive")("42")

        client.tasks.update.assert_called_once_with(42, status=status)
        out = capsys.readouterr().out
        assert banner in out
        assert f"Status: {status}" in out


def _imported_modules(path: Path, package: str) -> set[str]:
    """Absolute module names imported by a file, resolving relative imports."""
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    parts = package.split(".")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = ".".join(parts[: len(parts) - node.level + 1]) if node.level else ""
            prefix = f"{base}.{node.module}" if node.module else base
            names.add(prefix)
            names.update(f"{prefix}.{alias.name}" for alias in node.names)
    return names


@pytest.mark.parametrize(
    ("relative_path", "package"),
    [("cli/tasks.py", "m8tes.cli"), ("cli/commands/task.py", "m8tes.cli.commands")],
)
def test_task_cli_never_imports_the_legacy_v1_client(relative_path, package):
    """The port is only done while these stay absent — the legacy modules get deleted."""
    import m8tes

    path = Path(m8tes.__file__).parent / relative_path
    imported = _imported_modules(path, package)

    banned = {"m8tes.client", "m8tes.task", "m8tes.services", "m8tes.http"}
    assert not {name for name in imported for b in banned if name == b or name.startswith(f"{b}.")}
