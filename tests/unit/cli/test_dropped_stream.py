"""A dropped stream must never end a CLI command as if the run were done.

The API detaches a run from the connection that started it. Before this, a stream
that stopped early made ``m8tes mate task`` print a run summary of half the work
and exit 0, and a broken connection exited with "Command execution failed" while
the run carried on. Every command that streams a run now waits for the run, and
reports how it stands: finished, failed, cancelled, closed, or paused on a person.

The SDK half (what raises ``StreamInterruptedError``) is pinned in
``tests/unit/test_v2_stream_drop.py``; these pin what the CLI does with it.
"""

from argparse import Namespace
import io
from unittest.mock import Mock, patch

import pytest
import responses
from rich.console import Console

from m8tes._exceptions import RunFailedError, StreamInterruptedError
from m8tes._http import HTTPClient
from m8tes._resources.runs import Runs
from m8tes._types import Run, RunOutcome, Task, Teammate
from m8tes.cli.commands.mate import TaskCommand
from m8tes.cli.display import VerboseDisplay
from m8tes.cli.mates import MateCLI
from m8tes.cli.tasks import TaskCLI
from m8tes.cli.util import (
    DROPPED_RUN_FAILURE_STATUSES,
    DROPPED_RUN_WAIT_SECONDS,
    RunPausedError,
    _cli_on_approval,
    _cli_on_question,
    _stop_at_approval,
    _stop_at_question,
    can_ask,
    dropped_run_problem,
    wait_for_dropped_run,
)
from m8tes.streaming import StreamEvent

BASE = "https://api.m8tes.ai/v2"


def _run(status="completed", **overrides) -> Run:
    return Run.from_dict({"id": 7, "status": status, "teammate_id": 3, **overrides})


def _teammate() -> Teammate:
    return Teammate.from_dict(
        {
            "id": 3,
            "name": "Mate",
            "status": "enabled",
            "tools": [],
            "created_at": "2026-07-01T00:00:00Z",
        }
    )


class DroppedStream:
    """Stands in for RunStream: yields its events, then the connection drops."""

    def __init__(self, events=(), run_id=7, await_queued_message_id=None):
        self._events = list(events)
        self.run_id = run_id
        self.await_queued_message_id = await_queued_message_id

    def __iter__(self):
        yield from self._events
        raise StreamInterruptedError(self.run_id, "the connection was lost (reset)")


class FinishedStream:
    """Stands in for a RunStream that ran to its end."""

    run_id = 7

    def __iter__(self):
        return iter(())


def _display(text=""):
    display = Mock()
    display.get_final_text.return_value = text
    display.accumulator.has_errors.return_value = False
    display.accumulator.get_errors.return_value = []
    display.accumulator.get_tool_calls.return_value = {}
    return display


def _waited(client) -> dict:
    """What the CLI's one wait was asked for, once it is known to be for run 7."""
    client.runs.wait.assert_called_once()
    args, kwargs = client.runs.wait.call_args
    assert args == (7,)
    assert kwargs["timeout"] == DROPPED_RUN_WAIT_SECONDS
    return kwargs


def _paused_api(tool_name: str = "Bash") -> Runs:
    """The real ``Runs`` over a mocked API whose run 7 is parked on a gate."""
    run = {"id": 7, "status": "awaiting_approval", "teammate_id": 3}
    responses.add(responses.GET, f"{BASE}/runs/7", json=run, status=200)
    responses.add(
        responses.GET,
        f"{BASE}/runs/7/permissions",
        json=[{"request_id": "r1", "tool_name": tool_name, "status": "pending"}],
        status=200,
    )
    return Runs(HTTPClient(api_key="m8_test123", base_url=BASE, timeout=5))


@pytest.fixture
def client():
    c = Mock()
    c.agents.get.return_value = _teammate()
    c.runs.outcome.return_value = RunOutcome.from_dict({"run_id": 7})
    c.runs.messages.return_value = []
    return c


