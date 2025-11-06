import io

from rich.console import Console

from m8tes.cli.display import VerboseDisplay
from m8tes.streaming import (
    StreamEventType,
    ToolCallStartEvent,
    ToolResultEndEvent,
)


def test_verbose_display_prevents_overlapping_progress(monkeypatch):
    """Ensure VerboseDisplay stops an active spinner before starting a new one."""
    active_instances = {"count": 0}

    class DummyProgress:
        def __init__(self, *args, **kwargs):
            self.started = False

        def start(self) -> None:
            if self.started:
                raise RuntimeError("progress already started")
            if active_instances["count"]:
                raise RuntimeError("another progress is already active")
            self.started = True
            active_instances["count"] += 1

        def add_task(self, *args, **kwargs):
            return "dummy-task"

        def stop(self) -> None:
            if self.started:
                self.started = False
                active_instances["count"] = max(0, active_instances["count"] - 1)

    monkeypatch.setattr("m8tes.cli.display.Progress", DummyProgress)

    display = VerboseDisplay()

    # Route output to in-memory buffer so Rich doesn't touch the real terminal.
    display.console = Console(file=io.StringIO(), force_terminal=False, color_system=None)

    first_tool = ToolCallStartEvent(
        type=StreamEventType.TOOL_CALL_START,
        raw={},
        tool_call_id="call-1",
        tool_name="TodoWrite",
    )
    second_tool = ToolCallStartEvent(
        type=StreamEventType.TOOL_CALL_START,
        raw={},
        tool_call_id="call-2",
        tool_name="mcp__google_ads__gaql_query",
    )

    # Starting the first tool should open exactly one progress spinner.
    display.on_event(first_tool)
    assert active_instances["count"] == 1

    # Starting a second tool while the first is active should stop the first spinner first.
    # The dummy progress raises if a previous instance is still active.
    display.on_event(second_tool)
    assert active_instances["count"] == 1

    # Ending the second tool should clean up the remaining spinner.
    display.on_event(
        ToolResultEndEvent(
            type=StreamEventType.TOOL_RESULT_END,
            raw={},
            tool_call_id="call-2",
            result={},
        )
    )
    assert active_instances["count"] == 0
