"""Regression tests for shipped README copy and example scripts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import runpy
import sys
from types import ModuleType, SimpleNamespace

import pytest

README_PATH = Path(__file__).resolve().parents[2] / "README.md"
EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"


@dataclass
class CallRecorder:
    calls: list[tuple[str, dict]] = field(default_factory=list)

    def record(self, call_name: str, **kwargs) -> None:
        self.calls.append((call_name, kwargs))

    def find(self, name: str) -> list[dict]:
        return [payload for call_name, payload in self.calls if call_name == name]


class DummyWriteFile:
    def __enter__(self) -> "DummyWriteFile":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def write(self, data) -> int:
        return len(data)


class FakeRunStream:
    def __init__(self, recorder: CallRecorder):
        self._recorder = recorder
        self.run_id = 901
        self.text = "working...done"
        self._events = [
            SimpleNamespace(type="text-delta", delta="working...", tool_name=None, tool_input=None),
            SimpleNamespace(
                type="tool-call-start",
                delta=None,
                tool_name="Write",
                tool_input={"file_path": "/workspace/weekly_report.md"},
            ),
            SimpleNamespace(type="done", delta=None, tool_name=None, tool_input=None),
        ]

    def __enter__(self) -> "FakeRunStream":
        self._recorder.record("runs.stream.enter")
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self._recorder.record("runs.stream.exit")
        return False

    def __iter__(self):
        return iter(self._events)

    def iter_text(self):
        return iter(["working...", "done"])


class FakeTeammates:
    def __init__(self, recorder: CallRecorder):
        self._recorder = recorder

    def create(self, **kwargs):
        self._recorder.record("teammates.create", **kwargs)
        return SimpleNamespace(
            id=101,
            email_address="ops-assistant@m8tes.ai" if kwargs.get("email_inbox") else None,
        )


class FakeTaskTriggers:
    def __init__(self, recorder: CallRecorder):
        self._recorder = recorder

    def create(self, task_id: int, **kwargs):
        self._recorder.record("tasks.triggers.create", task_id=task_id, **kwargs)
        return SimpleNamespace(id=301, **kwargs)


class FakeTasks:
    def __init__(self, recorder: CallRecorder):
        self._recorder = recorder
        self.triggers = FakeTaskTriggers(recorder)

    def create(self, **kwargs):
        self._recorder.record("tasks.create", **kwargs)
        return SimpleNamespace(id=201, webhook_url="https://m8tes.ai/hook/task_201")

    def run_and_wait(self, task_id: int, **kwargs):
        self._recorder.record("tasks.run_and_wait", task_id=task_id, **kwargs)
        return SimpleNamespace(id=202, output="scheduled run complete")


class FakeRuns:
    def __init__(self, recorder: CallRecorder):
        self._recorder = recorder

    def create(self, **kwargs):
        self._recorder.record("runs.create", **kwargs)
        if kwargs.get("stream", True) is False:
            return SimpleNamespace(id=401, output=None, status="running")
        return FakeRunStream(self._recorder)

    def create_and_wait(self, **kwargs):
        self._recorder.record("runs.create_and_wait", **kwargs)
        return SimpleNamespace(id=402, output="completed output", status="completed")

    def wait(self, run_id: int, **kwargs):
        self._recorder.record("runs.wait", run_id=run_id, **kwargs)
        return SimpleNamespace(id=run_id, output="completed output", status="completed")

    def list_files(self, run_id: int):
        self._recorder.record("runs.list_files", run_id=run_id)
        return [
            SimpleNamespace(name="weekly_report.md", size=123),
            SimpleNamespace(name="weekly_data.csv", size=456),
        ]

    def download_file(self, run_id: int, filename: str) -> bytes:
        self._recorder.record("runs.download_file", run_id=run_id, filename=filename)
        return b"file-bytes"

    def list(self, **kwargs):
        self._recorder.record("runs.list", **kwargs)
        return SimpleNamespace(data=[SimpleNamespace(id=1), SimpleNamespace(id=2)])


class FakeApps:
    def __init__(self, recorder: CallRecorder):
        self._recorder = recorder

    def connect_oauth(self, app_name: str, redirect_uri: str, *, user_id: str | None = None):
        self._recorder.record(
            "apps.connect_oauth", app_name=app_name, redirect_uri=redirect_uri, user_id=user_id
        )
        return SimpleNamespace(
            authorization_url="https://accounts.example.test/oauth",
            connection_id="conn_123",
        )

    def connect_complete(self, app_name: str, connection_id: str, *, user_id: str | None = None):
        self._recorder.record(
            "apps.connect_complete",
            app_name=app_name,
            connection_id=connection_id,
            user_id=user_id,
        )
        return SimpleNamespace(status="connected")

    def connect_api_key(self, app_name: str, *, api_key: str, user_id: str | None = None):
        self._recorder.record(
            "apps.connect_api_key", app_name=app_name, api_key=api_key, user_id=user_id
        )
        return SimpleNamespace(status="connected")

    def is_connected(self, app_name: str, *, user_id: str | None = None) -> bool:
        self._recorder.record("apps.is_connected", app_name=app_name, user_id=user_id)
        return True

    def list(self, *, user_id: str | None = None):
        self._recorder.record("apps.list", user_id=user_id)
        return SimpleNamespace(
            data=[
                SimpleNamespace(name="gmail", connected=True, auth_type="composio"),
                SimpleNamespace(name="openai", connected=True, auth_type="api_key"),
            ],
            has_more=False,
        )


class FakeUsers:
    def __init__(self, recorder: CallRecorder):
        self._recorder = recorder

    def create(self, **kwargs):
        self._recorder.record("users.create", **kwargs)
        return SimpleNamespace(**kwargs)


class FakeMemories:
    def __init__(self, recorder: CallRecorder):
        self._recorder = recorder

    def create(self, **kwargs):
        self._recorder.record("memories.create", **kwargs)
        return SimpleNamespace(id=501, **kwargs)


class FakeClient:
    def __init__(self, recorder: CallRecorder, **kwargs):
        recorder.record("client.init", **kwargs)
        self.teammates = FakeTeammates(recorder)
        self.tasks = FakeTasks(recorder)
        self.runs = FakeRuns(recorder)
        self.apps = FakeApps(recorder)
        self.users = FakeUsers(recorder)
        self.memories = FakeMemories(recorder)


class PermissionRequest:
    def __init__(
        self,
        *,
        is_plan_approval: bool = False,
        plan_text: str = "",
        tool_input: dict | None = None,
        tool_name: str = "",
    ):
        self.is_plan_approval = is_plan_approval
        self.plan_text = plan_text
        self.tool_input = tool_input or {}
        self.tool_name = tool_name


def install_fake_m8tes(monkeypatch: pytest.MonkeyPatch, recorder: CallRecorder) -> None:
    module = ModuleType("m8tes")
    module.M8tes = lambda **kwargs: FakeClient(recorder, **kwargs)
    module.PermissionRequest = PermissionRequest
    monkeypatch.setitem(sys.modules, "m8tes", module)


def run_example(monkeypatch: pytest.MonkeyPatch, filename: str) -> CallRecorder:
    recorder = CallRecorder()
    install_fake_m8tes(monkeypatch, recorder)
    monkeypatch.setattr("builtins.open", lambda *args, **kwargs: DummyWriteFile())
    monkeypatch.setattr("builtins.input", lambda *args, **kwargs: "y")
    runpy.run_path(str(EXAMPLES_DIR / filename), run_name="__main__")
    return recorder


def test_readme_documents_opt_in_inbox_and_auth_usage_notes():
    readme = README_PATH.read_text()

    assert "Enable an @m8tes.ai inbox per teammate" in readme
    assert "client.auth.get_usage()" in readme
    assert "POST /api/v2/token" in readme
    assert "invalidates the previous one" in readme


def test_demo_example_uses_current_quickstart_flow(monkeypatch: pytest.MonkeyPatch):
    recorder = run_example(monkeypatch, "demo.py")

    assert recorder.find("teammates.create")[0]["email_inbox"] is True
    assert recorder.find("tasks.create")[0]["schedule_timezone"] == "America/New_York"
    assert recorder.find("runs.create")[0]["permission_mode"] == "autonomous"


def test_embed_oauth_example_uses_supported_methods(monkeypatch: pytest.MonkeyPatch):
    recorder = run_example(monkeypatch, "embed-oauth.py")

    oauth_call = recorder.find("apps.connect_oauth")[0]
    assert oauth_call == {
        "app_name": "gmail",
        "redirect_uri": "https://yourapp.com/oauth/callback",
        "user_id": "user_alice",
    }
    assert recorder.find("users.create")[0]["user_id"] == "user_alice"
    assert recorder.find("runs.create_and_wait")[0]["user_id"] == "user_alice"


def test_file_report_example_uses_files_and_triggers(monkeypatch: pytest.MonkeyPatch):
    recorder = run_example(monkeypatch, "file-report.py")

    assert recorder.find("runs.list_files")
    assert recorder.find("runs.download_file")
    trigger_call = recorder.find("tasks.triggers.create")[0]
    assert trigger_call["type"] == "schedule"
    assert trigger_call["timezone"] == "America/New_York"
    assert recorder.find("tasks.run_and_wait")[0]["task_id"] == 201


def test_plan_mode_example_uses_plan_callbacks(monkeypatch: pytest.MonkeyPatch):
    recorder = run_example(monkeypatch, "plan-mode.py")

    create_call = recorder.find("runs.create")[0]
    assert create_call["human_in_the_loop"] is True
    assert create_call["permission_mode"] == "plan"
    assert create_call["stream"] is False

    wait_call = recorder.find("runs.wait")[0]
    assert callable(wait_call["on_question"])
    assert callable(wait_call["on_approval"])

    automated_call = recorder.find("runs.create_and_wait")[0]
    assert automated_call["permission_mode"] == "plan"
    assert callable(automated_call["on_question"])
    assert callable(automated_call["on_approval"])


def test_customer_agent_example_keeps_user_scoping(monkeypatch: pytest.MonkeyPatch):
    recorder = run_example(monkeypatch, "customer-agent.py")

    user_ids = [call["user_id"] for call in recorder.find("users.create")]
    assert user_ids == ["acme-corp", "globex-inc"]

    memory_user_ids = [call["user_id"] for call in recorder.find("memories.create")]
    assert memory_user_ids == ["acme-corp", "acme-corp", "globex-inc", "globex-inc"]

    run_user_ids = [call["user_id"] for call in recorder.find("runs.create_and_wait")]
    assert run_user_ids == ["acme-corp", "globex-inc"]
    assert recorder.find("runs.list")[0]["user_id"] == "acme-corp"
