"""
Multi-tenant customer agent — gives each end-user their own AI assistant with
isolated memory, tools, and permissions. Demonstrates per-user isolation via user_id.

Use this pattern when embedding AI agents in your own product.

Usage:
    export M8TES_API_KEY=m8_...
    python customer-agent.py
"""

from m8tes import M8tes

client = M8tes()

# ── 1. Create user profiles ────────────────────────────────────────────────────

client.users.create(user_id="acme-corp", name="Acme Corp", email="admin@acme.com")
client.users.create(user_id="globex-inc", name="Globex Inc", email="ops@globex.com")

# ── 2. Seed each user's memory (context that persists across runs) ─────────────

client.memories.create(user_id="acme-corp", content="uses Slack channel #acme-ops for alerts")
client.memories.create(user_id="acme-corp", content="primary CRM is HubSpot, deal stage is 'Closed Won'")

client.memories.create(user_id="globex-inc", content="uses email for all notifications, not Slack")
client.memories.create(user_id="globex-inc", content="operates in UTC, weekly reports due Friday")

# ── 3. Create a shared teammate ────────────────────────────────────────────────
# one teammate definition, used by all users — each run is fully isolated

assistant = client.teammates.create(
    name="ops-assistant",
    instructions=(
        "You are an operations assistant. Help the user with reporting, "
        "monitoring, and task automation. Use their memory context to tailor "
        "your responses and output format to their preferences."
    ),
    tools=["gmail", "slack", "hubspot", "google-sheets"],
)

# ── 4. Run on behalf of each user — memory, history, tools all scoped ─────────

print("Running for acme-corp...")
acme_run = client.runs.create_and_wait(
    teammate_id=assistant.id,
    message="Summarize this week's closed deals and send a recap to the team.",
    user_id="acme-corp",  # all memory and history scoped to this user
)
print(f"acme-corp: {acme_run.output[:200]}...")

print()
print("Running for globex-inc...")
globex_run = client.runs.create_and_wait(
    teammate_id=assistant.id,
    message="Summarize this week's closed deals and send a recap to the team.",
    user_id="globex-inc",  # completely isolated — no data bleeds between users
)
print(f"globex-inc: {globex_run.output[:200]}...")

# ── 5. List runs per user ──────────────────────────────────────────────────────

acme_runs = client.runs.list(user_id="acme-corp")
print(f"\nacme-corp run count: {len(acme_runs.data)}")
