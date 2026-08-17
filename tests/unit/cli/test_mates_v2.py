"""MateCLI + mate commands on the v2 SDK client.

Pins the CLI→v2 port: agents CRUD via client.agents, task/chat streaming via
client.runs.create/reply, client-side auto-detect (the v1 auto-detect endpoint
has no v2 twin), and the exit-code contract for v2 typed exceptions. Also
guards that neither ported module imports the legacy V1 SDK modules slated for
deletion.
"""

from argparse import Namespace
import ast
from pathlib import Path
from typing import ClassVar
from unittest.mock import Mock, patch

import pytest

from m8tes._exceptions import (
    APIError,
    AuthenticationError,
    NotFoundError,
    RunFailedError,
    ValidationError,
)
from m8tes._types import RunMessage, RunOutcome, SyncPage, Teammate
from m8tes.cli.commands.mate import (
    ArchiveCommand,
    EnableCommand,
    GetCommand,
    ListCommand,
    TaskCommand,
)
from m8tes.cli.mates import MateCLI


def _teammate(**overrides) -> Teammate:
    payload = {
        "id": 1,
        "name": "Mate",
        "status": "enabled",
        "tools": [],
        "created_at": "2026-07-01T00:00:00Z",
    }
    payload.update(overrides)
    return Teammate.from_dict(payload)


def _page(agents: list[Teammate]) -> SyncPage:
    return SyncPage(data=agents, has_more=False)


class FakeStream:
    """Stands in for RunStream: iterable events + run_id from metadata."""

    def __init__(self, events=(), run_id=77):
        self._events = list(events)
        self.run_id = run_id

    def __iter__(self):
        return iter(self._events)


def _display_mock(*, has_errors=False, text="ok", tool_calls=None):
    display = Mock()
    display.get_final_text.return_value = text
    display.accumulator.has_errors.return_value = has_errors
    display.accumulator.get_errors.return_value = ["boom"] if has_errors else []
    display.accumulator.get_tool_calls.return_value = tool_calls or {}
    return display


@pytest.fixture
def client():
    c = Mock()
    c.api_key = "m8_test"
    return c


