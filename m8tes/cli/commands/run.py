"""
Run management commands for the m8tes CLI.

Provides commands for viewing run details and history.
"""

from argparse import ArgumentParser, Namespace
from typing import TYPE_CHECKING, ClassVar, Optional

from ...exceptions import AgentError, AuthenticationError, NetworkError
from ..base import Command, CommandGroup

if TYPE_CHECKING:
    from ...client import M8tes


class RunCommandGroup(CommandGroup):
    """Run management command group."""

    name = "run"
    aliases: ClassVar[list[str]] = ["r"]
    description = "View run details and history"
    requires_auth = True

    def __init__(self) -> None:
        super().__init__()
        # Register all run subcommands
        self.add_subcommand(GetRunCommand())
        self.add_subcommand(ListRunsCommand())
        self.add_subcommand(ListTeammateRunsCommand())
        self.add_subcommand(ConversationCommand())
        self.add_subcommand(UsageCommand())
        self.add_subcommand(ToolsCommand())


class GetRunCommand(Command):
    """Get run details command."""

    name = "get"
    aliases: ClassVar[list[str]] = ["g"]
    description = "Get run details by ID"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add get-specific arguments."""
        parser.add_argument("run_id", help="Run ID to retrieve")

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        """Execute run get."""
        if not client:
            print("❌ Authentication required")
            return 1

        try:
            run_id = int(args.run_id)

            # Get comprehensive run details
            run = client.runs.get(run_id)
            details = run.get_details()

            print(f"\n📊 Run Details - ID: {run_id}")
            print(f"{'=' * 60}")

            # Basic info
            run_data = details.get("run", {})
            print("\n🔹 Basic Info:")
            print(f"   Mode: {run_data.get('run_mode', 'N/A')}")
            print(f"   Instance ID: {run_data.get('instance_id', 'N/A')}")
            print(f"   Description: {run_data.get('description', 'No description')}")
            print(f"   Created: {run_data.get('created_at', 'N/A')}")

            # Conversation
            conversation = details.get("conversation", {})
            message_count = conversation.get("message_count", 0)
            print(f"\n💬 Conversation: {message_count} messages")

            # Usage
            usage = details.get("usage", {})
            total_cost = usage.get("totalCost", 0)
            total_tokens = usage.get("totalTokens", 0)
            print("\n💰 Token Usage:")
            print(f"   Total Cost: ${total_cost:.4f}")
            print(f"   Total Tokens: {total_tokens:,}")

            # Tool executions
            tool_data = details.get("tool_executions", {})
            executions = tool_data.get("executions", [])
            print(f"\n🔧 Tool Executions: {len(executions)}")
            for tool in executions:
                status = "✅" if tool.get("success") else "❌"
                print(f"   {status} {tool.get('tool_name')} ({tool.get('duration_ms')}ms)")

            print()
            return 0

        except (AgentError, AuthenticationError, NetworkError) as e:
            print(f"❌ Error getting run: {e}")
            return 1
        except ValueError:
            print("❌ Invalid run ID")
            return 1


class ListRunsCommand(Command):
    """List all runs command."""

    name = "list"
    aliases: ClassVar[list[str]] = ["ls"]
    description = "List all runs"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add list-specific arguments."""
        parser.add_argument("--limit", type=int, default=10, help="Maximum runs to return")

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        """Execute run listing."""
        if not client:
            print("❌ Authentication required")
            return 1

        try:
            limit = getattr(args, "limit", 10)
            runs = client.runs.list_user_runs(limit=limit)

            print(f"🏃 Your Runs (showing {len(runs)})")
            print()

            if not runs:
                print("No runs found.")
                return 0

            for run in runs:
                print(f"🏃 Run {run.id} - {run.run_mode}")
                print(f"   Teammate ID: {run.instance_id}")
                if run.description:
                    desc = (
                        run.description[:60] + "..."
                        if len(run.description) > 60
                        else run.description
                    )
                    print(f"   Task: {desc}")
                print(f"   Created: {run.created_at}")
                print()

            return 0
        except (AgentError, AuthenticationError, NetworkError) as e:
            print(f"❌ Error listing runs: {e}")
            return 1


