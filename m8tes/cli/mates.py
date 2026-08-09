"""
Teammate management CLI commands, built on the v2 SDK client.

Provides interactive commands for creating and managing m8tes agents via
``client.agents`` (CRUD) and ``client.runs`` (task execution + chat).

Error contract: fatal failures raise (typed SDK exceptions where possible) so
the command layer maps them to a non-zero exit code. Helpers never swallow a
fatal error — a swallowed error made `m8tes mate list` exit 0 on auth failure.
"""

# mypy: disable-error-code="union-attr,arg-type,index,assignment,no-untyped-def"
from typing import TYPE_CHECKING

from .._exceptions import (
    APIError,
    AuthenticationError,
    M8tesError,
    NotFoundError,
    PermissionDeniedError,
    RunFailedError,
    ValidationError,
)
from .prompt import confirm_prompt, prompt
from .util import parse_id

if TYPE_CHECKING:
    from .._client import M8tes
    from .._types import Teammate


def _parse_mate_id(mate_id: str) -> int:
    return parse_id(mate_id, "Teammate ID")


# Available tools with descriptions
AVAILABLE_TOOLS = [
    {
        "id": "run_gaql_query",
        "name": "Google Ads Query (GAQL)",
        "description": (
            "Execute GAQL queries to retrieve Google Ads campaign data, metrics, and performance"
        ),
    },
]

# One page covers every realistic CLI account; auto_paging_iter handles the rest.
_LIST_LIMIT = 100


