"""
Teammate management CLI commands.

Provides interactive commands for creating and managing m8tes teammates.
"""

# mypy: disable-error-code="union-attr,arg-type,index,assignment,no-untyped-def"
from datetime import UTC
import json
from typing import Any

from ..client import M8tes
from .prompt import confirm_prompt, prompt

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


class MateCLI:
    """CLI for teammate management operations."""

    def __init__(self, client: M8tes):
        """
        Initialize MateCLI.

        Args:
            client: M8tes client instance
        """
        self.client = client

    def select_or_confirm_mate(self, mate_id: int | None) -> int | None:
        """
        Get mate ID with auto-detection and user confirmation.

        If mate_id is provided, returns it directly (explicit selection).
        Otherwise, attempts auto-detection and prompts for confirmation.

        Args:
            mate_id: Optional mate ID (if provided, returns immediately)

        Returns:
            Confirmed mate ID, or None if cancelled

        Flow:
            1. If mate_id provided → return it (explicit selection)
            2. Try auto-detect → show details with reason/timestamp
            3. Prompt: "Use this teammate? [Y/n]"
            4. If yes → return detected ID
            5. If no or 404 → show mate list and prompt for ID
        """
        # If mate_id explicitly provided, use it
        if mate_id is not None:
            return mate_id

        # Try auto-detection
        try:
            instance, metadata = self.client.instances.auto_detect()

            # Show detected teammate with details
            print()
            print("🔍 Auto-detected teammate:")
            print(f"   📋 {instance.name} (ID: {instance.id})")

            # Show reason for selection
            if metadata["reason"] == "last_used":
                # Format last_used_at timestamp
                last_used_str = metadata.get("last_used_at", "recently")
                if last_used_str and last_used_str != "recently":
                    try:
                        from datetime import datetime

                        dt = datetime.fromisoformat(last_used_str.replace("Z", "+00:00"))
                        last_used_str = self._format_timestamp(dt.isoformat())
                    except Exception:
                        last_used_str = "recently"
                print(f"   🕐 Last used: {last_used_str}")
            else:
                print("   ✨ Most recently created")

            print()

            # Prompt for confirmation
            if confirm_prompt("Use this teammate?", default=True):
                return instance.id

            # User declined - fall through to manual selection
            print()
            print("📋 Available teammates:")

        except Exception as e:
            # Import AuthenticationError for specific handling
            from ..exceptions import AuthenticationError

            # Handle authentication errors with clear guidance
            if isinstance(e, AuthenticationError):
                print()
                print("❌ Not authenticated")
                print("   Please login first: m8tes auth login")
                print()
                return None
            # Handle 404/not found errors
            elif "404" in str(e) or "not found" in str(e).lower():
                print()
                print("⚠️  No enabled teammates found for auto-detection")
            # Handle other errors
            else:
                print()
                print(f"⚠️  Auto-detection failed: {e}")

            print()
            print("📋 Available teammates:")

        # Show list of teammates and prompt for selection
        try:
            instances = self.client.instances.list()

            if not instances:
                print("   No teammates found.")
                print("💡 Create a teammate first: m8tes mate create")
                return None

            # Show teammate list
            for idx, inst in enumerate(instances, 1):
                status_emoji = "✅" if inst.status == "enabled" else "⏸️"
                print(f"   {idx}. {status_emoji} {inst.name} (ID: {inst.id})")

            print()

            # Prompt for selection
            selection = prompt(
                "Select teammate (number or ID), or press Enter to cancel: ", allow_empty=True
            )

            if not selection.strip():
                print("❌ Cancelled")
                return None

            # Parse selection (try as number first, then as ID)
            try:
                # Try parsing as 1-based index
                index = int(selection) - 1
                if 0 <= index < len(instances):
                    return instances[index].id
                else:
                    print(f"❌ Invalid selection: {selection}")
                    return None
            except ValueError:
                # Not a number - try as direct ID
                try:
                    mate_id = int(selection)
                    # Verify this ID exists in the list
                    if any(inst.id == mate_id for inst in instances):
                        return mate_id
                    else:
                        print(f"❌ Teammate ID {mate_id} not found")
                        return None
                except ValueError:
                    print(f"❌ Invalid selection: {selection}")
                    return None

        except Exception as e:
            # Import AuthenticationError for specific handling
            from ..exceptions import AuthenticationError

            # Handle authentication errors with clear guidance
            if isinstance(e, AuthenticationError):
                print()
                print("❌ Not authenticated")
                print("   Please login first: m8tes auth login")
                return None
            # Handle other errors
            else:
                print(f"❌ Failed to list teammates: {e}")
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
        integration_ids: list[int] | None = None,
    ) -> None:
        """
        Non-interactive teammate creation.

        Args:
            name: Teammate name
            tools: List of tool IDs
            instructions: Teammate instructions
            role: Optional teammate role/identity
            goals: Optional goals and metrics payload (plain text)
            integration_ids: Optional list of AppIntegration IDs (catalog references)
        """
        try:
            role = role.strip() if isinstance(role, str) else role
            if not role:
                role = None
            goals = goals.strip() if isinstance(goals, str) else goals
            if goals is not None and not goals:
                goals = None
            instance = self.client.instances.create(
                name=name,
                tools=tools,
                instructions=instructions,
                role=role,
                goals=goals,
                integration_ids=integration_ids,
            )

            print("✅ Teammate created successfully!")
            self._show_mate_usage_guide(instance)

        except Exception as e:
            raise Exception(f"Failed to create teammate: {e}") from e

    def _create_mate(self) -> None:
        """
        Simplified teammate creation with explicit configuration.

        All fields must be explicitly configured by the user.
        No auto-detection or "vibe mode" - everything is explicit.
        """
        print("🤝 Create New Teammate")
        print()
        print("Configure your teammate by providing all required information.")
        print()

        # Step 1: Role (optional)
        mate_role = None
        role_input = prompt(
            "Teammate role (optional, e.g., Campaign Optimizer): ", allow_empty=True
        )
        if role_input:
            mate_role = role_input

        # Step 2: Name (required)
        mate_name = prompt("Teammate name: ")
        if not mate_name.strip():
            print("❌ Teammate name cannot be empty")
            return

        # Step 3: Instructions (required)
        print()
        print("Instructions: Describe what this teammate should do.")
        print("Add clear instructions on role and responsibilities of the teammate.")
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
            print("⚠️  Warning: No tools selected. Teammate will have no tool access.")
            if not confirm_prompt("Continue without tools?", default=False):
                print("❌ Teammate creation cancelled")
                return

        # Step 5: Goals & Metrics (optional, text)
        print()
        print("=" * 60)
        print("Goals & Metrics (optional): Describe what success looks like for this teammate.")
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
        print("📋 Teammate Configuration Summary:")
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
        if not confirm_prompt("Create this teammate?", default=True):
            print("❌ Teammate creation cancelled")
            return

        # Create the teammate instance
        try:
            print("⏳ Creating teammate...")
            instance = self.client.instances.create(
                name=mate_name,
                tools=tools,
                instructions=instructions,
                role=mate_role,
                goals=goals,
            )

            print("✅ Teammate created successfully!")
            self._show_mate_usage_guide(instance)

        except Exception as e:
            print(f"❌ Failed to create teammate: {e}")

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

    def _parse_json(
        self,
        json_str: str,
        field_name: str,
        *,
        allowed_types: tuple[type, ...] = (dict,),
    ) -> Any | None:
        """
        Parse JSON string with error handling.

        Args:
            json_str: JSON string to parse
            field_name: Name of the field for error messages
            allowed_types: Accepted Python types for the parsed value

        Returns:
            Parsed JSON value, or None if invalid
        """
        try:
            data = json.loads(json_str)
            if not isinstance(data, allowed_types):
                allowed_names = " or ".join(
                    "object" if t is dict else ("array" if t is list else t.__name__)
                    for t in allowed_types
                )
                print(f"❌ {field_name} must be a JSON {allowed_names}, not {type(data).__name__}")
                return None
            return data
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON for {field_name}: {e}")
            print("   Make sure the JSON is properly formatted")
            print('   Example: {"key": "value", "number": 123}')
            return None

    def list_interactive(self, include_disabled: bool = False) -> None:
        """
        Interactive teammate listing.

        Args:
            include_disabled: Include disabled teammates in listing
        """
        try:
            print("👥 Your Teammates")
            print()

            # Use instances instead of agents (enabled first, then disabled if requested)
            instances = self.client.instances.list(include_disabled=include_disabled)

            if not instances:
                print("No teammates found.")
                print("💡 Create your first teammate with: m8tes mate create")
                if not include_disabled:
                    print("💡 To see disabled teammates: m8tes mate list --include-disabled")
                return

            for instance in instances:
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

                # Show run stats
                print(f"   Runs: {instance.run_count}")

                print()

        except Exception as e:
            print(f"❌ Failed to list teammates: {e}")

    def _format_timestamp(self, timestamp: str) -> str:
        """
        Format timestamp to human-readable relative time.

        Args:
            timestamp: ISO timestamp string

        Returns:
            Human-readable string like "2 hours ago"
        """
        try:
            from datetime import datetime

            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            now = datetime.now(UTC)
            diff = now - dt

            if diff.days > 0:
                if diff.days == 1:
                    return "1 day ago"
                elif diff.days < 7:
                    return f"{diff.days} days ago"
                elif diff.days < 30:
                    weeks = diff.days // 7
                    return f"{weeks} week{'s' if weeks > 1 else ''} ago"
                else:
                    months = diff.days // 30
                    return f"{months} month{'s' if months > 1 else ''} ago"

            hours = diff.seconds // 3600
            if hours > 0:
                return f"{hours} hour{'s' if hours > 1 else ''} ago"

            minutes = diff.seconds // 60
            if minutes > 0:
                return f"{minutes} min{'s' if minutes > 1 else ''} ago"

            return "just now"
        except Exception:
            # Fallback to original timestamp if parsing fails
            return timestamp

    def get_interactive(self, mate_id: str) -> None:
        """
        Interactive teammate details display.

        Args:
            mate_id: Teammate ID to retrieve
        """
        try:
            instance = self.client.instances.get(int(mate_id))

            print("🤝 Teammate Details")
            print()
            print(f"  ID: {instance.id}")
            print(f"  Name: {instance.name}")
            if instance.role:
                print(f"  Role: {instance.role}")
            if instance.agent_type:
                print(f"  Type: {instance.agent_type}")
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
            print(f"  Total Runs: {instance.run_count}")
            print(f"  Created: {instance.created_at}")

        except ValueError as e:
            print(f"❌ Invalid teammate ID: {e}")
        except Exception as e:
            print(f"❌ Failed to get teammate: {e}")

    def run_interactive(self, mate_id: str | None = None) -> None:
        """
        Interactive teammate execution.

        Args:
            mate_id: Optional teammate ID to run
        """
        if not mate_id:
            mate_id = prompt("Teammate ID: ")

        try:
            print(f"⏳ Starting teammate {mate_id}...")
            print()

            agent = self.client.get_agent(mate_id)

            # Run the teammate and stream results
            for event in agent.run():
                event_type = event.get("type", "unknown")

                if event_type == "start":
                    print("🚀 Teammate started")
                elif event_type == "thought":
                    print(f"💭 {event.get('content', '')}")
                elif event_type == "action":
                    tool = event.get("tool", "unknown")
                    action = event.get("action", "unknown")
                    print(f"⚡ Using {tool}: {action}")
                elif event_type == "result":
                    print(f"📊 {event.get('content', '')}")
                elif event_type == "complete":
                    print(f"✅ {event.get('summary', 'Teammate completed successfully')}")

        except Exception as e:
            print(f"❌ Failed to run teammate: {e}")

    def status_interactive(self, mate_id: str | None = None) -> None:
        """
        Interactive teammate status display.

        Args:
            mate_id: Optional teammate ID to show status for
        """
        if not mate_id:
            mate_id = prompt("Teammate ID: ")

        try:
            agent = self.client.get_agent(mate_id)

            print("🤝 Teammate Status")
            print()
            print(f"  ID: {agent.id}")
            print(f"  Name: {agent.name}")
            print(f"  Tools: {', '.join(agent.tools)}")
            print(f"  Instructions: {agent.instructions}")

        except Exception as e:
            print(f"❌ Failed to get teammate status: {e}")

    def task_interactive(
        self, message: str, mate_id: str, output_format: str = "verbose", debug: bool = False
    ) -> None:
        """
        Execute a one-off task with the teammate using streaming.

        Args:
            message: Task description
            mate_id: Teammate ID to use
            output_format: Display format ("verbose", "compact", or "json")
            debug: Enable debug mode with detailed logging
        """
        from .display import create_display

        try:
            # Show task header (unless json mode)
            if output_format != "json":
                print(f"🎯 Task: {message}")
                print()

            instance = self.client.instances.get(int(mate_id))

            if output_format != "json":
                print(f"🤝 Using: {instance.name} (ID: {instance.id})")
                print()

            if debug:
                print("[DEBUG] Starting task execution...")
                print()

            # Create display renderer
            display = create_display(output_format)
            display.start()

            # Stream task execution
            event_count = 0
            try:
                for event in instance.execute_task(message, stream=True, format="events"):
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
                    print("\n❌ Teammate encountered errors:")
                    for error in display.accumulator.get_errors():
                        print(f"   {error}")
                elif not has_text and not has_tool_calls and output_format != "json":
                    print("\n⚠️  Warning: Teammate produced no output")
                    if not debug:
                        print("   This may indicate a configuration or API issue.")
                        print("   Run with --debug for more details.")

                # Show run summary with results
                self._show_run_summary(instance, output_format, debug=debug)

                # Show completion (unless json mode)
                if output_format != "json":
                    print()
                    if has_errors:
                        print("❌ Task failed")
                    else:
                        print("✅ Task completed")

            except KeyboardInterrupt:
                display.finish()
                print("\n\n⏸️  Task interrupted")
                raise

        except Exception as e:
            print(f"❌ Failed to execute run: {e}")

    def chat_interactive(
        self, mate_id: str, resume_run_id: int | None = None, output_format: str = "verbose"
    ) -> None:
        """
        Start an interactive chat session with the teammate using streaming.

        Args:
            mate_id: Teammate ID to use
            resume_run_id: Optional run ID to resume (loads session_id for continuity)
            output_format: Display format ("verbose", "compact", or "json")

        Supports commands:
        - /exit or /quit - Exit chat session
        - /clear - Clear conversation history
        - /resume <run_id> - Resume from a different run
        """
        from .display import create_display

        if output_format != "json":
            print(
                "💬 Chat Mode - Type /exit to quit, /clear to reset history, "
                "/resume <run_id> to switch runs"
            )
            print()

        # Get instance and start chat session
        try:
            instance = self.client.instances.get(int(mate_id))
            chat_session = instance.start_chat_session(resume_run_id=resume_run_id)
            if output_format != "json":
                print(f"🤝 Chatting with: {instance.name} (ID: {instance.id})")
                if resume_run_id:
                    print(f"🔄 Resumed session from run {chat_session.run.id}")
                else:
                    print(f"📝 Session Run ID: {chat_session.run.id}")
                print()
        except Exception as e:
            print(f"❌ Failed to start chat: {e}")
            return

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
                        chat_session.end()
                        if output_format != "json":
                            print("\n👋 Chat session ended")
                        break

                    if message.strip() == "/clear":
                        chat_session.clear_history()
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
                            new_run_id = int(parts[1])
                            # End current session
                            chat_session.end()
                            # Start new session with the specified run_id
                            chat_session = instance.start_chat_session(resume_run_id=new_run_id)
                            if output_format != "json":
                                print(f"🔄 Resumed session from run {chat_session.run.id}")
                                print()
                        except ValueError:
                            if output_format != "json":
                                print(f"❌ Invalid run ID: {parts[1]} (must be a number)")
                        except Exception as e:
                            if output_format != "json":
                                print(f"❌ Failed to resume run: {e}")
                        continue

                    # Create display renderer
                    display = create_display(output_format)
                    display.start()

                    # Stream message response
                    try:
                        for event in chat_session.send(message, stream=True, format="events"):
                            display.on_event(event)

                        display.finish()

                        # Newline after response (unless json mode)
                        if output_format != "json":
                            print()

                    except KeyboardInterrupt:
                        display.finish()
                        if output_format != "json":
                            print("\n⏸️  Message interrupted")
                        continue

                except EOFError:
                    # Handle Ctrl+D
                    chat_session.end()
                    if output_format != "json":
                        print("\n\n👋 Chat session ended")
                    break

        except KeyboardInterrupt:
            # Handle Ctrl+C
            chat_session.end()
            if output_format != "json":
                print("\n\n👋 Chat session ended")
        except Exception as e:
            print(f"\n❌ Chat error: {e}")

    def update_interactive(self, mate_id: str) -> None:
        """
        Interactive teammate update flow.

        Args:
            mate_id: Teammate ID to update
        """
        try:
            # Get current teammate
            instance = self.client.instances.get(int(mate_id))

            print(f"🔧 Update Teammate: {instance.name} (ID: {instance.id})")
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
            new_instructions = prompt(
                "New instructions (or press Enter to keep): ", allow_empty=True
            )

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

            # Update instance
            print("⏳ Updating teammate...")
            instance.update(name=new_name, instructions=new_instructions)

            print("✅ Teammate updated successfully!")

        except Exception as e:
            print(f"❌ Failed to update teammate: {e}")

    def update_non_interactive(
        self, mate_id: str, name: str | None = None, instructions: str | None = None
    ) -> None:
        """
        Non-interactive teammate update.

        Args:
            mate_id: Teammate ID to update
            name: New name (optional)
            instructions: New instructions (optional)
        """
        try:
            # Get current teammate
            instance = self.client.instances.get(int(mate_id))

            # Update instance
            instance.update(name=name, instructions=instructions)

            print("✅ Teammate updated successfully!")
            print(f"   ID: {instance.id}")
            if name:
                print(f"   New Name: {name}")
            if instructions:
                print("   Instructions: Updated")

        except Exception as e:
            raise Exception(f"Failed to update teammate: {e}") from e

    def enable_interactive(self, mate_id: str) -> None:
        """
        Interactive teammate enable flow.

        Args:
            mate_id: Teammate ID to enable
        """
        from ..exceptions import AuthenticationError, NetworkError, ValidationError

        try:
            # Get teammate info
            instance = self.client.instances.get(int(mate_id))

            print(f"✅ Enable Teammate: {instance.name} (ID: {instance.id})")
            print()
            print(f"  Current status: {instance.status}")
            print()

            if instance.status == "enabled":
                print("⚠️  Teammate is already enabled")
                return

            # Enable instance
            print("⏳ Enabling teammate...")
            instance.enable()

            print("✅ Teammate enabled successfully!")
            print(f"   Status: {instance.status}")

        except ValueError as e:
            print(f"❌ Invalid teammate ID: {e}")
            print("   Please provide a numeric teammate ID")
        except AuthenticationError as e:
            print(f"❌ Authentication failed: {e}")
            print("   Your session may have expired. Try: m8tes auth login")
        except ValidationError as e:
            print(f"❌ Failed to enable teammate: {e}")
        except NetworkError as e:
            print(f"❌ Network error: {e}")
            print("   Check your connection and try again")
        except Exception as e:
            print(f"❌ Unexpected error occurred: {e}")

    def disable_interactive(self, mate_id: str, force: bool = False) -> None:
        """
        Interactive teammate disable flow.

        Args:
            mate_id: Teammate ID to disable
            force: Skip confirmation prompt
        """
        from ..exceptions import AuthenticationError, NetworkError, ValidationError

        try:
            # Get teammate info
            instance = self.client.instances.get(int(mate_id))

            print(f"⏸️  Disable Teammate: {instance.name} (ID: {instance.id})")
            print()
            print(f"  Run count: {instance.run_count}")
            print(f"  Status: {instance.status}")
            print()

            if instance.status == "disabled":
                print("⚠️  Teammate is already disabled")
                return

            # Confirm action
            if not force:
                print("⚠️  This will disable the teammate (soft disable).")
                print("   • Teammate will be marked as disabled")
                print("   • Still visible with --include-disabled flag")
                print("   • Run history will be preserved")
                print("   • Teammate can be re-enabled anytime")
                print()
                if not confirm_prompt("Disable this teammate?", default=False):
                    print("❌ Operation cancelled")
                    return

            # Disable instance
            print("⏳ Disabling teammate...")
            instance.disable()

            print("✅ Teammate disabled successfully!")
            print(f"   Status: {instance.status}")
            print("   Run history has been preserved.")
            print(f"💡 To re-enable: m8tes mate enable {instance.id}")

        except ValueError as e:
            print(f"❌ Invalid teammate ID: {e}")
            print("   Please provide a numeric teammate ID")
        except AuthenticationError as e:
            print(f"❌ Authentication failed: {e}")
            print("   Your session may have expired. Try: m8tes auth login")
        except ValidationError as e:
            print(f"❌ Failed to disable teammate: {e}")
        except NetworkError as e:
            print(f"❌ Network error: {e}")
            print("   Check your connection and try again")
        except Exception as e:
            print(f"❌ Unexpected error occurred: {e}")

    def archive_interactive(self, mate_id: str, force: bool = False) -> None:
        """
        Interactive teammate archiving flow.

        Args:
            mate_id: Teammate ID to archive
            force: Skip confirmation prompt
        """
        from ..exceptions import AuthenticationError, NetworkError, ValidationError

        try:
            # Get teammate info
            instance = self.client.instances.get(int(mate_id))

            print(f"🗑️  Archive Teammate: {instance.name} (ID: {instance.id})")
            print()
            print(f"  Run count: {instance.run_count}")
            print(f"  Status: {instance.status}")
            print()

            # Confirm archiving
            if not force:
                print("⚠️  This will archive the teammate (hidden from listings).")
                print("   • Teammate will be archived and hidden from listings")
                print("   • Run history will be preserved")
                print("   • Use disable instead if you want to keep it visible")
                print()
                if not confirm_prompt("Archive this teammate?", default=False):
                    print("❌ Operation cancelled")
                    return

            # Archive instance
            print("⏳ Archiving teammate...")
            success = instance.archive()

            if success:
                print("✅ Teammate archived successfully!")
                print("   Run history has been preserved.")
            else:
                print("❌ Failed to archive teammate: Operation returned false")

        except ValueError as e:
            print(f"❌ Invalid teammate ID: {e}")
            print("   Please provide a numeric teammate ID")
        except AuthenticationError as e:
            print(f"❌ Authentication failed: {e}")
            print("   Your session may have expired. Try: m8tes auth login")
        except ValidationError as e:
            error_msg = str(e)
            if "not found" in error_msg.lower():
                print(f"❌ Teammate not found: No teammate with ID {mate_id}")
                print("   Use 'm8tes mate list' to see available teammates")
            elif "access denied" in error_msg.lower():
                print(
                    f"❌ Access denied: Teammate {mate_id} belongs to another user "
                    "or was already archived"
                )
                print("   You can only archive teammates that you own")
                print("   Use 'm8tes mate list' to see your teammates")
            elif "403" in error_msg or "forbidden" in error_msg.lower():
                print("❌ Access denied: You don't have permission to archive this teammate")
            else:
                print(f"❌ Failed to archive teammate: {error_msg}")
        except NetworkError as e:
            print(f"❌ Network error: {e}")
            print("   Check your connection and try again")
        except Exception as e:
            print(f"❌ Unexpected error occurred: {e}")
            print("If the problem persists:")
            print("  • Use: m8tes --help")
            print("  • Contact support if needed")

    def _show_run_summary(
        self, instance, output_format: str = "verbose", debug: bool = False
    ) -> None:
        """
        Display run summary with results and details.

        Args:
            instance: Teammate instance that was executed
            output_format: Output format ("verbose", "compact", or "json")
            debug: Enable debug output
        """
        # Skip summary in JSON mode (raw events only)
        if output_format == "json":
            return

        try:
            # Get the run object stored during execute_task
            run = getattr(instance, "_current_run", None)
            if not run:
                if debug:
                    print("\n[DEBUG] No run object found on instance")
                return

            if debug:
                print(f"\n[DEBUG] Fetching details for run ID: {run.id}")

            # Fetch comprehensive run details
            conversation_error = None
            try:
                details = run.get_details()
            except Exception as e:
                conversation_error = str(e)
                if debug:
                    print(f"[DEBUG] get_details() failed: {e}")
                    print("[DEBUG] Falling back to individual calls")
                # Fallback to individual calls if get_details fails
                try:
                    messages = run.get_conversation()
                except Exception as conv_err:
                    messages = []
                    conversation_error = str(conv_err)
                    if debug:
                        print(f"[DEBUG] get_conversation() failed: {conv_err}")

                details = {
                    "conversation": {"messages": messages},
                    "tool_executions": {"executions": run.get_tool_executions()},
                    "usage": run.get_usage(),
                }

            # Extract data
            messages = details.get("conversation", {}).get("messages", [])
            tool_executions = details.get("tool_executions", {}).get("executions", [])
            usage = details.get("usage", {})

            # Get final teammate response from conversation
            final_response = None
            for msg in reversed(messages):
                if msg.get("role") == "assistant":
                    final_response = msg.get("content", "")
                    break

            # Display summary based on format
            if output_format == "compact":
                # Compact: just show final response or error message
                if final_response:
                    print(f"\n{final_response}")
                elif conversation_error and "404" in conversation_error:
                    print("\n⚠️  No conversation data (teammate may have failed)")
            else:
                # Verbose: full summary
                print()
                print("=" * 60)
                print("📊 Run Summary")
                print("=" * 60)

                # Show warning if no conversation data
                if not messages and conversation_error:
                    print("\n⚠️  No conversation data available")
                    if "404" in conversation_error:
                        print("   The teammate execution may have failed before generating output.")
                        if debug:
                            print(f"   Error: {conversation_error}")
                        else:
                            print("   Run with --debug for more details.")
                    else:
                        print(f"   Error: {conversation_error}")

                # Final response
                if final_response:
                    print("\n🤝 Teammate Response:")
                    print(f"{final_response}")

                # Tool executions
                if tool_executions:
                    print(f"\n⚡ Tools Used: {len(tool_executions)}")
                    for tool_exec in tool_executions:
                        tool_name = tool_exec.get("tool_name", "unknown")
                        success = tool_exec.get("success", False)
                        status = "✅" if success else "❌"
                        print(f"   {status} {tool_name}")

                # Usage stats
                if usage:
                    total_tokens = usage.get("total_tokens", 0)
                    total_cost = usage.get("total_cost", 0)
                    duration = usage.get("duration_seconds", 0)

                    print("\n💰 Usage:")
                    if total_tokens:
                        print(f"   Tokens: {total_tokens:,}")
                    if total_cost:
                        print(f"   Cost: ${total_cost:.4f}")
                    if duration:
                        print(f"   Duration: {duration:.2f}s")

                print("\n" + "=" * 60)

        except Exception as e:
            # Don't fail the whole task if summary fails
            if output_format == "verbose":
                print(f"\n⚠️  Could not fetch run summary: {e}")
                if debug:
                    import traceback

                    print("\n[DEBUG] Full traceback:")
                    traceback.print_exc()

    def _show_mate_usage_guide(self, instance, mode: str | None = None) -> None:
        """
        Show comprehensive usage guide after teammate creation.

        Args:
            instance: Created teammate instance
            mode: Optional mode hint ('task', 'chat', or None for both)
        """
        print("\n" + "=" * 60)
        print("🎉 Teammate Ready!")
        print("=" * 60)

        print("\n📋 Teammate Details:")
        print(f"   ID: {instance.id}")
        print(f"   Name: {instance.name}")
        role_value = getattr(instance, "role", None)
        if role_value:
            print(f"   Role: {role_value}")
        if hasattr(instance, "tools") and instance.tools:
            print(f"   Tools: {', '.join(instance.tools)}")
        goals_value = getattr(instance, "goals", None)
        if goals_value:
            print("   Goals:")
            for line in goals_value.splitlines():
                print(f"      {line}")

        print("\n🚀 How to Use Your Teammate:")

        # Task mode examples
        if mode != "chat":
            print("\n1️⃣  Run a one-off task:")
            print(f'   m8tes mate task {instance.id} "Your task here"')

            # Show tool-specific examples if Google Ads tools are available
            if hasattr(instance, "tools") and any(
                "google_ads" in tool.lower() or "gaql" in tool.lower() for tool in instance.tools
            ):
                print("\n   💡 Google Ads Example:")
                print(f'   m8tes mate task {instance.id} "What\'s my daily Google Ads spend?"')

        # Chat mode examples
        if mode != "task":
            print("\n2️⃣  Start an interactive chat session:")
            print(f"   m8tes mate chat {instance.id}")

        # General commands
        print("\n📊 Other Commands:")
        print("   m8tes mate list         # View all your teammates")
        print(f"   m8tes mate get {instance.id}     # Get teammate details")
        print(f"   m8tes mate update {instance.id}  # Update teammate configuration")

        print("\n📚 Need Help?")
        print("   m8tes mate --help")
        print()
