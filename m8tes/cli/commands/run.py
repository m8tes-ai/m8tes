"""
Run management commands for the m8tes CLI.

Provides commands for viewing run details and history.
"""

from argparse import ArgumentParser, Namespace
from typing import TYPE_CHECKING, ClassVar, Optional

from ..._exceptions import M8tesError as SDKM8tesError
from ...exceptions import AgentError, AuthenticationError, NetworkError
from ..base import Command, CommandGroup
from ..v2 import v2_client_from_args

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
        self.add_subcommand(SetPermissionModeCommand())
        self.add_subcommand(ToolsCommand())
        self.add_subcommand(RetryRunCommand())
        self.add_subcommand(AuditLogsCommand())


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

            # /detail returns the run's fields FLAT plus aggregated metrics.
            details = client.runs.get(run_id).get_details()

            print(f"\n📊 Run Details - ID: {run_id}")
            print(f"{'=' * 60}")

            print("\n🔹 Basic Info:")
            print(f"   Status: {details.get('status', 'N/A')}")
            print(f"   Agent ID: {details.get('instance_id', 'N/A')}")
            if details.get("task_name"):
                print(f"   Task: {details['task_name']}")
            print(f"   Description: {details.get('description') or 'No description'}")
            print(f"   Created: {details.get('created_at', 'N/A')}")

            print(f"\n💬 Conversation: {details.get('message_count', 0)} messages")

            print("\n💰 Token Usage:")
            print(f"   Total Cost: ${float(details.get('total_cost_usd') or 0):.4f}")
            print(f"   Total Tokens: {int(details.get('total_tokens') or 0):,}")

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
                print(f"   Agent ID: {run.instance_id}")
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
    description = "List runs for a specific agent"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add list-mate-specific arguments."""
        parser.add_argument("mate_id", help="Agent ID")
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

            print(f"🏃 Runs for Agent {mate_id} (showing {len(runs)})")
            print()

            if not runs:
                print("No runs found for this agent.")
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
            print("❌ Invalid agent ID")
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

            # Aggregated metrics from the run detail (per-message metrics live
            # on /messages; there is no per-model breakdown endpoint).
            usage = client.runs.get(run_id).get_usage()

            print(f"\n💰 Token Usage - Run ID: {run_id}")
            print(f"{'=' * 60}")

            print("\n📊 Summary:")
            print(f"   Total Cost: ${float(usage.get('total_cost_usd') or 0):.4f}")
            print(f"   Total Tokens: {int(usage.get('total_tokens') or 0):,}")
            print(f"   Messages: {usage.get('message_count', 0)}")

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

            # Tool calls are derived from message content blocks — the API does
            # not track per-call success/duration, so only name + args render.
            for i, tool in enumerate(tools, 1):
                print(f"{i}. {tool.get('tool_name', 'Unknown')}")

                if verbose and tool.get("arguments") is not None:
                    args_str = str(tool["arguments"])
                    print(
                        f"   Arguments: {args_str[:100]}..."
                        if len(args_str) > 100
                        else f"   Arguments: {args_str}"
                    )

                print()

            return 0

        except (AgentError, AuthenticationError, NetworkError) as e:
            print(f"❌ Error retrieving tool executions: {e}")
            return 1


class SetPermissionModeCommand(Command):
    """Switch permission mode on an active run."""

    name = "set-permission-mode"
    aliases: ClassVar[list[str]] = ["mode"]
    description = "Switch an active run between autonomous, approval, and plan"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("run_id", type=int, help="Run ID")
        parser.add_argument(
            "permission_mode",
            choices=["autonomous", "approval", "plan"],
            help="New permission mode",
        )

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        if not client:
            print("❌ Authentication required")
            return 1

        try:
            with v2_client_from_args(args, client) as v2_client:
                result = v2_client.runs.update_permission_mode(
                    args.run_id,
                    permission_mode=args.permission_mode,
                )

            print("\n✅ Permission mode updated")
            print(f"   Run ID: {args.run_id}")
            print(f"   Permission mode: {result.permission_mode}")
            if result.permission_mode == "autonomous":
                print("   Pending tool approvals were auto-approved. Questions still need answers.")
            return 0
        except SDKM8tesError as e:
            print(f"❌ Failed to update permission mode: {e}")
            return 1


class RetryRunCommand(Command):
    """Retry a failed or cancelled run."""

    name = "retry"
    aliases: ClassVar[list[str]] = ["rerun"]
    description = "Retry a failed or cancelled run (creates a new run)"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("run_id", type=int, help="Run ID to retry")
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Acknowledge that retrying may repeat actions the run already took",
        )

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        if not client:
            print("❌ Authentication required")
            return 1

        try:
            with v2_client_from_args(args, client) as v2_client:
                run = v2_client.runs.retry(args.run_id, confirm=args.confirm)
            print("\n✅ Retry started")
            print(f"   New run: {run.id} (retry of {run.retry_of_run_id})")
            print(f"   Status: {run.status}")
            print(f"   Watch:  m8tes run get {run.id}")
            return 0
        except SDKM8tesError as e:
            if getattr(e, "code", None) == "retry_needs_confirmation":
                print(
                    "⚠️  This run already performed actions, so retrying may repeat them.\n"
                    f"   Re-run with --confirm to proceed: m8tes run retry {args.run_id} --confirm"
                )
                return 1
            print(f"❌ Failed to retry run: {e}")
            return 1


class AuditLogsCommand(Command):
    """List account-scoped v2 API request audit logs."""

    name = "audit-logs"
    aliases: ClassVar[list[str]] = ["logs"]
    description = "List account API request audit logs"
    requires_auth = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--limit", type=int, default=20, help="Maximum logs to return")
        parser.add_argument(
            "--action",
            choices=["list", "read", "create", "update", "delete"],
            help="Filter by action",
        )
        parser.add_argument("--resource-type", help="Filter by resource type (for example run)")
        parser.add_argument(
            "--method",
            choices=["GET", "POST", "PATCH", "PUT", "DELETE"],
            help="Filter by HTTP method",
        )
        parser.add_argument("--status-code", type=int, help="Filter by status code")

    def execute(self, args: Namespace, client: Optional["M8tes"] = None) -> int:
        if not client:
            print("❌ Authentication required")
            return 1

        try:
            with v2_client_from_args(args, client) as v2_client:
                page = v2_client.audit_logs.list(
                    action=getattr(args, "action", None),
                    resource_type=getattr(args, "resource_type", None),
                    method=getattr(args, "method", None),
                    status_code=getattr(args, "status_code", None),
                    limit=getattr(args, "limit", 20),
                )

            if not page.data:
                print("No audit logs found.")
                return 0

            print(f"\n🧾 Audit Logs (showing {len(page.data)})")
            print(f"{'=' * 80}")
            for log in page.data:
                resource = (
                    f"{log.resource_type}/{log.resource_id}"
                    if log.resource_type and log.resource_id
                    else (log.resource_type or "N/A")
                )
                action = log.action or "N/A"
                print(
                    f"{log.id:>6}  {log.method:<6} {log.status_code:<3} "
                    f"{resource:<20} {action:<7} {log.path}"
                )
            if page.has_more:
                print("\nMore logs available. Use --limit to fetch a larger page.")
            return 0
        except SDKM8tesError as e:
            print(f"❌ Failed to list audit logs: {e}")
            return 1