class MateCLI:
    """CLI for teammate management operations."""

    def __init__(self, client: "M8tes"):
        """
        Initialize MateCLI.

        Args:
            client: v2 M8tes SDK client
        """
        self.client = client

    def select_or_confirm_mate(self, mate_id: int | None) -> int | None:
        """
        Get mate ID with auto-detection and user confirmation.

        If mate_id is provided, returns it directly (explicit selection).
        Otherwise auto-detects client-side (the v1 auto-detect endpoint has no
        v2 twin): the most recently created enabled agent.

        Args:
            mate_id: Optional mate ID (if provided, returns immediately)

        Returns:
            Confirmed mate ID, or None if cancelled

        Flow:
            1. If mate_id provided → return it (explicit selection)
            2. Auto-detect most recently created enabled agent → show details
            3. Prompt: "Use this agent? [Y/n]"
            4. If yes → return detected ID
            5. If no or none enabled → show mate list and prompt for selection
        """
        # If mate_id explicitly provided, use it
        if mate_id is not None:
            return mate_id

        try:
            # Page through everything: .data alone caps at one page, and an account
            # whose only enabled agent sits past it would read as "none enabled".
            agents = list(self.client.agents.list(limit=_LIST_LIMIT).auto_paging_iter())
        except AuthenticationError:
            # Handle authentication errors with clear guidance
            print()
            print("❌ Authentication failed")
            api_key = getattr(self.client, "api_key", None)
            if api_key and api_key.startswith("m8_"):
                print("   Check that your API key is valid: m8tes --api-key m8_...")
            else:
                print("   Please login first: m8tes auth login")
            print()
            return None
        except M8tesError as e:
            print(f"❌ Failed to list agents: {e}")
            return None

        enabled = [a for a in agents if a.status == "enabled"]
        if enabled:
            detected = max(enabled, key=lambda a: (a.created_at or "", a.id))
            print()
            print("🔍 Auto-detected agent:")
            print(f"   📋 {detected.name} (ID: {detected.id})")
            print("   ✨ Most recently created")
            print()
            if confirm_prompt("Use this agent?", default=True):
                return detected.id
            # User declined - fall through to manual selection
            print()
        else:
            print()
            print("⚠️  No enabled agents found for auto-detection")
            print()

        print("📋 Available agents:")
        if not agents:
            print("   No agents found.")
            print("💡 Create an agent first: m8tes agent create")
            return None

        for idx, inst in enumerate(agents, 1):
            status_emoji = "✅" if inst.status == "enabled" else "⏸️"
            print(f"   {idx}. {status_emoji} {inst.name} (ID: {inst.id})")
        print()

        selection = prompt(
            "Select agent (number or ID), or press Enter to cancel: ", allow_empty=True
        )
        if not selection.strip():
            print("❌ Cancelled")
            return None

        # Parse selection: 1-based list index first, then direct agent ID.
        try:
            number = int(selection)
        except ValueError:
            print(f"❌ Invalid selection: {selection}")
            return None
        if 1 <= number <= len(agents):
            return agents[number - 1].id
        if any(inst.id == number for inst in agents):
            return number
        print(f"❌ Agent ID {number} not found")
        return None

    def create_interactive(self) -> None:
        """
        Interactive teammate creation flow.

        All fields must be explicitly configured by the user.
        """
        return self._create_mate()

    def create_non_interactive(
        self,
        name: str,
        tools: list[str],
        instructions: str,
        *,
        role: str | None = None,
        goals: str | None = None,
        inbound_imessage_enabled: bool = False,
        imessage_chat_guid: str | None = None,
    ) -> None:
        """
        Non-interactive teammate creation.

        Args:
            name: Teammate name
            tools: List of tool IDs
            instructions: Teammate instructions
            role: Optional teammate role/identity
            goals: Optional goals and metrics payload (plain text)
            inbound_imessage_enabled: Enable inbound Apple Messages routing
            imessage_chat_guid: BlueBubbles chat GUID used for inbound routing and replies
        """
        role = role.strip() if isinstance(role, str) else role
        if not role:
            role = None
        goals = goals.strip() if isinstance(goals, str) else goals
        if goals is not None and not goals:
            goals = None
        if inbound_imessage_enabled and not imessage_chat_guid:
            raise ValidationError("--imessage-chat-guid is required when --enable-imessage is set")
        instance = self.client.agents.create(
            name=name,
            tools=tools,
            instructions=instructions,
            role=role,
            goals=goals,
            inbound_imessage_enabled=inbound_imessage_enabled,
            imessage_chat_guid=imessage_chat_guid,
        )

        print("✅ Agent created successfully!")
        self._show_mate_usage_guide(instance)

    def _create_mate(self) -> None:
        """
        Simplified teammate creation with explicit configuration.

        All fields must be explicitly configured by the user.
        No auto-detection or "vibe mode" - everything is explicit.
        """
        print("🤝 Create New Agent")
        print()
        print("Configure your agent by providing all required information.")
        print()

        # Step 1: Role (optional)
        mate_role = None
        role_input = prompt("Agent role (optional, e.g., Campaign Optimizer): ", allow_empty=True)
        if role_input:
            mate_role = role_input

        # Step 2: Name (required)
        mate_name = prompt("Agent name: ")
        if not mate_name.strip():
            print("❌ Agent name cannot be empty")
            return

        # Step 3: Instructions (required)
        print()
        print("Instructions: Describe what this agent should do.")
        print("Add clear instructions on role and responsibilities of the agent.")
        print("When you're finished press Enter twice")
        print()

        instructions_lines: list[str] = []
        try:
            while True:
                line = input()
                if line.strip().lower() == "/done":
                    break
                if line == "" and instructions_lines and instructions_lines[-1] == "":
                    break
                instructions_lines.append(line)
        except EOFError:
            pass

        instructions = "\n".join(instructions_lines).strip()
        if not instructions:
            print("❌ Instructions cannot be empty")
            return

        # Step 4: Tools (required, explicit selection)
        print()
        print("=" * 60)
        print("Available Tools:")
        print("=" * 60)
        for idx, tool in enumerate(AVAILABLE_TOOLS, 1):
            print(f"\n{idx}. {tool['name']} ({tool['id']})")
            print(f"   {tool['description']}")
        print("\n" + "=" * 60)
        print()

        tools: list[str] = []
        tool_input = prompt(
            "Select tools (comma-separated numbers or IDs, or press Enter to skip): ",
            allow_empty=True,
        )

        if tool_input.strip():
            tools = self._parse_tool_selection(tool_input.strip())
            if tools is None:
                print("❌ Invalid tool selection")  # type: ignore[unreachable]
                return  # type: ignore[unreachable]

        if not tools:
            print("⚠️  Warning: No tools selected. Agent will have no tool access.")
            if not confirm_prompt("Continue without tools?", default=False):
                print("❌ Agent creation cancelled")
                return

        # Step 5: Goals & Metrics (optional, text)
        print()
        print("=" * 60)
        print("Goals & Metrics (optional): Describe what success looks like for this agent.")
        print("=" * 60)
        print()
        print("Enter text and press Enter to finish. Leave blank to skip.")
        print()
        goals: str | None = None
        initial_goals = prompt("Goals & metrics: ", allow_empty=True)

        if initial_goals.strip():
            goals_lines: list[str] = [initial_goals]
            print("Add more lines (optional):")
            try:
                while True:
                    line = input()
                    if line == "":
                        break
                    goals_lines.append(line)
            except EOFError:
                pass

            goals = "\n".join(goals_lines).strip()

        # Show summary
        print()
        print("=" * 60)
        print("📋 Agent Configuration Summary:")
        print("=" * 60)
        print(f"  Name: {mate_name}")
        if mate_role:
            print(f"  Role: {mate_role}")
        print(f"  Instructions: {instructions[:100]}{'...' if len(instructions) > 100 else ''}")
        print(f"  Tools: {', '.join(tools) if tools else 'None'}")
        if goals:
            print("  Goals:")
            for line in goals.splitlines():
                print(f"    {line}")
        print("=" * 60)
        print()

        # Confirm creation
        if not confirm_prompt("Create this agent?", default=True):
            print("❌ Agent creation cancelled")
            return

        # Create the teammate
        print("⏳ Creating agent...")
        instance = self.client.agents.create(
            name=mate_name,
            tools=tools,
            instructions=instructions,
            role=mate_role,
            goals=goals,
        )

        print("✅ Agent created successfully!")
        self._show_mate_usage_guide(instance)

    def _parse_tool_selection(self, tool_input: str) -> list[str] | None:
        """
        Parse user's tool selection input.

        Args:
            tool_input: User input (comma-separated numbers or IDs)

        Returns:
            List of tool IDs, or None if invalid
        """
        tools = []
        parts = [p.strip() for p in tool_input.split(",")]

        for part in parts:
            # Try parsing as number (index)
            try:
                idx = int(part) - 1  # Convert to 0-based index
                if 0 <= idx < len(AVAILABLE_TOOLS):
                    tools.append(AVAILABLE_TOOLS[idx]["id"])
                else:
                    print(f"❌ Invalid tool number: {part} (must be 1-{len(AVAILABLE_TOOLS)})")
                    return None
            except ValueError:
                # Not a number, check if it's a valid tool ID
                tool_ids = [t["id"] for t in AVAILABLE_TOOLS]
                if part in tool_ids:
                    tools.append(part)
                else:
                    print(f"❌ Unknown tool ID: {part}")
                    print(f"   Available tools: {', '.join(tool_ids)}")
                    return None

        # Remove duplicates while preserving order
        return list(dict.fromkeys(tools))

    def list_interactive(self, include_disabled: bool = False) -> None:
        """
        Interactive teammate listing.

        Args:
            include_disabled: Include disabled (and archived) teammates in listing
        """
        print("👥 Your Agents")
        print()

        # v2 always lists disabled agents alongside enabled ones (only archived
        # agents are hidden), so the default view filters client-side and the
        # flag widens the fetch to archived too.
        page = self.client.agents.list(limit=_LIST_LIMIT, include_archived=include_disabled)
        agents = list(page.auto_paging_iter())
        if not include_disabled:
            agents = [a for a in agents if a.status == "enabled"]

        if not agents:
            print("No agents found.")
            print("💡 Create your first agent with: m8tes agent create")
            if not include_disabled:
                print("💡 To see disabled agents: m8tes agent list --include-disabled")
            return

        for instance in agents:
            # Status emoji
            if instance.status == "enabled":
                status_emoji = "✅"
            elif instance.status == "disabled":
                status_emoji = "⏸️"
            else:
                status_emoji = "📦"  # archived or other

            print(f"{status_emoji} {instance.name}")
            print(f"   ID: {instance.id}")
            print(f"   Status: {instance.status}")
            if instance.role:
                print(f"   Role: {instance.role}")
            tools_display = ", ".join(instance.tools) if instance.tools else "None"
            print(f"   Tools: {tools_display}")

            # Truncate instructions smartly
            instructions = (instance.instructions or "").strip()
            if instructions:
                if len(instructions) > 80:
                    instructions = instructions[:77] + "..."
                print(f"   Instructions: {instructions}")
            else:
                print("   Instructions: (none provided)")

            if instance.goals:
                goals_preview = instance.goals.strip().replace("\n", " / ")
                if len(goals_preview) > 80:
                    goals_preview = goals_preview[:77] + "..."
                print(f"   Goals: {goals_preview}")

            print()

    def get_interactive(self, mate_id: str) -> None:
        """
        Interactive teammate details display.

        Args:
            mate_id: Teammate ID to retrieve
        """
        instance = self.client.agents.get(_parse_mate_id(mate_id))

        print("🤝 Agent Details")
        print()
        print(f"  ID: {instance.id}")
        print(f"  Name: {instance.name}")
        if instance.role:
            print(f"  Role: {instance.role}")
        print(f"  Status: {instance.status}")
        tools_display = ", ".join(instance.tools) if instance.tools else "None"
        print(f"  Tools: {tools_display}")
        instructions = instance.instructions or "(none provided)"
        print(f"  Instructions: {instructions}")
        if instance.goals:
            print("  Goals:")
            for line in instance.goals.splitlines():
                print(f"    {line}")
        else:
            print("  Goals: None")
        print()
        print(f"  Created: {instance.created_at}")

    def task_interactive(
        self,
        message: str,
        mate_id: str,
        output_format: str = "verbose",
        debug: bool = False,
        task_setup_tools: bool = True,
    ) -> None:
        """
        Execute a one-off task with the teammate using streaming.

        Args:
            message: Task description
            mate_id: Teammate ID to use
            output_format: Display format ("verbose", "compact", or "json")
            debug: Enable debug mode with detailed logging
            task_setup_tools: When False, force-disable built-in same-scope
                management tools for this run (True inherits the agent default)
        """
        from .display import create_display

        # Show task header (unless json mode)
        if output_format != "json":
            print(f"🎯 Task: {message}")
            print()

        instance = self.client.agents.get(_parse_mate_id(mate_id))

        if output_format != "json":
            print(f"🤝 Using: {instance.name} (ID: {instance.id})")
            print()

        if debug:
            print("[DEBUG] Starting task execution...")
            print()

        # Create display renderer
        display = create_display(output_format)
        display.start()

        # Stream task execution. task_setup_tools=None inherits the agent
        # default; only an explicit False (the --no-task-setup-tools flag)
        # overrides it for this run.
        stream = self.client.runs.create(
            agent_id=instance.id,
            message=message,
            stream=True,
            task_setup_tools=None if task_setup_tools else False,
        )

        event_count = 0
        try:
            for event in stream:
                event_count += 1
                if debug and output_format != "json":
                    print(f"[DEBUG] Event #{event_count}: {event.type}")
                display.on_event(event)

            display.finish()

            if debug:
                print(f"\n[DEBUG] Received {event_count} events")
                print(f"[DEBUG] Text accumulated: {len(display.get_final_text())} chars")
                print(f"[DEBUG] Errors: {len(display.accumulator.get_errors())}")

            # Check for errors or empty response
            has_errors = display.accumulator.has_errors()
            has_text = bool(display.get_final_text())
            has_tool_calls = bool(display.accumulator.get_tool_calls())

            if has_errors and output_format != "json":
                print("\n❌ Agent encountered errors:")
                for error in display.accumulator.get_errors():
                    print(f"   {error}")
            elif not has_text and not has_tool_calls and output_format != "json":
                print("\n⚠️  Warning: Agent produced no output")
                if not debug:
                    print("   This may indicate a configuration or API issue.")
                    print("   Run with --debug for more details.")

            # Show run summary with results
            self._show_run_summary(stream.run_id, output_format, debug=debug)

            # Show completion (unless json mode)
            if output_format != "json":
                print()
                if has_errors:
                    print("❌ Task failed")
                else:
                    print("✅ Task completed")

            if has_errors:
                raise RunFailedError("Run finished with errors")

        except KeyboardInterrupt:
            display.finish()
            print("\n\n⏸️  Task interrupted")
            raise

    def _validated_resume_run_id(self, run_id: int, instance, output_format: str) -> int | None:
        """Confirm a resume target actually belongs to the selected mate.

        The v2 server replies on the RUN's own agent regardless of which mate the
        chat header shows, so an unvalidated id would silently continue a different
        mate's conversation under this one's name (the legacy client rejected the
        mismatch server-side).
        """
        from .._exceptions import M8tesError

        try:
            run = self.client.runs.get(run_id)
        except M8tesError as exc:
            if output_format != "json":
                print(f"❌ Cannot resume run {run_id}: {exc}")
            return None
        if run.teammate_id is not None and run.teammate_id != instance.id:
            if output_format != "json":
                print(
                    f"❌ Run {run_id} belongs to agent {run.teammate_id}, "
                    f"not {instance.name} (ID: {instance.id})"
                )
            return None
        return run_id

    def chat_interactive(
        self, mate_id: str, resume_run_id: int | None = None, output_format: str = "verbose"
    ) -> None:
        """
        Start an interactive chat session with the teammate using streaming.

        The v2 API has no standing chat session: the first message creates a
        run (runs.create), follow-ups continue it (runs.reply). The run ID is
        therefore announced after the first response, not before it.

        Args:
            mate_id: Teammate ID to use
            resume_run_id: Optional run ID to resume (replies continue that run)
            output_format: Display format ("verbose", "compact", or "json")

        Supports commands:
        - /exit or /quit - Exit chat session
        - /clear - Clear conversation history (next message starts a fresh run)
        - /resume <run_id> - Resume from a different run
        """
        from .display import create_display

        if output_format != "json":
            print(
                "💬 Chat Mode - Type /exit to quit, /clear to reset history, "
                "/resume <run_id> to switch runs"
            )
            print()

        instance = self.client.agents.get(_parse_mate_id(mate_id))
        run_id: int | None = None
        if resume_run_id is not None:
            run_id = self._validated_resume_run_id(resume_run_id, instance, output_format)
        if output_format != "json":
            print(f"🤝 Chatting with: {instance.name} (ID: {instance.id})")
            if run_id:
                print(f"🔄 Resumed session from run {run_id}")
            print()

        try:
            while True:
                try:
                    # Get user input
                    if output_format != "json":
                        message = input("> ")
                    else:
                        # In JSON mode, read from stdin
                        import sys

                        message = sys.stdin.readline().strip()
                        if not message:
                            break

                    # Handle empty messages
                    if not message.strip():
                        continue

                    # Handle commands
                    if message.strip() in ["/exit", "/quit"]:
                        if output_format != "json":
                            print("\n👋 Chat session ended")
                        break

                    if message.strip() == "/clear":
                        # A fresh run = fresh history; nothing to clear server-side.
                        run_id = None
                        if output_format != "json":
                            print("✅ Conversation history cleared")
                        continue

                    if message.strip().startswith("/resume "):
                        # Extract run ID from command
                        parts = message.strip().split()
                        if len(parts) != 2:
                            if output_format != "json":
                                print("❌ Usage: /resume <run_id>")
                            continue

                        try:
                            candidate = int(parts[1])
                        except ValueError:
                            if output_format != "json":
                                print(f"❌ Invalid run ID: {parts[1]} (must be a number)")
                            continue
                        validated = self._validated_resume_run_id(
                            candidate, instance, output_format
                        )
                        if validated is not None:
                            run_id = validated
                            if output_format != "json":
                                print(f"🔄 Resumed session from run {run_id}")
                                print()
                        continue

                    # Create display renderer
                    display = create_display(output_format)
                    display.start()

                    # Stream message response: first message creates the run,
                    # follow-ups reply to it.
                    stream = None
                    try:
                        is_first = run_id is None
                        if is_first:
                            stream = self.client.runs.create(
                                agent_id=instance.id, message=message, stream=True
                            )
                        else:
                            stream = self.client.runs.reply(run_id, message=message, stream=True)

                        for event in stream:
                            display.on_event(event)

                        display.finish()

                        if is_first and stream.run_id:
                            run_id = stream.run_id
                            if output_format != "json":
                                print(f"📝 Session Run ID: {run_id}")

                        # Newline after response (unless json mode)
                        if output_format != "json":
                            print()

                    except KeyboardInterrupt:
                        display.finish()
                        # The run keeps executing server-side, and its id arrives
                        # in the stream's first metadata event — capture it so the
                        # next message REPLIES to this run instead of forking a
                        # second one and silently dropping this context. Best-effort
                        # by construction: an interrupt BEFORE that event leaves the
                        # id unknowable client-side, so say so rather than pretend.
                        if is_first and stream is not None and stream.run_id:
                            run_id = stream.run_id
                        if output_format != "json":
                            print("\n⏸️  Message interrupted (the run continues server-side)")
                            if is_first and run_id is None:
                                print(
                                    "⚠️  Its run ID hadn't arrived yet — the next message "
                                    "starts a NEW run; find this one with: m8tes run list"
                                )
                        continue

                except EOFError:
                    # Handle Ctrl+D
                    if output_format != "json":
                        print("\n\n👋 Chat session ended")
                    break

        except KeyboardInterrupt:
            # Handle Ctrl+C
            if output_format != "json":
                print("\n\n👋 Chat session ended")

    def update_interactive(self, mate_id: str) -> None:
        """
        Interactive teammate update flow.

        Args:
            mate_id: Teammate ID to update
        """
        # Get current teammate
        instance = self.client.agents.get(_parse_mate_id(mate_id))

        print(f"🔧 Update Agent: {instance.name} (ID: {instance.id})")
        print()
        print("Current configuration:")
        print(f"  Name: {instance.name}")
        print(f"  Instructions: {instance.instructions}")
        print()

        # Prompt for new values
        print("Enter new values (press Enter to keep current):")
        print()

        new_name = prompt(f"Name [{instance.name}]: ", allow_empty=True)
        if not new_name:
            new_name = None

        print()
        print("Instructions (current):")
        print(f"  {instance.instructions}")
        print()
        new_instructions = prompt("New instructions (or press Enter to keep): ", allow_empty=True)

        # Check if anything changed
        if not new_name and not new_instructions:
            print("❌ No changes made")
            return

        # Confirm update
        print()
        print("📋 Update Summary:")
        if new_name:
            print(f"  Name: {instance.name} → {new_name}")
        if new_instructions:
            print("  Instructions: Updated")
        print()

        if not confirm_prompt("Apply these changes?", default=True):
            print("❌ Update cancelled")
            return

        # Update teammate (empty strings mean "keep current", so send None)
        print("⏳ Updating agent...")
        self.client.agents.update(
            instance.id, name=new_name or None, instructions=new_instructions or None
        )

        print("✅ Agent updated successfully!")

    def update_non_interactive(
        self,
        mate_id: str,
        name: str | None = None,
        instructions: str | None = None,
        *,
        inbound_imessage_enabled: bool | None = None,
        imessage_chat_guid: str | None = None,
    ) -> None:
        """
        Non-interactive teammate update.

        Args:
            mate_id: Teammate ID to update
            name: New name (optional)
            instructions: New instructions (optional)
            inbound_imessage_enabled: Enable or disable Apple Messages routing
            imessage_chat_guid: Updated BlueBubbles chat GUID
        """
        # Get current teammate (validates the ID before patching)
        instance = self.client.agents.get(_parse_mate_id(mate_id))

        self.client.agents.update(
            instance.id,
            name=name,
            instructions=instructions,
            inbound_imessage_enabled=inbound_imessage_enabled,
            imessage_chat_guid=imessage_chat_guid,
        )

        print("✅ Agent updated successfully!")
        print(f"   ID: {instance.id}")
        if name:
            print(f"   New Name: {name}")
        if instructions:
            print("   Instructions: Updated")

    def enable_interactive(self, mate_id: str) -> None:
        """
        Interactive teammate enable flow.

        Args:
            mate_id: Teammate ID to enable
        """
        try:
            # Get teammate info
            instance = self.client.agents.get(_parse_mate_id(mate_id))

            print(f"✅ Enable Agent: {instance.name} (ID: {instance.id})")
            print()
            print(f"  Current status: {instance.status}")
            print()

            if instance.status == "enabled":
                print("⚠️  Agent is already enabled")
                return

            # Enable teammate
            print("⏳ Enabling agent...")
            updated = self.client.agents.enable(instance.id)

            print("✅ Agent enabled successfully!")
            print(f"   Status: {updated.status}")

        except ValidationError as e:
            print(f"❌ Failed to enable agent: {e}")
            raise
        except APIError as e:
            print(f"❌ Network error: {e}")
            print("   Check your connection and try again")
            raise

    def disable_interactive(self, mate_id: str, force: bool = False) -> None:
        """
        Interactive teammate disable flow.

        Args:
            mate_id: Teammate ID to disable
            force: Skip confirmation prompt
        """
        try:
            # Get teammate info
            instance = self.client.agents.get(_parse_mate_id(mate_id))

            print(f"⏸️  Disable Agent: {instance.name} (ID: {instance.id})")
            print()
            print(f"  Status: {instance.status}")
            print()

            if instance.status == "disabled":
                print("⚠️  Agent is already disabled")
                return

            # Confirm action
            if not force:
                print("⚠️  This will disable the agent (soft disable).")
                print("   • Agent will be marked as disabled")
                print("   • Still visible with --include-disabled flag")
                print("   • Run history will be preserved")
                print("   • Agent can be re-enabled anytime")
                print()
                if not confirm_prompt("Disable this agent?", default=False):
                    print("❌ Operation cancelled")
                    return

            # Disable teammate
            print("⏳ Disabling agent...")
            updated = self.client.agents.disable(instance.id)

            print("✅ Agent disabled successfully!")
            print(f"   Status: {updated.status}")
            print("   Run history has been preserved.")
            print(f"💡 To re-enable: m8tes agent enable {instance.id}")

        except ValidationError as e:
            print(f"❌ Failed to disable agent: {e}")
            raise
        except APIError as e:
            print(f"❌ Network error: {e}")
            print("   Check your connection and try again")
            raise

    def archive_interactive(self, mate_id: str, force: bool = False) -> None:
        """
        Interactive teammate archiving flow (v2 agents.delete = archive).

        Args:
            mate_id: Teammate ID to archive
            force: Skip confirmation prompt
        """
        try:
            # Get teammate info
            instance = self.client.agents.get(_parse_mate_id(mate_id))

            print(f"🗑️  Archive Agent: {instance.name} (ID: {instance.id})")
            print()
            print(f"  Status: {instance.status}")
            print()

            # Confirm archiving
            if not force:
                print("⚠️  This will archive the agent (hidden from listings).")
                print("   • Agent will be archived and hidden from listings")
                print("   • Run history will be preserved")
                print("   • Use disable instead if you want to keep it visible")
                print()
                if not confirm_prompt("Archive this agent?", default=False):
                    print("❌ Operation cancelled")
                    return

            # Archive teammate (raises on failure)
            print("⏳ Archiving agent...")
            self.client.agents.delete(instance.id)

            print("✅ Agent archived successfully!")
            print("   Run history has been preserved.")

        except NotFoundError:
            print(f"❌ Agent not found: No agent with ID {mate_id}")
            print("   Use 'm8tes agent list' to see available agents")
            raise
        except PermissionDeniedError:
            print("❌ Access denied: You don't have permission to archive this agent")
            raise
        except ValidationError as e:
            print(f"❌ Failed to archive agent: {e}")
            raise
        except APIError as e:
            print(f"❌ Network error: {e}")
            print("   Check your connection and try again")
            raise

    def _show_run_summary(
        self, run_id: int | None, output_format: str = "verbose", debug: bool = False
    ) -> None:
        """
        Display run summary with results and details.

        Args:
            run_id: Run ID captured from the stream's metadata event
            output_format: Output format ("verbose", "compact", or "json")
            debug: Enable debug output
        """
        # Skip summary in JSON mode (raw events only)
        if output_format == "json":
            return

        try:
            if not run_id:
                if debug:
                    print("\n[DEBUG] No run ID captured from the stream")
                return

            if debug:
                print(f"\n[DEBUG] Fetching details for run ID: {run_id}")

            # outcome() carries the aggregated usage; the transcript comes from
            # messages(). Tool calls are derived from message content blocks.
            conversation_error: str | None = None
            not_found = False
            outcome = None
            try:
                outcome = self.client.runs.outcome(run_id)
            except M8tesError as e:
                conversation_error = str(e)
                not_found = isinstance(e, NotFoundError)
                if debug:
                    print(f"[DEBUG] runs.outcome() failed: {e}")
            try:
                messages = self.client.runs.messages(run_id)
            except M8tesError as conv_err:
                messages = []
                if conversation_error is None:
                    conversation_error = str(conv_err)
                    not_found = isinstance(conv_err, NotFoundError)
                if debug:
                    print(f"[DEBUG] runs.messages() failed: {conv_err}")

            tool_names = [
                block.get("name", "unknown")
                for msg in messages
                for block in (msg.content_blocks or [])
                if isinstance(block, dict) and block.get("type") == "tool_use"
            ]

            # Get final teammate response from conversation
            final_response = None
            for msg in reversed(messages):
                if msg.role == "assistant":
                    final_response = msg.content
                    break

            # Display summary based on format
            if output_format == "compact":
                # Compact: just show final response or error message
                if final_response:
                    print(f"\n{final_response}")
                elif not_found:
                    print("\n⚠️  No conversation data (agent may have failed)")
            else:
                # Verbose: full summary
                print()
                print("=" * 60)
                print("📊 Run Summary")
                print("=" * 60)

                # Show warning if no conversation data
                if not messages and conversation_error:
                    print("\n⚠️  No conversation data available")
                    if not_found:
                        print("   The agent execution may have failed before generating output.")
                        if debug:
                            print(f"   Error: {conversation_error}")
                        else:
                            print("   Run with --debug for more details.")
                    else:
                        print(f"   Error: {conversation_error}")

                # Final response
                if final_response:
                    print("\n🤝 Agent Response:")
                    print(f"{final_response}")

                # Tool executions (names only — the API tracks no per-call status)
                if tool_names:
                    print(f"\n⚡ Tools Used: {len(tool_names)}")
                    for tool_name in tool_names:
                        print(f"   🔧 {tool_name}")

                # Usage stats (cost_usd arrives as a decimal string)
                total_tokens = outcome.total_tokens if outcome else 0
                total_cost = float(outcome.cost_usd or 0) if outcome else 0.0
                if total_tokens or total_cost:
                    print("\n💰 Usage:")
                    if total_tokens:
                        print(f"   Tokens: {total_tokens:,}")
                    if total_cost:
                        print(f"   Cost: ${total_cost:.4f}")

                print("\n" + "=" * 60)

        except Exception as e:
            # Don't fail the whole task if summary fails
            if output_format == "verbose":
                print(f"\n⚠️  Could not fetch run summary: {e}")
                if debug:
                    import traceback

                    print("\n[DEBUG] Full traceback:")
                    traceback.print_exc()

    def _show_mate_usage_guide(self, instance: "Teammate", mode: str | None = None) -> None:
        """
        Show comprehensive usage guide after teammate creation.

        Args:
            instance: Created teammate
            mode: Optional mode hint ('task', 'chat', or None for both)
        """
        print("\n" + "=" * 60)
        print("🎉 Agent Ready!")
        print("=" * 60)

        print("\n📋 Agent Details:")
        print(f"   ID: {instance.id}")
        print(f"   Name: {instance.name}")
        if instance.role:
            print(f"   Role: {instance.role}")
        if instance.tools:
            print(f"   Tools: {', '.join(instance.tools)}")
        if instance.goals:
            print("   Goals:")
            for line in instance.goals.splitlines():
                print(f"      {line}")

        print("\n🚀 How to Use Your Agent:")

        # Task mode examples
        if mode != "chat":
            print("\n1️⃣  Run a one-off task:")
            print(f'   m8tes agent task {instance.id} "Your task here"')

            # Show tool-specific examples if Google Ads tools are available
            if any(
                "google_ads" in tool.lower() or "gaql" in tool.lower() for tool in instance.tools
            ):
                print("\n   💡 Google Ads Example:")
                print(f'   m8tes agent task {instance.id} "What\'s my daily Google Ads spend?"')

        # Chat mode examples
        if mode != "task":
            print("\n2️⃣  Start an interactive chat session:")
            print(f"   m8tes agent chat {instance.id}")

        # General commands
        print("\n📊 Other Commands:")
        print("   m8tes agent list         # View all your agents")
        print(f"   m8tes agent get {instance.id}     # Get agent details")
        print(f"   m8tes agent update {instance.id}  # Update agent configuration")

        print("\n📚 Need Help?")
        print("   m8tes agent --help")
        print()
