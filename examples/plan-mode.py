"""
Plan mode — agent proposes what it will do before executing.

Use this pattern when you want to review and approve the agent's approach
before it takes any actions. Good for high-stakes workflows where surprises
are expensive (sending emails, updating records, making API calls).

Usage:
    export M8TES_API_KEY=m8_...
    python plan-mode.py
"""

from m8tes import M8tes, PermissionMode, PermissionRequest

client = M8tes()

# ── Create a teammate with write-access tools ──────────────────────────────────

agent = client.teammates.create(
    name="ops agent",
    tools=["gmail", "linear", "slack"],
    instructions="You are an operations assistant. Before taking any actions, "
    "present a clear plan explaining what you will do and why.",
)

# ── Option A: Interactive approval in a terminal ───────────────────────────────
# Use req.is_plan_approval and req.plan_text to detect and display the plan.


def handle_question(req: PermissionRequest) -> dict:
    if req.is_plan_approval:
        print("\n── Proposed Plan ──────────────────────────────────────────────")
        print(req.plan_text)
        print("───────────────────────────────────────────────────────────────")
        choice = input("Approve? [y/n/r]: ").strip().lower()
        if choice == "y":
            return {"Plan Approval": "Approve"}
        elif choice == "r":
            revision = input("Describe what to change: ")
            return {"Plan Approval": f"Revise: {revision}"}
        else:
            return {"Plan Approval": "Revise"}
    # Generic question — print options and let the user choose
    for q in req.tool_input.get("questions", []):
        options = [o["label"] for o in q.get("options", [])]
        print(f"\n{q['question']} [{'/'.join(options)}]: ", end="")
        return {q["question"]: input().strip()}
    return {}


def handle_approval(req: PermissionRequest) -> str:
    # After plan approval, auto-allow any remaining tool calls
    print(f"  → {req.tool_name}")
    return "allow"


run = client.runs.create(
    teammate_id=agent.id,
    message="Process unread support emails: create Linear tickets for bugs, "
    "post urgent issues to #ops in Slack.",
    human_in_the_loop=True,
    permission_mode=PermissionMode.PLAN,
    stream=False,
)

run = client.runs.wait(run.id, on_question=handle_question, on_approval=handle_approval)
print(f"\nDone: {run.output[:300]}...")

# ── Option B: Fully automated (auto-approve the plan) ─────────────────────────
# Use this in scripts where you just want to log the plan but not pause.

print("\n\n── Automated run (auto-approve plan) ─────────────────────────────")

automated_run = client.runs.create_and_wait(
    teammate_id=agent.id,
    message="Check for any new Linear tickets assigned to me and post a summary to Slack.",
    human_in_the_loop=True,
    permission_mode=PermissionMode.PLAN,
    on_question=lambda req: {"Plan Approval": "Approve"} if req.is_plan_approval else {},
    on_approval=lambda req: "allow",
)
print(automated_run.output)
