"""
Support triage agent — classifies inbound support emails, creates Linear tickets
for bugs, and escalates urgent issues to Slack. Runs every weekday at 8am.

Demonstrates: teammates, tasks, scheduled triggers, real-time streaming.

Usage:
    export M8TES_API_KEY=m8_...
    python support-triage.py
"""

from m8tes import M8tes

client = M8tes()

# create the teammate once
teammate = client.teammates.create(
    name="support-triage",
    instructions=(
        "Triage inbound support emails. "
        "For bug reports: create a Linear ticket with steps to reproduce. "
        "For urgent issues (down, broken, data loss): create the ticket AND "
        "post a summary to #support-escalations on Slack immediately. "
        "For general questions: draft a helpful reply and save it as a draft. "
        "Mark each email as processed after handling."
    ),
    tools=["gmail", "linear", "slack"],
)

# schedule — every weekday at 8am ET
task = client.tasks.create(teammate_id=teammate.id)
trigger = client.tasks.triggers.create(
    task.id,
    type="schedule",
    cron="0 8 * * 1-5",
    timezone="America/New_York",
)

print(f"teammate: {teammate.id}")
print(f"task:     {task.id}")
print(f"trigger:  {trigger.id} (runs weekdays at 8am ET)")
print()
print("Streaming a test run now...")
print("-" * 40)

# stream a test run to see it work in real time
for event in client.runs.create(
    teammate_id=teammate.id,
    message="Process all unread support emails from the last 24 hours.",
):
    match event.type:
        case "text-delta":
            print(event.delta, end="", flush=True)
        case "tool-call-start":
            print(f"\n  → {event.tool_name}", flush=True)
        case "done":
            print(f"\n\nstop reason: {event.stop_reason}")