class TestSelectOrConfirmMate:
    def test_explicit_id_skips_api(self, client):
        assert MateCLI(client).select_or_confirm_mate(9) == 9
        client.agents.list.assert_not_called()

    @patch("m8tes.cli.mates.confirm_prompt", return_value=True)
    def test_auto_detects_most_recently_created_enabled(self, _confirm, client, capsys):
        client.agents.list.return_value = _page(
            [
                _teammate(id=1, created_at="2026-07-01T00:00:00Z"),
                _teammate(id=2, name="Newest", created_at="2026-07-03T00:00:00Z"),
                _teammate(id=3, status="disabled", created_at="2026-07-05T00:00:00Z"),
            ]
        )
        assert MateCLI(client).select_or_confirm_mate(None) == 2
        out = capsys.readouterr().out
        assert "Newest" in out
        assert "Most recently created" in out

    @patch("m8tes.cli.mates.confirm_prompt", return_value=True)
    def test_auto_detect_pages_past_the_first_page(self, _confirm, client):
        """The only enabled agent past page one must still be found — .data alone
        capped detection at 100 agents."""
        second = SyncPage(
            data=[_teammate(id=200, name="Deep", created_at="2026-07-09T00:00:00Z")],
            has_more=False,
        )
        first = SyncPage(
            data=[_teammate(id=1, status="disabled", created_at="2026-07-01T00:00:00Z")],
            has_more=True,
            _fetch_next=lambda **kw: second,
        )
        client.agents.list.return_value = first
        assert MateCLI(client).select_or_confirm_mate(None) == 200

    @patch("m8tes.cli.mates.prompt", return_value="1")
    @patch("m8tes.cli.mates.confirm_prompt", return_value=False)
    def test_decline_falls_back_to_manual_index_selection(self, _c, _p, client, capsys):
        client.agents.list.return_value = _page(
            [_teammate(id=5, name="A"), _teammate(id=6, name="B")]
        )
        assert MateCLI(client).select_or_confirm_mate(None) == 5
        assert "📋 Available agents:" in capsys.readouterr().out

    @patch("m8tes.cli.mates.prompt", return_value="42")
    def test_no_enabled_agents_warns_then_selects_by_direct_id(self, _p, client, capsys):
        client.agents.list.return_value = _page(
            [_teammate(id=41, status="disabled"), _teammate(id=42, status="disabled")]
        )
        assert MateCLI(client).select_or_confirm_mate(None) == 42
        assert "No enabled agents found for auto-detection" in capsys.readouterr().out

    @patch("m8tes.cli.mates.prompt", return_value="abc")
    @patch("m8tes.cli.mates.confirm_prompt", return_value=False)
    def test_non_numeric_selection_cancels(self, _c, _p, client, capsys):
        client.agents.list.return_value = _page([_teammate(id=5)])
        assert MateCLI(client).select_or_confirm_mate(None) is None
        assert "❌ Invalid selection: abc" in capsys.readouterr().out

    @patch("m8tes.cli.mates.prompt", return_value="99")
    @patch("m8tes.cli.mates.confirm_prompt", return_value=False)
    def test_unknown_numeric_id_cancels(self, _c, _p, client, capsys):
        client.agents.list.return_value = _page([_teammate(id=5)])
        assert MateCLI(client).select_or_confirm_mate(None) is None
        assert "❌ Agent ID 99 not found" in capsys.readouterr().out

    @patch("m8tes.cli.mates.prompt", return_value="")
    @patch("m8tes.cli.mates.confirm_prompt", return_value=False)
    def test_empty_selection_cancels(self, _c, _p, client, capsys):
        client.agents.list.return_value = _page([_teammate(id=5)])
        assert MateCLI(client).select_or_confirm_mate(None) is None
        assert "❌ Cancelled" in capsys.readouterr().out

    def test_empty_account_hints_create(self, client, capsys):
        client.agents.list.return_value = _page([])
        assert MateCLI(client).select_or_confirm_mate(None) is None
        assert "Create an agent first" in capsys.readouterr().out

    def test_auth_error_with_api_key_hints_key(self, client, capsys):
        client.agents.list.side_effect = AuthenticationError("nope")
        assert MateCLI(client).select_or_confirm_mate(None) is None
        assert "Check that your API key is valid" in capsys.readouterr().out

    def test_auth_error_without_api_key_hints_login(self, client, capsys):
        client.api_key = None
        client.agents.list.side_effect = AuthenticationError("nope")
        assert MateCLI(client).select_or_confirm_mate(None) is None
        assert "Please login first: m8tes auth login" in capsys.readouterr().out

    def test_other_sdk_error_cancels(self, client, capsys):
        client.agents.list.side_effect = APIError("boom")
        assert MateCLI(client).select_or_confirm_mate(None) is None
        assert "❌ Failed to list agents: boom" in capsys.readouterr().out


class TestListInteractive:
    def test_default_shows_enabled_only(self, client, capsys):
        client.agents.list.return_value = _page(
            [_teammate(id=1, name="On"), _teammate(id=2, name="Off", status="disabled")]
        )
        MateCLI(client).list_interactive()
        out = capsys.readouterr().out
        assert "On" in out
        assert "Off" not in out
        client.agents.list.assert_called_once_with(limit=100, include_archived=False)

    def test_include_disabled_widens_to_archived_and_shows_disabled(self, client, capsys):
        client.agents.list.return_value = _page(
            [_teammate(id=1, name="On"), _teammate(id=2, name="Off", status="disabled")]
        )
        MateCLI(client).list_interactive(include_disabled=True)
        out = capsys.readouterr().out
        assert "Off" in out
        assert "⏸️" in out
        client.agents.list.assert_called_once_with(limit=100, include_archived=True)

    def test_empty_listing_hints(self, client, capsys):
        client.agents.list.return_value = _page([])
        MateCLI(client).list_interactive()
        out = capsys.readouterr().out
        assert "No agents found." in out
        assert "--include-disabled" in out


