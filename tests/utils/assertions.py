"""Custom assertion helpers for m8tes SDK tests."""

from typing import Any


def assert_dict_contains_keys(data: dict[str, Any], keys: list[str]) -> None:
    """Assert that a dictionary contains all specified keys."""
    missing_keys = [key for key in keys if key not in data]
    if missing_keys:
        raise AssertionError(f"Dictionary missing keys: {missing_keys}")


def assert_dict_subset(subset: dict[str, Any], superset: dict[str, Any]) -> None:
    """Assert that one dictionary is a subset of another."""
    for key, value in subset.items():
        if key not in superset:
            raise AssertionError(f"Key '{key}' not found in superset")
        if superset[key] != value:
            raise AssertionError(
                f"Value mismatch for key '{key}': expected {value}, got {superset[key]}"
            )


def assert_valid_agent_id(agent_id: str) -> None:
    """Assert that an agent ID has valid format."""
    if not isinstance(agent_id, str):
        raise AssertionError(f"Agent ID must be string, got {type(agent_id)}")
    if not agent_id:
        raise AssertionError("Agent ID cannot be empty")
    if len(agent_id) < 5:
        raise AssertionError(f"Agent ID too short: {agent_id}")


def assert_valid_tools_list(tools: list[str]) -> None:
    """Assert that tools list is valid."""
    if not isinstance(tools, list):
        raise AssertionError(f"Tools must be a list, got {type(tools)}")

    valid_tools = [
        "google_ads_search",
        "google_ads_negatives",
        "google_ads_performance",
        "facebook_ads_insights",
    ]  # Extend as registry grows
    for tool in tools:
        if not isinstance(tool, str):
            raise AssertionError(f"Tool name must be string, got {type(tool)}")
        if tool not in valid_tools:
            raise AssertionError(f"Unknown tool: {tool}")


def assert_valid_instructions(instructions: str) -> None:
    """Assert that instructions are valid."""
    if not isinstance(instructions, str):
        raise AssertionError(f"Instructions must be string, got {type(instructions)}")
    if not instructions.strip():
        raise AssertionError("Instructions cannot be empty")
    if len(instructions) > 10000:  # Reasonable limit
        raise AssertionError(f"Instructions too long: {len(instructions)} characters")


def assert_valid_schedule(schedule: str | None) -> None:
    """Assert that schedule format is valid."""
    if schedule is None:
        return

    if not isinstance(schedule, str):
        raise AssertionError(f"Schedule must be string, got {type(schedule)}")

    valid_simple_schedules = ["hourly", "daily", "weekly", "monthly"]

    # Check if it's a simple schedule
    if schedule in valid_simple_schedules:
        return

    # Check if it might be cron format (basic validation)
    if " " in schedule:
        parts = schedule.split()
        if len(parts) == 5:  # Basic cron format check
            return

    raise AssertionError(f"Invalid schedule format: {schedule}")


def assert_valid_deployment_status(status: str) -> None:
    """Assert that deployment status is valid."""
    valid_statuses = ["active", "inactive", "error"]
    if status not in valid_statuses:
        raise AssertionError(f"Invalid deployment status: {status}")


def assert_event_structure(event: dict[str, Any], required_fields: list[str] | None = None) -> None:
    """Assert that an event has proper structure."""
    if not isinstance(event, dict):
        raise AssertionError(f"Event must be a dictionary, got {type(event)}")

    if "type" not in event:
        raise AssertionError("Event missing required 'type' field")

    if "timestamp" not in event:
        raise AssertionError("Event missing required 'timestamp' field")

    if required_fields:
        assert_dict_contains_keys(event, required_fields)
