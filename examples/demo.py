"""
m8tes demo: create a teammate, schedule it, give it an email inbox, run it live.

Shows the full setup in one script: teammate creation, scheduling, email trigger,
and a live streaming run. Run this once and the agent is deployed.

Usage:
    export M8TES_API_KEY=m8_...
    python demo.py
"""

from m8tes import M8tes, PermissionMode

client = M8tes()

# 1. create a teammate with an email inbox
teammate = client.teammates.create(
    name="ops assistant",
    tools=["stripe", "linear", "slack"],
    instructions=(
        "pull last week's metrics from Stripe and Linear, "
        "write a short bullet-point summary, "
        "and post it to #ops on Slack"
    ),
    email_inbox=True,
)
print(f"teammate: {teammate.id}")
print(f"inbox:    {teammate.email_address}  # forward anything here to trigger a run")

# 2. schedule it: every Monday at 9am ET
task = client.tasks.create(
    teammate_id=teammate.id,
    instructions="run the weekly ops summary",
    schedule="0 9 * * 1",
    schedule_timezone="America/New_York",
)
print(f"task:     {task.id}  # runs every Monday at 9am ET")
print()
print("streaming a test run now...")
print("-" * 48)

# 3. run it now: autonomous (no approval prompts), streams live output
with client.runs.create(
    teammate_id=teammate.id,
    message="run the ops summary now",
    permission_mode=PermissionMode.AUTONOMOUS,
) as stream:
    for chunk in stream.iter_text():
        print(chunk, end="", flush=True)

print(f"\n\nrun {stream.run_id} complete")