class TestCreate:
    def test_non_interactive_calls_agents_create(self, client, capsys):
        client.agents.create.return_value = _teammate(id=8, name="New")
        MateCLI(client).create_non_interactive(
            name="New",
            tools=["run_gaql_query"],
            instructions="Do things",
            role="Optimizer",
            goals="ROAS up",
        )
        client.agents.create.assert_called_once_with(
            name="New",
            tools=["run_gaql_query"],
            instructions="Do things",
            role="Optimizer",
            goals="ROAS up",
            inbound_imessage_enabled=False,
            imessage_chat_guid=None,
        )
        assert "✅ Agent created successfully!" in capsys.readouterr().out

    def test_imessage_without_guid_raises(self, client):
        with pytest.raises(ValidationError):
            MateCLI(client).create_non_interactive(
                name="x", tools=[], instructions="y", inbound_imessage_enabled=True
            )
        client.agents.create.assert_not_called()


class TestTaskInteractive:
    def _run(
        self,
        client,
        *,
        display,
        stream,
        task_setup_tools=True,
        output_format="verbose",
        outcome=None,
        messages=(),
    ):
        client.agents.get.return_value = _teammate(id=3, name="Mate")
        client.runs.create.return_value = stream
        client.runs.outcome.return_value = outcome or RunOutcome.from_dict({"run_id": 77})
        client.runs.messages.return_value = list(messages)
        with patch("m8tes.cli.display.create_display", return_value=display):
            MateCLI(client).task_interactive(
                "do it", "3", output_format=output_format, task_setup_tools=task_setup_tools
            )

    def test_streams_via_runs_create_and_forwards_events(self, client):
        events = [Mock(type="text-delta"), Mock(type="finish")]
        display = _display_mock()
        self._run(client, display=display, stream=FakeStream(events))
        client.runs.create.assert_called_once_with(
            agent_id=3, message="do it", stream=True, task_setup_tools=None
        )
        assert [c.args[0] for c in display.on_event.call_args_list] == events

    def test_no_task_setup_tools_flag_forces_false(self, client):
        self._run(client, display=_display_mock(), stream=FakeStream(), task_setup_tools=False)
        assert client.runs.create.call_args.kwargs["task_setup_tools"] is False

    def test_summary_fetched_for_stream_run_id(self, client, capsys):
        message = RunMessage.from_dict(
            {
                "id": 1,
                "run_id": 77,
                "sequence": 1,
                "role": "assistant",
                "content": "All done",
                "content_blocks": [{"type": "tool_use", "name": "run_gaql_query"}],
            }
        )
        self._run(
            client,
            display=_display_mock(),
            stream=FakeStream(run_id=77),
            outcome=RunOutcome.from_dict(
                {"run_id": 77, "total_tokens": 1234, "cost_usd": "0.5000"}
            ),
            messages=[message],
        )
        client.runs.outcome.assert_called_once_with(77)
        client.runs.messages.assert_called_once_with(77)
        out = capsys.readouterr().out
        assert "All done" in out
        assert "run_gaql_query" in out
        assert "Tokens: 1,234" in out
        assert "✅ Task completed" in out

    def test_error_events_raise_run_failed(self, client, capsys):
        with pytest.raises(RunFailedError):
            self._run(client, display=_display_mock(has_errors=True), stream=FakeStream())
        assert "❌ Task failed" in capsys.readouterr().out