class TestWaitForDroppedRun:
    def test_it_waits_for_the_run_the_error_names(self, client):
        client.runs.wait.return_value = _run()
        out = io.StringIO()

        run = wait_for_dropped_run(client, StreamInterruptedError(7, "reset"), out=out)

        assert run.status == "completed"
        assert _waited(client)["user_id"] is None
        assert "Run 7 is still going" in out.getvalue()
        assert "Ctrl+C stops waiting, not the run" in out.getvalue()

    def test_it_waits_inside_the_end_user_scope(self, client):
        client.runs.wait.return_value = _run()

        wait_for_dropped_run(
            client, StreamInterruptedError(7, "reset"), out=io.StringIO(), user_id="customer_42"
        )

        assert _waited(client)["user_id"] == "customer_42"

    def test_with_no_run_to_go_back_to_the_interruption_propagates(self, client):
        exc = StreamInterruptedError(None, "reset")

        with pytest.raises(StreamInterruptedError) as raised:
            wait_for_dropped_run(client, exc, out=io.StringIO())

        assert raised.value is exc
        client.runs.wait.assert_not_called()

    def test_the_wait_is_long_enough_for_an_ordinary_run(self):
        # The run that started this fix worked for thirteen minutes.
        assert DROPPED_RUN_WAIT_SECONDS >= 1800

    def test_it_forwards_the_queued_message_id(self, client):
        # Without it the wait returns the turn the reply was queued behind.
        client.runs.wait.return_value = _run()

        wait_for_dropped_run(
            client,
            StreamInterruptedError(7, "reset"),
            out=io.StringIO(),
            await_queued_message_id=99,
        )

        assert _waited(client)["await_queued_message_id"] == 99

    def test_a_reply_that_was_not_queued_awaits_no_message(self, client):
        client.runs.wait.return_value = _run()

        wait_for_dropped_run(client, StreamInterruptedError(7, "reset"), out=io.StringIO())

        assert _waited(client)["await_queued_message_id"] is None


