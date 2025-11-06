"""
CLI display components for streaming agent output.

Provides different output formats for rendering streaming events:
- VerboseDisplay: Rich terminal UI with spinners, colors, and formatting
- CompactDisplay: Minimal output showing only essential information
- JsonDisplay: Raw JSON events for scripting and debugging
"""

from abc import ABC, abstractmethod
import json
import re
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TaskID, TextColumn

from ..streaming import (
    DoneEvent,
    ErrorEvent,
    MetadataEvent,
    PlanDeltaEvent,
    PlanEndEvent,
    PlanStartEvent,
    ReasoningDeltaEvent,
    ReasoningEndEvent,
    ReasoningStartEvent,
    SandboxConnectedEvent,
    SandboxConnectingEvent,
    StreamAccumulator,
    StreamEvent,
    TextDeltaEvent,
    ThinkingDeltaEvent,
    ThinkingEndEvent,
    ThinkingStartEvent,
    TodoUpdateEvent,
    ToolCallEndEvent,
    ToolCallStartEvent,
    ToolResultDeltaEvent,
    ToolResultEndEvent,
)


class StreamDisplay(ABC):
    """Base class for stream display renderers."""

    def __init__(self, console: Console | None = None) -> None:
        """Initialize display."""
        self.accumulator = StreamAccumulator()
        self.console = console or Console()

    @abstractmethod
    def on_event(self, event: StreamEvent) -> None:
        """
        Handle a stream event.

        Args:
            event: Stream event to process and display
        """
        pass

    @abstractmethod
    def start(self) -> None:
        """Start the display (called before first event)."""
        pass

    @abstractmethod
    def finish(self) -> None:
        """Finish the display (called after last event or on error)."""
        pass

    def get_final_text(self) -> str:
        """
        Get accumulated final text from streaming.

        Returns:
            Complete text response from agent
        """
        return self.accumulator.get_text()


class CompactDisplay(StreamDisplay):
    """
    Compact display showing only final text output.

    Minimal output - just shows the agent's final response text without
    tool call details or progress indicators.
    """

    def __init__(self, console: Console | None = None) -> None:
        super().__init__(console=console)
        self.connection_shown = False

    def start(self) -> None:
        """Start compact display (no-op)."""
        pass

    def on_event(self, event: StreamEvent) -> None:
        """Display only text deltas."""
        self.accumulator.process(event)

        if isinstance(event, SandboxConnectingEvent):
            # Show connection start message
            print("⏳ Connecting...", flush=True)
            self.connection_shown = True

        elif isinstance(event, SandboxConnectedEvent):
            if self.connection_shown:
                # Clear the connecting message and show connected
                # Use \r to go back to start of line, then clear with spaces
                duration_sec = (event.duration_ms / 1000) if event.duration_ms else 0
                print(f"\r✅ Connected to teammate! ({duration_sec:.1f}s)")
                print()  # Blank line after connection
                self.connection_shown = False

        elif isinstance(event, TextDeltaEvent):
            # Print text without newline
            print(event.delta, end="", flush=True)

        elif isinstance(event, ErrorEvent):
            # Show errors
            self.console.print(f"\n[red]❌ Error: {event.error}[/red]")

    def finish(self) -> None:
        """Finish with newline."""
        if self.accumulator.get_text():
            print()  # Final newline after text