class TestChatInteractive:
    def _chat(self, client, inputs, streams, resume_run_id=None):
        client.agents.get.return_value = _teammate(id=3, name="Mate")
        it = iter(inputs)
        with (
            patch("m8tes.cli.display.create_display", return_value=_display_mock()),
            patch("builtins.input", lambda *_: next(it)),
        ):
            client.runs.create.side_effect = streams
            client.runs.reply.side_effect = streams
            MateCLI(client).chat_interactive("3", resume_run_id=resume_run_id)

    def test_first_message_creates_run_followups_reply(self, client, capsys):
        self._chat(client, ["hello", "again", "/exit"], [FakeStream(run_id=77), FakeStream()])
        client.runs.create.assert_called_once_with(agent_id=3, message="hello", stream=True)
        client.runs.reply.assert_called_once_with(77, message="again", stream=True)
        assert "📝 Session Run ID: 77" in capsys.readouterr().out

    def test_resume_run_id_replies_from_the_start(self, client, capsys):
        client.runs.get.return_value = Mock(teammate_id=3)
        self._chat(client, ["hi", "/exit"], [FakeStream()], resume_run_id=55)
        client.runs.create.assert_not_called()
        client.runs.reply.assert_called_once_with(55, message="hi", stream=True)
        assert "🔄 Resumed session from run 55" in capsys.readouterr().out

    def test_resume_rejects_another_mates_run(self, client, capsys):
        """The v2 server replies on the RUN's agent — a mismatched resume target
        would silently continue a different mate's conversation, so it's refused
        and the next message starts a fresh run on the selected mate."""
        client.runs.get.return_value = Mock(teammate_id=9)
        self._chat(client, ["hi", "/exit"], [FakeStream(run_id=80)], resume_run_id=55)
        client.runs.reply.assert_not_called()
        client.runs.create.assert_called_once_with(agent_id=3, message="hi", stream=True)
        assert "belongs to agent 9" in capsys.readouterr().out

    def test_interrupted_first_message_keeps_its_run(self, client, capsys):
        """Ctrl-C mid-stream: the run keeps executing server-side, so the captured
        run_id must make the NEXT message a reply, not a second concurrent run."""

        class InterruptingStream(FakeStream):
            def __iter__(self):
                raise KeyboardInterrupt

        self._chat(client, ["hi", "again", "/exit"], [InterruptingStream(run_id=77), FakeStream()])
        client.runs.create.assert_called_once_with(agent_id=3, message="hi", stream=True)
        client.runs.reply.assert_called_once_with(77, message="again", stream=True)
        assert "interrupted" in capsys.readouterr().out

    def test_interrupt_before_metadata_warns_and_starts_fresh(self, client, capsys):
        """An interrupt before the metadata event leaves the run id unknowable —
        the CLI must say so (and how to find the orphan) instead of pretending."""

        class PreMetadataInterrupt(FakeStream):
            def __init__(self):
                super().__init__(run_id=None)

            def __iter__(self):
                raise KeyboardInterrupt

        self._chat(
            client, ["hi", "again", "/exit"], [PreMetadataInterrupt(), FakeStream(run_id=90)]
        )
        assert client.runs.create.call_count == 2
        client.runs.reply.assert_not_called()
        assert "m8tes run list" in capsys.readouterr().out

    def test_clear_starts_a_fresh_run(self, client, capsys):
        self._chat(
            client,
            ["hi", "/clear", "again", "/exit"],
            [FakeStream(run_id=77), FakeStream(run_id=78)],
        )
        assert client.runs.create.call_count == 2
        client.runs.reply.assert_not_called()
        assert "✅ Conversation history cleared" in capsys.readouterr().out

    def test_resume_command_switches_run(self, client, capsys):
        client.runs.get.return_value = Mock(teammate_id=3)
        self._chat(client, ["/resume 91", "hi", "/exit"], [FakeStream()])
        client.runs.create.assert_not_called()
        client.runs.reply.assert_called_once_with(91, message="hi", stream=True)
        assert "🔄 Resumed session from run 91" in capsys.readouterr().out


class TestUpdate:
    def test_non_interactive_patches_via_agents_update(self, client, capsys):
        client.agents.get.return_value = _teammate(id=4)
        MateCLI(client).update_non_interactive(
            "4", name="Renamed", instructions="New", imessage_chat_guid="guid-1"
        )
        client.agents.update.assert_called_once_with(
            4,
            name="Renamed",
            instructions="New",
            inbound_imessage_enabled=None,
            imessage_chat_guid="guid-1",
        )
        assert "✅ Agent updated successfully!" in capsys.readouterr().out


class TestEnableDisable:
    def test_enable_calls_agents_enable_and_prints_new_status(self, client, capsys):
        client.agents.get.return_value = _teammate(id=4, status="disabled")
        client.agents.enable.return_value = _teammate(id=4, status="enabled")
        MateCLI(client).enable_interactive("4")
        client.agents.enable.assert_called_once_with(4)
        assert "Status: enabled" in capsys.readouterr().out

    def test_enable_already_enabled_short_circuits(self, client, capsys):
        client.agents.get.return_value = _teammate(id=4, status="enabled")
        MateCLI(client).enable_interactive("4")
        client.agents.enable.assert_not_called()
        assert "already enabled" in capsys.readouterr().out

    def test_disable_force_calls_agents_disable(self, client, capsys):
        client.agents.get.return_value = _teammate(id=4, status="enabled")
        client.agents.disable.return_value = _teammate(id=4, status="disabled")
        MateCLI(client).disable_interactive("4", force=True)
        client.agents.disable.assert_called_once_with(4)
        assert "✅ Agent disabled successfully!" in capsys.readouterr().out

    @patch("m8tes.cli.mates.confirm_prompt", return_value=False)
    def test_disable_declined_does_nothing(self, _c, client, capsys):
        client.agents.get.return_value = _teammate(id=4, status="enabled")
        MateCLI(client).disable_interactive("4")
        client.agents.disable.assert_not_called()
        assert "❌ Operation cancelled" in capsys.readouterr().out