class TestWhoAnswersAGate:
    """``runs.wait`` raises at an approval or a question unless it is given callbacks.
    With a person at the terminal the CLI asks them. With nobody there it must not
    answer for them: a prompt in json chat printed into the event stream and read the
    next chat message as the answer, and an empty line denied the tool."""

    def test_with_a_person_there_the_wait_prompts(self, client):
        client.runs.wait.return_value = _run()

        wait_for_dropped_run(
            client, StreamInterruptedError(7, "reset"), out=io.StringIO(), ask=True
        )

        waited = _waited(client)
        assert waited["on_approval"] is _cli_on_approval
        assert waited["on_question"] is _cli_on_question

    def test_with_nobody_there_the_wait_stops_at_the_gate(self, client):
        client.runs.wait.return_value = _run()

        wait_for_dropped_run(client, StreamInterruptedError(7, "reset"), out=io.StringIO())

        waited = _waited(client)
        assert waited["on_approval"] is _stop_at_approval
        assert waited["on_question"] is _stop_at_question

    @pytest.mark.parametrize(
        ("output_format", "tty", "expected"),
        [
            ("verbose", True, True),
            ("compact", True, True),
            ("json", True, False),  # stdout is the event stream, stdin the messages
            ("verbose", False, False),  # a pipe: the next line is not an answer
        ],
    )
    def test_a_gate_is_only_put_to_a_person_at_the_terminal(self, output_format, tty, expected):
        with patch("sys.stdin") as stdin:
            stdin.isatty.return_value = tty

            assert can_ask(output_format) is expected

    @responses.activate
    @pytest.mark.parametrize(
        ("tool_name", "needs"),
        [
            ("Bash", "your approval to use Bash"),
            ("AskUserQuestion", "your answer to a question"),
        ],
    )
    def test_the_wait_ends_at_the_gate_and_decides_nothing(self, tool_name, needs):
        # The real runs.wait: it is the one that raises, lists the gate, and would post.
        client = Mock()
        client.runs = _paused_api(tool_name)

        with pytest.raises(RunPausedError) as paused:
            wait_for_dropped_run(client, StreamInterruptedError(7, "reset"), out=io.StringIO())

        assert paused.value.run_id == 7
        assert f"Run 7 is paused and has not finished: it needs {needs}" in str(paused.value)
        # Two reads and nothing else. An approve or an answer would be the CLI deciding
        # for the person, and a third read would be the run after someone else did.
        assert [(c.request.method, c.request.path_url) for c in responses.calls] == [
            ("GET", "/v2/runs/7"),
            ("GET", "/v2/runs/7/permissions"),
        ]

    @responses.activate
    def test_a_paused_task_exits_non_zero_and_shows_no_summary(self, client, capsys):
        # Greptile P1 on 4690715: exit 0 and a Run Summary told a script the work was done.
        client.runs.wait.side_effect = _paused_api().wait
        client.runs.create.return_value = DroppedStream()
        args = Namespace(command_args=["3", "do it"], output="verbose", user_id=None, model=None)

        with patch("m8tes.cli.display.create_display", return_value=_display()):
            code = TaskCommand().execute(args, client)

        assert code == 1
        out = capsys.readouterr().out
        assert "Run 7 is paused and has not finished: it needs your approval to use Bash" in out
        client.runs.outcome.assert_not_called()

    @responses.activate
    def test_a_paused_task_execute_fails_the_command(self, client, monkeypatch):
        client.runs.wait.side_effect = _paused_api().wait
        monkeypatch.setattr("m8tes.cli.display.create_display", lambda fmt: _display())
        client.tasks.get.return_value = Task.from_dict(
            {
                "id": 42,
                "teammate_id": 3,
                "name": "weekly recap",
                "instructions": "Summarize the week",
                "status": "enabled",
                "created_at": "2026-08-01T10:00:00Z",
            }
        )
        client.tasks.run.return_value = DroppedStream()

        with pytest.raises(RunPausedError):
            TaskCLI(client).execute_interactive("42")

    @responses.activate
    def test_a_paused_chat_turn_never_shows_another_turns_answer(self, client, capsys):
        # Greptile P1 on 4690715: reading the run again after the pause returns whichever
        # turn finished last. For a queued reply that is the turn in front of it.
        client.runs.wait.side_effect = _paused_api().wait
        client.runs.get.return_value = _run("completed", output="the previous turn's answer")
        it = iter(["hello", "again", "/exit"])
        client.runs.create.side_effect = [FinishedStream()]
        client.runs.reply.side_effect = [DroppedStream(await_queued_message_id=55)]

        with (
            patch("m8tes.cli.display.create_display", return_value=_display()),
            patch("builtins.input", lambda *_: next(it)),
        ):
            MateCLI(client).chat_interactive("3")

        out = capsys.readouterr().out
        assert "Run 7 is paused and has not finished" in out
        assert "the previous turn's answer" not in out
        client.runs.get.assert_not_called()

    @responses.activate
    def test_json_chat_at_a_gate_keeps_its_stdout_and_its_next_message(self, client, capsys):
        # Greptile P1 on 752626a. The prompt wrote "Approval needed" and "(y/N)" to
        # stdout, then took "next message" as the answer to it.
        client.runs.wait.side_effect = _paused_api().wait
        client.runs.create.side_effect = [DroppedStream()]
        client.runs.reply.side_effect = [FinishedStream()]

        with (
            patch("m8tes.cli.display.create_display", return_value=_display()),
            patch("sys.stdin", io.StringIO("hello\nnext message\n\n")),
        ):
            MateCLI(client).chat_interactive("3", output_format="json")

        captured = capsys.readouterr()
        assert captured.out == ""
        assert "Run 7 is paused and has not finished: it needs your approval" in captured.err
        client.runs.reply.assert_called_once_with(7, message="next message", stream=True)
        assert {call.request.method for call in responses.calls} == {"GET"}

    def test_a_command_at_a_terminal_asks(self, client):
        client.runs.wait.return_value = _run()
        client.runs.create.return_value = DroppedStream()

        with (
            patch("m8tes.cli.display.create_display", return_value=_display()),
            patch("m8tes.cli.mates.can_ask", return_value=True) as asked,
        ):
            MateCLI(client).task_interactive("do it", "3", output_format="compact")

        asked.assert_called_once_with("compact")
        assert _waited(client)["on_approval"] is _cli_on_approval