class VerboseDisplay(StreamDisplay):
    """
    Verbose display with rich terminal UI.

    Shows:
    - Real-time text streaming
    - Tool call progress with spinners
    - Tool results in formatted panels
    - Reasoning (for o3-mini etc) in distinct style
    - Errors with clear formatting
    """

    def __init__(self, console: Console | None = None) -> None:
        super().__init__(console=console)
        self.current_tool_call: str | None = None
        self.current_tool_name: str | None = None
        self.progress: Progress | None = None
        self.task_id: TaskID | None = None
        self.plan_started: bool = False
        self.plan_chars_emitted: int = 0
        self.latest_usage: dict[str, Any] | None = None
        self._printed_todo_updates: int = 0
        self.thinking_active: bool = False
        self.completed_tools: set[str] = set()
        self.connection_progress: Progress | None = None
        self.connection_task_id: TaskID | None = None

    def start(self) -> None:
        """Start verbose display."""
        # Don't start live display yet - wait for first event
        pass

    def on_event(self, event: StreamEvent) -> None:
        """Display event with rich formatting."""
        self.accumulator.process(event)

        # Handle sandbox connection events
        if isinstance(event, SandboxConnectingEvent):
            # Start connection progress indicator
            self.connection_progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console,
            )
            self.connection_progress.start()
            self.connection_task_id = self.connection_progress.add_task(
                "[yellow]Connecting...[/yellow]",
                total=None,
            )
            return

        if isinstance(event, SandboxConnectedEvent):
            # Stop connection progress and show success
            if self.connection_progress and self.connection_task_id is not None:
                self.connection_progress.stop()
                self.connection_progress = None
                duration_sec = (event.duration_ms / 1000) if event.duration_ms else 0
                self.console.print(f"[green]Connected![/green] ({duration_sec:.1f}s)")
                self.console.print()  # Blank line after connection
            return

        if isinstance(event, TextDeltaEvent):
            self.console.print(event.delta, end="", style="white")
            return

        if isinstance(event, ReasoningStartEvent | ThinkingStartEvent):
            self._ensure_thinking_section()
            return

        if isinstance(event, ReasoningDeltaEvent | ThinkingDeltaEvent):
            self._ensure_thinking_section()
            self.console.print(event.delta, end="", style="dim italic cyan")
            return

        if isinstance(event, ReasoningEndEvent | ThinkingEndEvent):
            if self.thinking_active:
                self.console.print()
                self.thinking_active = False
            return

        if isinstance(event, PlanStartEvent):
            self._handle_plan_start()
            return

        if isinstance(event, PlanDeltaEvent):
            self._render_plan_delta()
            return

        if isinstance(event, PlanEndEvent):
            self.plan_chars_emitted = len(self.accumulator.get_plan())
            if self.plan_started:
                self.console.print()
            self.plan_started = False
            return

        if isinstance(event, ToolCallStartEvent):
            self._handle_tool_call_start(event)
            return

        if isinstance(event, ToolResultDeltaEvent):
            self._handle_tool_result_delta()
            return

        if isinstance(event, ToolResultEndEvent):
            self._handle_tool_result_end(event)
            return

        if isinstance(event, ToolCallEndEvent):
            self._handle_tool_call_end(event)
            return

        if isinstance(event, TodoUpdateEvent):
            self._render_todo_update(event.todos)
            return

        if isinstance(event, ErrorEvent):
            self._stop_progress(reset_current_tool=True)
            error_panel = Panel(
                f"[red]{event.error}[/red]",
                title="[red]❌ Error[/red]",
                border_style="red",
            )
            self.console.print(error_panel)
            return

        if isinstance(event, MetadataEvent):
            usage = event.payload.get("usage") if isinstance(event.payload, dict) else None
            if isinstance(usage, dict):
                self.latest_usage = usage
            return

        if isinstance(event, DoneEvent):
            return

    def _ensure_thinking_section(self) -> None:
        """Display thinking header once per reasoning run."""
        if not self.thinking_active:
            self.console.print("\n[dim cyan]🧠 Thinking...[/dim cyan]")
            self.thinking_active = True

    def _handle_plan_start(self) -> None:
        """Prepare plan display when a new plan begins."""
        self.plan_chars_emitted = len(self.accumulator.get_plan())
        self.plan_started = False
        self._render_plan_header_if_needed()

    def _render_plan_header_if_needed(self) -> None:
        """Ensure plan header is shown before streaming plan content."""
        if not self.plan_started:
            self.console.print("\n[bold magenta]🗺️ Plan[/bold magenta]")
            self.plan_started = True

    def _render_plan_delta(self) -> None:
        """Stream plan content incrementally."""
        self._render_plan_header_if_needed()
        plan_text = self.accumulator.get_plan()
        new_segment = plan_text[self.plan_chars_emitted :]
        if new_segment:
            self.console.print(new_segment, end="", style="magenta")
            self.plan_chars_emitted = len(plan_text)

    def _handle_tool_call_start(self, event: ToolCallStartEvent) -> None:
        """Render tool call start with spinner feedback."""
        self._stop_progress()
        if event.tool_call_id:
            self.completed_tools.discard(event.tool_call_id)
        self.current_tool_call = event.tool_call_id
        self.current_tool_name = event.tool_name

        self.console.print()
        display_name = event.tool_name or "Unknown tool"
        self.console.print(
            f"[bold cyan]⚡ Calling tool:[/bold cyan] [yellow]{display_name}[/yellow]"
        )

        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
            transient=True,
        )
        self.progress.start()
        task_label = f"Executing {display_name}..."
        self.task_id = self.progress.add_task(task_label, total=None)

    def _handle_tool_result_delta(self) -> None:
        """Keep spinner responsive while tool streams results."""
        if self.progress and self.task_id is not None and self.current_tool_name:
            self.progress.update(
                self.task_id,
                description=f"{self.current_tool_name} (streaming result...)",
            )

    def _handle_tool_result_end(self, event: ToolResultEndEvent) -> None:
        """Render tool completion with optional result payload."""
        tool_id = event.tool_call_id
        tool_name = self._resolve_tool_name(tool_id)
        self._stop_progress()
        if tool_id:
            self.completed_tools.add(tool_id)

        message = "[green]✅ Tool completed[/green]"
        if tool_name:
            message = f"[green]✅ Completed tool:[/green] [yellow]{tool_name}[/yellow]"

        self.console.print()
        self.console.print(message)

        tool_result_payload = event.result
        if not tool_result_payload and tool_id:
            tool_result_payload = self.accumulator.get_tool_calls().get(tool_id, {}).get("result")
        if tool_result_payload:
            result_text = self._format_tool_result(tool_result_payload)
            title_name = tool_name or "Tool Result"
            panel = Panel(
                result_text,
                title=f"[green]✓[/green] Tool Result: {title_name}",
                border_style="green",
                expand=False,
            )
            self.console.print(panel)

        self.current_tool_call = None
        self.current_tool_name = None

    def _handle_tool_call_end(self, event: ToolCallEndEvent) -> None:
        """Ensure spinner stops even if no explicit tool result arrives."""
        tool_id = event.tool_call_id
        tool_name = self._resolve_tool_name(tool_id)
        already_reported = bool(tool_id and tool_id in self.completed_tools)

        self._stop_progress()

        if not already_reported:
            message = "[green]✅ Tool completed[/green]"
            if tool_name:
                message = f"[green]✅ Completed tool:[/green] [yellow]{tool_name}[/yellow]"
            self.console.print()
            self.console.print(message)
            if tool_id:
                self.completed_tools.add(tool_id)

        self.current_tool_call = None
        self.current_tool_name = None

    def _resolve_tool_name(self, tool_call_id: str | None) -> str | None:
        """Lookup tool name from accumulator state."""
        if tool_call_id:
            tool_data = self.accumulator.get_tool_calls().get(tool_call_id)
            if tool_data and tool_data.get("name"):
                name = tool_data["name"]
                return str(name) if name is not None else None
        return self.current_tool_name

    def _format_tool_result(self, result: object) -> str:
        """Format tool result for display."""
        if isinstance(result, dict):
            # Pretty print JSON
            try:
                json_str = json.dumps(result, indent=2)
                # Truncate if too long
                if len(json_str) > 500:
                    json_str = json_str[:497] + "..."
                return json_str
            except Exception:
                return str(result)
        elif isinstance(result, list):
            # Show list summary
            count = len(result)
            if count > 5:
                sample = result[:5]
                sample_json = json.dumps(sample, indent=2)
                return f"List with {count} items (showing first 5):\n{sample_json}\n..."
            else:
                return json.dumps(result, indent=2)
        else:
            return str(result)

    def _render_todo_update(self, todos: list[dict[str, Any]]) -> None:
        """Render todo updates with status summary."""
        if not todos:
            return

        status_icon = {
            "completed": "✅",
            "in_progress": "🔧",
            "pending": "🕒",
        }

        completed = sum(1 for todo in todos if todo.get("status") == "completed")
        total = len(todos)
        in_progress = sum(1 for todo in todos if todo.get("status") == "in_progress")

        header = f"\n[bold blue]📝 Todo Update[/bold blue] ({completed}/{total} completed"
        if in_progress:
            header += f", {in_progress} in progress"
        header += ")"
        self.console.print(header)

        for idx, todo in enumerate(todos, start=1):
            status = todo.get("status", "pending")
            icon = status_icon.get(status, "•")
            text = todo.get("activeForm") or todo.get("content") or todo.get("title") or ""
            if not text:
                text = json.dumps(todo, ensure_ascii=False)
            self.console.print(f"{idx}. {icon} {text}")

        self._printed_todo_updates += 1

    def finish(self) -> None:
        """Cleanup verbose display."""
        self._stop_progress()

        if self.thinking_active:
            self.console.print()
            self.thinking_active = False

        plan_text = self.accumulator.get_plan()
        if plan_text and self.plan_chars_emitted < len(plan_text):
            self.console.print("\n[bold magenta]🗺️ Plan[/bold magenta]")
            remaining_plan = plan_text[self.plan_chars_emitted :]
            self.console.print(remaining_plan, style="magenta")

        usage = self.latest_usage or self.accumulator.get_usage()
        if usage:
            tokens = usage.get("token_count") or usage.get("tokens")
            cost = usage.get("cost") or usage.get("total_cost")
            details: list[str] = []
            if tokens is not None:
                details.append(f"tokens={tokens}")
            if cost is not None:
                details.append(f"cost={cost}")
            if details:
                usage_line = "[dim]Usage: " + ", ".join(details) + "[/dim]"
                self.console.print(f"\n{usage_line}")

        if self._printed_todo_updates == 0:
            final_updates = self.accumulator.get_todo_updates()
            if final_updates:
                self._render_todo_update(final_updates[-1]["todos"])

        final_text = self.accumulator.get_text()
        final_text_stripped = final_text.strip()

        if final_text_stripped:
            self.console.print()
            self.console.print(
                _build_markdown_panel(
                    final_text,
                    title="[cyan]Response[/cyan]",
                    empty_message="[dim]No response generated.[/dim]",
                )
            )
        elif final_text:
            # Preserve legacy behavior of ending with newline if only whitespace streamed
            self.console.print()

    def _stop_progress(self, *, reset_current_tool: bool = False) -> None:
        """Safely stop the active spinner to avoid overlapping Live displays."""
        if self.progress:
            try:
                self.progress.stop()
            except Exception:
                # Progress.stop() can raise if Rich internals already cleaned up.
                pass
            finally:
                self.progress = None
        self.task_id = None

        if reset_current_tool:
            self.current_tool_call = None
            self.current_tool_name = None


