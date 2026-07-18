"""
Revenue reporting agent — pulls weekly MRR from Stripe, compares to the prior week,
posts a delta summary to #finance on Slack.

Runs every Monday at 9am. Demonstrates: agents, tasks, scheduled triggers.

Usage:
    export M8TES_API_KEY=m8_...
    python revenue-report.py
"""

from m8tes import M8tes

client = M8tes()

# create a reusable agent
agent = client.agents.create(
    name="revenue-report",
    instructions=(
        "You are a finance ops assistant. "
        "Pull last week's Stripe charges, compare to the prior week, "
        "and post a concise summary to #finance on Slack. "
        "Include: total MRR, week-over-week change, and any notable anomalies. "
        "Be precise with numbers. Use bullet points."
    ),
    tools=["stripe", "slack"],
)

# create a task and schedule it — every Monday at 9am ET
task = client.tasks.create(
    agent_id=agent.id,
    instructions="run the weekly revenue report and post the delta to #finance on slack",
)
trigger = client.tasks.triggers.create(
    task.id,
    type="schedule",
    cron="0 9 * * 1",
    timezone="America/New_York",
)

print(f"agent: {agent.id}")
print(f"task:     {task.id}")
print(f"trigger:  {trigger.id} (runs every Monday at 9am ET)")
print()
print("Running once now to verify setup...")

# run it once immediately to verify everything is connected
run = client.runs.create_and_wait(
    agent_id=agent.id,
    message="Run the weekly revenue report now.",
)
print(run.output)