class TestDroppedRunProblem:
    def test_cancelled_and_closed_are_unsuccessful(self):
        assert frozenset({"failed", "cancelled", "closed"}) == DROPPED_RUN_FAILURE_STATUSES

    def test_a_failed_run_reports_its_error(self):
        assert dropped_run_problem(_run("failed", error="credential expired")) == (
            "credential expired"
        )

    def test_a_failed_run_with_no_error_falls_back_to_its_output(self):
        assert dropped_run_problem(_run("failed", output="An error occurred.")) == (
            "An error occurred."
        )

    def test_a_failed_run_with_nothing_to_say_still_reports(self):
        assert dropped_run_problem(_run("failed")) == "the run failed"

    @pytest.mark.parametrize("status", ["cancelled", "closed"])
    def test_a_stopped_run_never_reports_its_partial_output_as_the_error(self, status):
        assert dropped_run_problem(_run(status, output="half an answer")) == (
            f"the run was {status}"
        )

    def test_a_stop_with_a_reason_reports_the_reason(self):
        assert dropped_run_problem(_run("cancelled", error="stopped by user")) == "stopped by user"

    def test_a_run_that_finished_has_no_problem(self):
        assert dropped_run_problem(_run("completed", output="done")) is None


class TestMateTask:
    def _task(self, client, stream, display=None, **kwargs):
        client.runs.create.return_value = stream
        with patch("m8tes.cli.display.create_display", return_value=display or _display()):
            MateCLI(client).task_interactive("do it", "3", **kwargs)

    def test_a_dropped_stream_waits_for_the_run_then_shows_its_summary(self, client, capsys):
        client.runs.wait.return_value = _run()
        display = _display()

        self._task(client, DroppedStream([Mock(type="text-delta")]), display=display)

        # Once: the rich display prints its response panel every time it is finished.
        display.finish.assert_called_once_with(show_response=False)

        assert _waited(client)["user_id"] is None
        client.runs.outcome.assert_called_once_with(7)
        out = capsys.readouterr().out
        assert "Connection lost. Run 7 is still going" in out
        # What streamed before the drop says nothing about the output.
        assert "Agent produced no output" not in out

    def test_a_dropped_run_that_failed_fails_the_command(self, client, capsys):
        client.runs.wait.return_value = _run("failed", error="credential expired")

        with pytest.raises(RunFailedError):
            self._task(client, DroppedStream())

        out = capsys.readouterr().out
        assert "credential expired" in out
        assert "❌ Task failed" in out

    def test_a_cancelled_dropped_run_fails_the_command(self, client, capsys):
        client.runs.wait.return_value = _run("cancelled", error="stopped by user")

        with pytest.raises(RunFailedError):
            self._task(client, DroppedStream())

        out = capsys.readouterr().out
        assert "stopped by user" in out
        assert "❌ Task failed" in out

    @pytest.mark.parametrize("status", ["cancelled", "closed"])
    def test_a_dropped_run_that_was_stopped_fails_the_command(self, client, capsys, status):
        # Exit 0 here told a script that work which never finished had been done.
        client.runs.wait.return_value = _run(status, output="half an answer")

        with pytest.raises(RunFailedError):
            self._task(client, DroppedStream())

        out = capsys.readouterr().out
        assert f"the run was {status}" in out
        assert "half an answer" not in out
        assert "❌ Task failed" in out

    def test_json_mode_keeps_stdout_for_events(self, client, capsys):
        client.runs.wait.return_value = _run()

        self._task(client, DroppedStream(), output_format="json")

        captured = capsys.readouterr()
        assert "Connection lost" not in captured.out
        assert "Connection lost" in captured.err

    def test_the_wait_stays_inside_the_end_user_scope(self, client):
        client.runs.wait.return_value = _run()

        self._task(client, DroppedStream(), user_id="customer_42")

        assert _waited(client)["user_id"] == "customer_42"

    def test_a_drop_before_the_run_is_named_exits_non_zero(self, client, capsys):
        client.runs.create.return_value = DroppedStream(run_id=None)
        args = Namespace(command_args=["3", "do it"], output="verbose", user_id=None, model=None)

        with patch("m8tes.cli.display.create_display", return_value=_display()):
            code = TaskCommand().execute(args, client)

        assert code == 1
        client.runs.wait.assert_not_called()
        client.runs.outcome.assert_not_called()
        assert "Agent task failed: The stream was interrupted" in capsys.readouterr().out