class JsonDisplay(StreamDisplay):
    """
    JSON display for raw event streaming.

    Outputs each event as a JSON line for machine consumption.
    Useful for:
    - Scripting and automation
    - Debugging event streams
    - Integration with other tools
    """

    def __init__(self, console: Console | None = None) -> None:
        super().__init__(console=console)

    def start(self) -> None:
        """Start JSON display (no-op)."""
        pass

    def on_event(self, event: StreamEvent) -> None:
        """Output event as JSON line."""
        # Don't accumulate - just output raw
        output = {
            "type": event.type,
            **event.raw,
        }
        print(json.dumps(output), flush=True)

    def finish(self) -> None:
        """Finish JSON display (no-op)."""
        pass


_TASK_LIST_PATTERN = re.compile(r"^(\s*[-*]\s+)\[([ xX])\]\s+(.*)$", flags=re.MULTILINE)


def _normalize_markdown(text: str) -> str:
    """Apply small GitHub-flavored markdown tweaks Rich lacks natively."""

    def replace(match: re.Match[str]) -> str:
        prefix, state, content = match.groups()
        symbol = "☑" if state.lower() == "x" else "☐"
        return f"{prefix}{symbol} {content}"

    return _TASK_LIST_PATTERN.sub(replace, text)


def _build_markdown_panel(
    text: str,
    *,
    title: str = "[cyan]Response[/cyan]",
    empty_message: str = "[dim]No response generated.[/dim]",
) -> Panel:
    """Convert raw markdown text into a Rich panel with consistent styling."""
    normalized = _normalize_markdown(text)
    if normalized.strip():
        content: Markdown | str = Markdown(normalized, code_theme="monokai", justify="left")
        panel_title: str | None = title
    else:
        content = empty_message
        panel_title = None
    return Panel(content, title=panel_title, border_style="cyan", expand=True)


def create_display(format: str = "verbose") -> StreamDisplay:
    """
    Factory function to create appropriate display.

    Args:
        format: Display format ("verbose", "compact", or "json")

    Returns:
        StreamDisplay instance
    """
    if format == "compact":
        return CompactDisplay()
    elif format == "json":
        return JsonDisplay()
    else:  # "verbose" is default
        return VerboseDisplay()