class ListTeammateRunsCommand(Command):
    """List runs for a specific teammate."""

    name = "list-mate"
    aliases: ClassVar[list[str]] = ["lm"]
    description = "List runs for a specific teammate"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add list-mate-specific arguments."""
        parser.add_argument("mate_id", help="Teammate ID")
        parser.add_argument("--limit", type=int, default=10, help="Maximum runs to return")

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        """Execute teammate run listing."""
        if not client:
            print("❌ Authentication required")
            return 1

        try:
            mate_id = int(args.mate_id)
            limit = getattr(args, "limit", 10)
            runs = client.runs.list_for_instance(mate_id, limit=limit)

            print(f"🏃 Runs for Teammate {mate_id} (showing {len(runs)})")
            print()

            if not runs:
                print("No runs found for this teammate.")
                return 0

            for run in runs:
                print(f"🏃 Run {run.id} - {run.run_mode}")
                if run.description:
                    desc = (
                        run.description[:60] + "..."
                        if len(run.description) > 60
                        else run.description
                    )
                    print(f"   Task: {desc}")
                print(f"   Created: {run.created_at}")
                if run.duration_seconds:
                    print(f"   Duration: {run.duration_seconds}s")
                print()

            return 0
        except (AgentError, AuthenticationError, NetworkError) as e:
            print(f"❌ Error listing runs: {e}")
            return 1
        except ValueError:
            print("❌ Invalid teammate ID")
            return 1


class ConversationCommand(Command):
    """View run conversation history."""

    name = "conversation"
    aliases: ClassVar[list[str]] = ["conv", "messages"]
    description = "View run conversation history"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add conversation-specific arguments."""
        parser.add_argument("run_id", type=int, help="Run ID")

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        """Execute conversation view."""
        if not client:
            print("❌ Authentication required")
            return 1

        try:
            run_id = args.run_id

            # Get run and conversation
            run = client.runs.get(run_id)
            messages = run.get_conversation()

            print(f"\n💬 Conversation - Run ID: {run_id}")
            print(f"{'=' * 60}")
            print(f"\n{len(messages)} messages:\n")

            for msg in messages:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")

                # Format based on role
                if role == "system":
                    print(
                        f"🔧 System: {content[:100]}..."
                        if len(content) > 100
                        else f"🔧 System: {content}"
                    )
                elif role == "user":
                    print("\n👤 User:")
                    print(f"   {content}")
                elif role == "assistant":
                    print("\n🤖 Assistant:")
                    print(f"   {content}")
                elif role == "tool":
                    tool_call_id = msg.get("tool_call_id", "N/A")
                    print(f"\n🔧 Tool Response (ID: {tool_call_id}):")
                    print(f"   {content[:200]}..." if len(content) > 200 else f"   {content}")

            print()
            return 0

        except (AgentError, AuthenticationError, NetworkError) as e:
            print(f"❌ Error retrieving conversation: {e}")
            return 1


class UsageCommand(Command):
    """View run token usage and costs."""

    name = "usage"
    aliases: ClassVar[list[str]] = ["cost"]
    description = "View run token usage and costs"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add usage-specific arguments."""
        parser.add_argument("run_id", type=int, help="Run ID")

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        """Execute usage view."""
        if not client:
            print("❌ Authentication required")
            return 1

        try:
            run_id = args.run_id

            # Get run and usage data
            run = client.runs.get(run_id)
            usage = run.get_usage()

            print(f"\n💰 Token Usage - Run ID: {run_id}")
            print(f"{'=' * 60}")

            # Overall stats
            total_cost = usage.get("totalCost", 0)
            total_tokens = usage.get("totalTokens", 0)

            print("\n📊 Summary:")
            print(f"   Total Cost: ${total_cost:.4f}")
            print(f"   Total Tokens: {total_tokens:,}")

            # Breakdown by usage record (if available)
            usage_records = usage.get("usage", [])
            if usage_records:
                print(f"\n📝 Usage Records ({len(usage_records)}):")
                for record in usage_records:
                    model = record.get("model", "N/A")
                    prompt_tokens = record.get("promptTokens", 0)
                    completion_tokens = record.get("completionTokens", 0)
                    cost = record.get("estimatedCost", 0)
                    print(f"\n   Model: {model}")
                    print(f"   Prompt Tokens: {prompt_tokens:,}")
                    print(f"   Completion Tokens: {completion_tokens:,}")
                    print(f"   Cost: ${cost:.4f}")

            print()
            return 0

        except (AgentError, AuthenticationError, NetworkError) as e:
            print(f"❌ Error retrieving usage: {e}")
            return 1


class ToolsCommand(Command):
    """View run tool executions."""

    name = "tools"
    aliases: ClassVar[list[str]] = ["executions"]
    description = "View run tool executions"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add tools-specific arguments."""
        parser.add_argument("run_id", type=int, help="Run ID")
        parser.add_argument(
            "--verbose", "-v", action="store_true", help="Show detailed tool information"
        )

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        """Execute tools view."""
        if not client:
            print("❌ Authentication required")
            return 1

        try:
            run_id = args.run_id
            verbose = args.verbose

            # Get run and tool executions
            run = client.runs.get(run_id)
            tools = run.get_tool_executions()

            print(f"\n🔧 Tool Executions - Run ID: {run_id}")
            print(f"{'=' * 60}")

            if not tools:
                print("\n   No tool executions found")
                print()
                return 0

            print(f"\n{len(tools)} tool executions:\n")

            for i, tool in enumerate(tools, 1):
                tool_name = tool.get("tool_name", "Unknown")
                success = tool.get("success", False)
                duration = tool.get("duration_ms", 0)
                status = "✅ Success" if success else "❌ Failed"

                print(f"{i}. {tool_name}")
                print(f"   Status: {status}")
                print(f"   Duration: {duration}ms")

                if verbose:
                    # Show arguments
                    args_str = tool.get("arguments", "")
                    if args_str:
                        print(
                            f"   Arguments: {args_str[:100]}..."
                            if len(args_str) > 100
                            else f"   Arguments: {args_str}"
                        )

                    # Show result or error
                    if success:
                        result = tool.get("result", "")
                        if result:
                            print(
                                f"   Result: {result[:100]}..."
                                if len(result) > 100
                                else f"   Result: {result}"
                            )
                    else:
                        error = tool.get("error_message", "No error message")
                        print(f"   Error: {error}")

                print()

            return 0

        except (AgentError, AuthenticationError, NetworkError) as e:
            print(f"❌ Error retrieving tool executions: {e}")
            return 1