class TestMateChat:
    def _chat(self, client, inputs, streams, display=None):
        it = iter(inputs)
        client.runs.create.side_effect = streams
        client.runs.reply.side_effect = streams
        with (
            patch("m8tes.cli.display.create_display", return_value=display or _display()),
            patch("builtins.input", lambda *_: next(it)),
        ):
            MateCLI(client).chat_interactive("3")

    def test_a_dropped_reply_is_waited_for_and_printed(self, client, capsys):
        client.runs.wait.return_value = _run(output="Here is the answer.")
        display = _display()

        self._chat(client, ["hello", "/exit"], [DroppedStream()], display=display)

        assert _waited(client)["user_id"] is None
        assert "Here is the answer." in capsys.readouterr().out
        display.finish.assert_called_once_with(show_response=False)

    def test_a_failed_dropped_turn_is_reported(self, client, capsys):
        client.runs.wait.return_value = _run("failed", error="boom", output="")

        self._chat(client, ["hello", "/exit"], [DroppedStream()])

        out = capsys.readouterr().out
        assert "❌ Turn failed" in out
        assert "boom" in out

    @pytest.mark.parametrize("status", ["cancelled", "closed"])
    def test_a_dropped_turn_that_was_stopped_says_so(self, client, capsys, status):
        # Printing nothing here, then the next prompt, read as a reply that went through.
        client.runs.wait.return_value = _run(status, output="half an answer")

        self._chat(client, ["hello", "/exit"], [DroppedStream()])

        out = capsys.readouterr().out
        assert f"❌ Turn {status}: the run was {status}" in out
        assert "half an answer" not in out

    def test_a_queued_reply_is_waited_for_by_its_own_receipt(self, client):
        client.runs.wait.return_value = _run()
        it = iter(["hello", "again", "/exit"])
        client.runs.create.side_effect = [FinishedStream()]
        client.runs.reply.side_effect = [DroppedStream(await_queued_message_id=55)]

        with (
            patch("m8tes.cli.display.create_display", return_value=_display()),
            patch("builtins.input", lambda *_: next(it)),
        ):
            MateCLI(client).chat_interactive("3")

        assert _waited(client)["await_queued_message_id"] == 55

    def test_text_that_was_cut_off_is_marked_before_the_full_answer(self, client, capsys):
        # Greptile outside-diff on 752626a: the streamed prefix and the full answer
        # both stay on screen, and nothing said which was which.
        client.runs.wait.return_value = _run(output="Here is the answer.")

        self._chat(client, ["hello", "/exit"], [DroppedStream()], display=_display("Here is"))

        out = capsys.readouterr().out
        assert out.index("The text above was cut off") < out.index("Here is the answer.")

    def test_a_drop_before_any_text_marks_nothing(self, client, capsys):
        client.runs.wait.return_value = _run(output="Here is the answer.")

        self._chat(client, ["hello", "/exit"], [DroppedStream()], display=_display(""))

        assert "cut off" not in capsys.readouterr().out

    def test_json_mode_keeps_stdout_for_events(self, client, capsys):
        client.runs.wait.return_value = _run(output="Here is the answer.")
        client.runs.create.side_effect = [DroppedStream()]

        with (
            patch("m8tes.cli.display.create_display", return_value=_display("Here is")),
            patch("sys.stdin", io.StringIO("hello\n\n")),
        ):
            MateCLI(client).chat_interactive("3", output_format="json")

        captured = capsys.readouterr()
        assert "Connection lost" in captured.err
        assert captured.out == ""

    def test_json_mode_reports_a_turn_that_did_not_answer_on_stderr(self, client, capsys):
        client.runs.wait.return_value = _run("cancelled")
        client.runs.create.side_effect = [DroppedStream()]

        with (
            patch("m8tes.cli.display.create_display", return_value=_display()),
            patch("sys.stdin", io.StringIO("hello\n\n")),
        ):
            MateCLI(client).chat_interactive("3", output_format="json")

        captured = capsys.readouterr()
        assert "❌ Turn cancelled: the run was cancelled" in captured.err
        assert captured.out == ""

    def test_the_wait_stays_inside_the_end_user_scope(self, client):
        client.runs.wait.return_value = _run()
        it = iter(["hello", "/exit"])
        client.runs.create.side_effect = [DroppedStream()]

        with (
            patch("m8tes.cli.display.create_display", return_value=_display()),
            patch("builtins.input", lambda *_: next(it)),
        ):
            MateCLI(client).chat_interactive("3", user_id="customer_42")

        assert _waited(client)["user_id"] == "customer_42"

    def test_the_next_message_replies_to_the_run_that_dropped(self, client):
        # Starting a second run here would drop the conversation and bill twice.
        client.runs.wait.return_value = _run()

        self._chat(client, ["hello", "again", "/exit"], [DroppedStream(), FinishedStream()])

        client.runs.create.assert_called_once()
        client.runs.reply.assert_called_once_with(7, message="again", stream=True)


