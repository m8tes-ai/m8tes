"""
File report — generate, stream progress, and download files produced by a run.

Use this pattern when your agent needs to write CSV exports, markdown summaries,
JSON data files, or any other text-based output that you want to retrieve after
the run completes.

Usage:
    export M8TES_API_KEY=m8_...
    python file-report.py
"""

from m8tes import M8tes

client = M8tes()

# ── Create a teammate that generates reports ───────────────────────────────────

reporter = client.teammates.create(
    name="weekly reporter",
    tools=["stripe", "google-sheets", "gmail"],
    instructions=(
        "Generate weekly reports. Write a markdown summary to weekly_report.md "
        "and a CSV of raw data to weekly_data.csv. "
        "Email the summary to the team when asked."
    ),
)

# ── Option A: Stream progress and watch for file writes ───────────────────────
# Use tool-call-start events to see exactly when each file is written.

print("── Streaming run with file tracking ──────────────────────────────────────")

files_written: list[str] = []
run_id: int | None = None

with client.runs.create(
    teammate_id=reporter.id,
    message=(
        "Pull last week's metrics from Stripe. "
        "Write weekly_report.md with an executive summary "
        "and weekly_data.csv with the raw revenue data."
    ),
) as stream:
    for event in stream:
        if event.type == "text-delta":
            print(event.delta, end="", flush=True)
        elif event.type == "tool-call-start" and event.tool_name == "Write":
            filename = (event.tool_input or {}).get("file_path", "").split("/")[-1]
            if filename:
                print(f"\n  writing {filename}...")
                files_written.append(filename)
        elif event.type == "done":
            run_id = stream.run_id

print(f"\n\nFiles written during run: {files_written}")

# ── Download generated files ───────────────────────────────────────────────────

if run_id:
    for f in client.runs.list_files(run_id):
        content = client.runs.download_file(run_id, f.name)
        with open(f.name, "wb") as fh:
            fh.write(content)
        print(f"saved {f.name} ({f.size} bytes)")

# ── Option B: Non-streaming with poll, then download ─────────────────────────
# Simpler for batch jobs where you don't need progress feedback.

print("\n\n── Non-streaming run ─────────────────────────────────────────────────────")

run = client.runs.create_and_wait(
    teammate_id=reporter.id,
    message="Export all VIP customers to vip_customers.json.",
    stream=False,  # don't need progress output
)

for f in client.runs.list_files(run.id):
    content = client.runs.download_file(run.id, f.name)
    with open(f.name, "wb") as fh:
        fh.write(content)
    print(f"saved {f.name} ({f.size} bytes)")

# ── Option C: Recurring scheduled report ─────────────────────────────────────
# Combine file generation with scheduling for reports that run automatically.

print("\n\n── Scheduled weekly report ────────────────────────────────────────────────")

task = client.tasks.create(
    teammate_id=reporter.id,
    instructions=(
        "Pull last week's key metrics from Stripe and Google Sheets. "
        "Write weekly_report.md and weekly_data.csv. "
        "Email weekly_report.md to team@acme.com."
    ),
)

client.tasks.triggers.create(
    task.id,
    type="schedule",
    cron="0 9 * * 1",  # every Monday at 9am
    timezone="America/New_York",
)

# Run once to verify everything works before the schedule kicks in
run = client.tasks.run_and_wait(task.id)

for f in client.runs.list_files(run.id):
    print(f"  {f.name} ({f.size} bytes)")

print(f"\nScheduled. Task ID: {task.id} — runs every Monday at 9am ET.")
print(f"Done: {run.output[:200]}...")
