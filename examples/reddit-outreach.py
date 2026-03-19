"""
Reddit outreach agent — finds fresh posts relevant to your target audience,
leaves genuine helpful comments, and logs each interaction to Google Sheets.

Demonstrates: teammates, tools, non-streaming runs.

Usage:
    export M8TES_API_KEY=m8_...
    python reddit-outreach.py
"""

from m8tes import M8tes

client = M8tes()

# ── configure these for your use case ───────────────────────────────────────
SPREADSHEET_ID = "your-google-sheets-spreadsheet-id"
TARGET_AUDIENCE = "describe who you're trying to reach and what problems they have"
# ────────────────────────────────────────────────────────────────────────────

teammate = client.teammates.create(
    name="reddit-outreach",
    instructions=(
        "You find fresh Reddit posts, leave genuine helpful comments, "
        "and log every interaction to a Google Sheet for tracking. "
        "\n\n"
        "FIRST: check that Reddit and Google Sheets integrations are configured. "
        "If either says 'not configured', stop immediately and report which ones are missing. "
        "\n\n"
        f"Target audience: {TARGET_AUDIENCE}. "
        "Search Reddit across multiple relevant subreddits — not just the obvious ones. "
        "Only consider posts from the last 12 hours. "
        "Good signals: someone asking for help, frustrated with a manual process, "
        "looking for a tool or workflow, or describing a pain point you can address. "
        "\n\n"
        "Comment style: short, helpful, human. Lead with genuine advice. "
        "Vary your tone. Keep it casual — don't capitalize everything, it looks robotic. "
        "No lists or structured formatting — just write naturally. "
        "If you have a relevant product or tool to mention, bring it up softly "
        "as personal experience, not a recommendation. Skip any post that isn't a real fit. "
        "\n\n"
        f"After each comment, log a row to Google Sheets (ID: {SPREADSHEET_ID}): "
        "Date | Subreddit | Post Title | Post URL | Comment Text | Status | Notes. "
        "Aim for 10 comments total."
    ),
    tools=["reddit", "google-sheets"],
)

print(f"teammate: {teammate.id}")
print()
print("Running outreach session...")

run = client.runs.create_and_wait(
    teammate_id=teammate.id,
    message="Start the outreach session. Find relevant posts from the last 12 hours and comment.",
)
print(run.output)