class TestTaskExecute:
    def _execute(self, client, stream, monkeypatch, display=None, **cli_kwargs):
        display = display or _display()
        monkeypatch.setattr("m8tes.cli.display.create_display", lambda fmt: display)
        client.tasks.get.return_value = Task.from_dict(
            {
                "id": 42,
                "teammate_id": 3,
                "name": "weekly recap",
                "instructions": "Summarize the week",
                "status": "enabled",
                "created_at": "2026-08-01T10:00:00Z",
            }
        )
        client.tasks.run.return_value = stream
        TaskCLI(client, **cli_kwargs).execute_interactive("42")

    def test_a_dropped_stream_waits_for_the_run_and_prints_its_output(
        self, client, monkeypatch, capsys
    ):
        client.runs.wait.return_value = _run(output="Weekly recap: all good.")
        display = _display()

        self._execute(client, DroppedStream(), monkeypatch, display=display)

        assert _waited(client)["user_id"] is None
        assert "Weekly recap: all good." in capsys.readouterr().out
        display.finish.assert_called_once_with(show_response=False)

    def test_the_wait_stays_inside_the_end_user_scope(self, client, monkeypatch):
        client.runs.wait.return_value = _run()

        self._execute(client, DroppedStream(), monkeypatch, user_id="customer_42")

        assert _waited(client)["user_id"] == "customer_42"

    def test_a_dropped_run_that_failed_fails_the_command(self, client, monkeypatch, capsys):
        client.runs.wait.return_value = _run("failed", error="credential expired")

        with pytest.raises(RunFailedError) as exc:
            self._execute(client, DroppedStream(), monkeypatch)

        assert exc.value.details["errors"] == ["credential expired"]
        assert "credential expired" in capsys.readouterr().out

    @pytest.mark.parametrize("status", ["cancelled", "closed"])
    def test_a_dropped_run_that_was_stopped_fails_the_command(
        self, client, monkeypatch, capsys, status
    ):
        client.runs.wait.return_value = _run(status, output="half the recap")

        with pytest.raises(RunFailedError) as exc:
            self._execute(client, DroppedStream(), monkeypatch)

        assert exc.value.details["errors"] == [f"the run was {status}"]
        # A stopped run's partial output is neither the result nor the error.
        assert "half the recap" not in capsys.readouterr().out

    def test_text_that_was_cut_off_is_marked_before_the_full_output(
        self, client, monkeypatch, capsys
    ):
        client.runs.wait.return_value = _run(output="Weekly recap: all good.")

        self._execute(client, DroppedStream(), monkeypatch, display=_display("Weekly rec"))

        out = capsys.readouterr().out
        assert out.index("The text above was cut off") < out.index("Weekly recap: all good.")

    def test_a_command_with_nobody_at_the_terminal_does_not_prompt(self, client, monkeypatch):
        client.runs.wait.return_value = _run()

        self._execute(client, DroppedStream(), monkeypatch)

        assert _waited(client)["on_approval"] is _stop_at_approval


class TestTheResponsePanelAfterADrop:
    """The rich display closes on a panel of the text so far, titled Response. After a
    drop that text is not the answer, so the panel is left out."""

    def _shown(self, **finish) -> str:
        console = Console(file=io.StringIO(), width=100, color_system=None)
        display = VerboseDisplay(console=console)
        delta = {"type": "text_delta", "text": "half an ans"}
        for event in StreamEvent.from_dict(
            {"type": "content_block_delta", "id": "b1", "delta": delta}
        ):
            display.on_event(event)
        display.finish(**finish)
        return console.file.getvalue()

    def test_text_shown_before_a_drop_is_not_presented_as_the_response(self):
        assert "Response" not in self._shown(show_response=False)

    def test_a_finished_stream_still_gets_its_response_panel(self):
        assert "Response" in self._shown()
