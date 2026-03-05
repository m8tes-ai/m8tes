"""
SEO monitoring agent — checks Google Search Console weekly for indexing issues,
coverage errors, and ranking opportunities. Posts a priority-flagged summary to Slack.

Demonstrates: teammates, scheduled triggers, non-streaming runs.

Usage:
    export M8TES_API_KEY=m8_...
    python seo-monitor.py
"""

from m8tes import M8tes

client = M8tes()

teammate = client.teammates.create(
    name="seo-monitor",
    instructions=(
        "You are an SEO specialist. Every week: "
        "1. Check Google Search Console for new indexing errors or coverage issues — "
        "flag any URLs blocked by robots, not found, or server errors. "
        "2. Find pages with high impressions but low CTR (>500 impressions, <2% CTR) — "
        "these are quick-win optimization opportunities. "
        "3. Submit any new URLs published in the last 7 days for indexing. "
        "4. Post a concise summary to #marketing on Slack with: issues found, "
        "opportunities flagged, and URLs submitted. Use priority labels (urgent / info)."
    ),
    tools=["google-search-console", "slack"],
)

# schedule — every Monday at 7am ET (before the team starts work)
task = client.tasks.create(teammate_id=teammate.id)
trigger = client.tasks.triggers.create(
    task.id,
    type="schedule",
    cron="0 7 * * 1",
    timezone="America/New_York",
)

print(f"teammate: {teammate.id}")
print(f"task:     {task.id}")
print(f"trigger:  {trigger.id} (runs every Monday at 7am ET)")
print()
print("Running SEO check now (non-streaming)...")

run = client.runs.create_and_wait(
    teammate_id=teammate.id,
    message="Run the weekly SEO check now.",
)
print(run.output)