class TestArchive:
    def test_force_archives_via_agents_delete(self, client, capsys):
        client.agents.get.return_value = _teammate(id=4)
        MateCLI(client).archive_interactive("4", force=True)
        client.agents.delete.assert_called_once_with(4)
        assert "✅ Agent archived successfully!" in capsys.readouterr().out

    def test_not_found_prints_guidance_and_reraises(self, client, capsys):
        client.agents.get.side_effect = NotFoundError("gone", status_code=404)
        with pytest.raises(NotFoundError):
            MateCLI(client).archive_interactive("4", force=True)
        assert "❌ Agent not found: No agent with ID 4" in capsys.readouterr().out


class TestCommandExitCodes:
    """v2 typed exceptions map to exit 1 (the scripting/CI contract)."""

    def test_list_v2_auth_failure_exits_1(self, client, capsys):
        client.agents.list.side_effect = AuthenticationError("bad key")
        assert ListCommand().execute(Namespace(), client) == 1
        assert "❌ Authentication failed" in capsys.readouterr().out

    def test_get_v2_not_found_exits_1(self, client):
        client.agents.get.side_effect = NotFoundError("gone", status_code=404)
        assert GetCommand().execute(Namespace(agent_id="1"), client) == 1

    def test_get_non_numeric_id_exits_1(self, client):
        # parse_id raises the LEGACY ValidationError — still mapped to exit 1.
        assert GetCommand().execute(Namespace(agent_id="abc"), client) == 1

    def test_enable_network_failure_exits_1(self, client):
        client.agents.get.side_effect = APIError("connection refused")
        assert EnableCommand().execute(Namespace(agent_id="1"), client) == 1

    def test_archive_not_found_exits_1(self, client):
        client.agents.get.side_effect = NotFoundError("gone", status_code=404)
        assert ArchiveCommand().execute(Namespace(agent_id="1", force=True), client) == 1

    def test_task_failed_run_exits_1(self, client, capsys):
        client.agents.get.return_value = _teammate(id=3)
        client.runs.create.return_value = FakeStream()
        client.runs.outcome.return_value = RunOutcome.from_dict({"run_id": 77})
        client.runs.messages.return_value = []
        args = Namespace(command_args=["3", "do", "it"], output="verbose")
        with patch("m8tes.cli.display.create_display", return_value=_display_mock(has_errors=True)):
            assert TaskCommand().execute(args, client) == 1
        assert "❌ Agent task failed: Run finished with errors" in capsys.readouterr().out

    def test_no_client_exits_1(self):
        assert ListCommand().execute(Namespace(), None) == 1


class TestNoLegacySdkImports:
    """The ported modules must not touch the V1 SDK modules slated for deletion."""

    FORBIDDEN: ClassVar[set[str]] = {"client", "instance", "agent", "chat", "services", "http"}

    @pytest.mark.parametrize("relpath", ["m8tes/cli/mates.py", "m8tes/cli/commands/mate.py"])
    def test_no_forbidden_imports(self, relpath):
        source = (Path(__file__).parents[3] / relpath).read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                # Relative imports from these files resolve inside the m8tes
                # package; the first module segment names the legacy module.
                top = (node.module or "").split(".")[0]
                if node.level == 0 and top == "m8tes":
                    top = (node.module or "").split(".")[1] if "." in (node.module or "") else ""
                assert top not in self.FORBIDDEN, f"{relpath} imports legacy m8tes.{top}"
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    parts = alias.name.split(".")
                    assert not (
                        parts[0] == "m8tes" and len(parts) > 1 and parts[1] in self.FORBIDDEN
                    ), f"{relpath} imports legacy {alias.name}"
