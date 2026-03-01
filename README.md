# m8tes Python SDK

[![PyPI](https://img.shields.io/pypi/v/m8tes.svg)](https://pypi.org/project/m8tes/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Deploy AI agents to production in minutes. Hosted runtime, 150+ integrations, schedules, webhooks, and human-in-the-loop. All out of the box.

## Install

```bash
pip install m8tes
```

## Quick start

Create a teammate, schedule it, give it an email inbox. Run it live in one script.

```python
from m8tes import M8tes

client = M8tes()  # uses M8TES_API_KEY env var

# create a teammate with an email inbox
teammate = client.teammates.create(
    name="ops assistant",
    tools=["stripe", "linear", "slack"],
    instructions="pull last week's metrics, write a short summary, post to #ops on Slack",
    email_inbox=True,
)
print(f"inbox: {teammate.email_address}")  # forward anything here to trigger a run

# schedule it: every Monday at 9am ET
task = client.tasks.create(
    teammate_id=teammate.id,
    instructions="run the weekly ops summary",
    schedule="0 9 * * 1",
    schedule_timezone="America/New_York",
)

# run it now: autonomous, streams live output
with client.runs.create(
    teammate_id=teammate.id,
    message="run the ops summary now",
    permission_mode="autonomous",
) as stream:
    for chunk in stream.iter_text():
        print(chunk, end="", flush=True)

print(stream.run_id)
```

## What you get out of the box

Everything you'd otherwise spend weeks building:

- **Hosted sandboxed runtime.** Every run executes in an isolated environment. No servers to manage.
- **150+ managed integrations.** Gmail, Slack, Notion, HubSpot, Stripe, Linear, Google Ads. OAuth handled for you.
- **Scheduled runs, webhooks, and email triggers.** Every agent gets its own @m8tes.ai inbox.
- **Persistent memory.** Builds context across runs, scoped per end-user.
- **Permission modes.** Autonomous, approval-required, or plan-then-execute.
- **Per-user isolation.** Set `user_id` on any run. Memory and tools are strictly scoped.
- **Real-time streaming.** SSE events for text output, tool calls, files, and completion.
- **File handling.** Agents generate reports and spreadsheets, downloadable through the API.

[Free to start. No credit card required.](https://m8tes.ai/signup)

## Use cases

**Revenue reporting.** Pull MRR from Stripe, update the tracking sheet, post weekly delta to Slack.

**Support triage.** Classify inbound tickets, draft replies, escalate blockers. Runs 24/7 on a schedule.

**Ad spend monitoring.** Check Google Ads weekly, pause low-converting campaigns, alert the team.

**Customer-facing agents.** Give each user their own agent with isolated memory, tools, and permissions.

## Why not LangChain or CrewAI

LangChain and CrewAI are frameworks for orchestrating LLM calls locally. You still need to build the execution environment, OAuth flows, scheduling, memory, and approval gates yourself.

m8tes is the hosted infrastructure layer: sandboxed execution, managed OAuth for 150+ apps, scheduling, human-in-the-loop, and persistent memory built in. You write the logic. We run it.

## Runs

### Streaming (default)

```python
for event in client.runs.create(
    message="pull MRR from Stripe, compare to last month, post the delta to #revenue",
    tools=["stripe", "slack"],
):
    match event.type:
        case "text-delta":      print(event.delta, end="")
        case "tool-call-start": print(f"\n  {event.tool_name}")
        case "tool-result-end": print(f"  > {event.result[:100]}")
        case "done":            print(f"\n  {event.stop_reason}")
```

### Non-streaming

```python
run = client.runs.create(message="generate quarterly report", stream=False)
result = client.runs.poll(run.id)  # blocks until complete
print(result.output)

# or use the convenience wrapper
result = client.runs.create_and_wait(message="generate quarterly report")
```

### Context manager

```python
with client.runs.create(message="summarize inbox") as stream:
    for event in stream:
        print(event.type)
print(stream.text)  # full accumulated text
```

### Reply to a run

```python
for event in client.runs.reply(run.id, message="also break it down by region"):
    print(event.type, event.raw)

# or block until complete
result = client.runs.reply_and_wait(run.id, message="also break it down by region")
```

### Stream text only

```python
for chunk in client.runs.stream_text(message="summarize inbox"):
    print(chunk, end="")
```

Need the run ID or accumulated text after? Use `iter_text()` instead:

```python
with client.runs.create(message="summarize inbox") as stream:
    for chunk in stream.iter_text():
        print(chunk, end="", flush=True)
print(stream.run_id, stream.text)
```

## Human-in-the-loop

Pass callbacks to `wait()` — approval pauses are handled inline:

```python
run = client.runs.create(
    message="draft and send the weekly report",
    human_in_the_loop=True,
    permission_mode="approval",  # or "plan", "autonomous"
    stream=False,
)
run = client.runs.wait(
    run.id,
    on_approval=lambda req: "allow",
    on_question=lambda req: {"Which channel?": "#general"},
)
print(run.output)
```

Or create and wait in a single call:

```python
run = client.runs.create_and_wait(
    message="draft and send the weekly report",
    human_in_the_loop=True,
    permission_mode="approval",
    on_approval=lambda req: "allow",
)
```

### Low-level control

```python
pending = client.runs.permissions(run.id)
client.runs.approve(run.id, request_id="req_123", decision="allow")
client.runs.answer(run.id, answers={"Which channel?": "#general"})
```

### Switch permission mode on an existing run

```python
run = client.runs.create(
    teammate_id=bot.id,
    message="prepare the weekly update",
    stream=False,
)

run = client.runs.update_permission_mode(run.id, permission_mode="approval")
print(run.permission_mode)  # "approval"
```

## Triggers

```python
# schedule -- every weekday at 9am (shortcut on tasks.create, no separate call needed)
task = client.tasks.create(teammate_id=..., instructions="...", schedule="0 9 * * 1-5")

# webhook -- POST to a URL to trigger runs
task = client.tasks.create(teammate_id=..., instructions="...", webhook=True)
print(task.webhook_url)  # POST here to trigger (shown once)

# email -- give the teammate an inbox at creation time
mate = client.teammates.create(name="inbox bot", email_inbox=True)
print(mate.email_address)  # forward emails here

# on demand -- run a saved task directly
for event in client.tasks.run(task.id):
    print(event.type, event.raw)
```

## Multi-tenancy

Give each user their own AI agent with isolated memory, tools, and permissions.

```python
# create a user profile
client.users.create(user_id="cust_123", name="Acme Corp", email="admin@acme.com")

# give them their own teammate
bot = client.teammates.create(
    name="acme assistant",
    tools=["gmail", "slack"],
    user_id="cust_123",
)

# seed their memory
client.memories.create(user_id="cust_123", content="prefers email over slack")

# pre-approve tools
client.permissions.create(user_id="cust_123", tool="gmail")

# run on their behalf -- memory, permissions, history all scoped
run = client.runs.create_and_wait(
    teammate_id=bot.id,
    message="check inbox for urgent items",
    user_id="cust_123",
)
```

## Apps & Connections

Inspect the app catalog first, then use the explicit helper that matches the app's auth type.

```python
apps = client.apps.list(user_id="cust_123")
for app in apps.data:
    print(app.name, app.auth_type, app.connected)

# OAuth app
start = client.apps.connect_oauth(
    "gmail",
    redirect_uri="https://app.example.com/oauth/callback",
    user_id="cust_123",
)
print(start.authorization_url)

# after your redirect handler gets the callback
client.apps.connect_complete("gmail", start.connection_id, user_id="cust_123")

# API key app
client.apps.connect_api_key("gemini", api_key="sk_live_...", user_id="cust_123")
client.apps.disconnect("gemini", user_id="cust_123")
```

Prefer `connect_oauth()` or `connect_api_key()` when you already know the auth flow. `client.apps.connect()` is still available if you want one polymorphic entry point.

## Resources

| Resource | Key methods | Description |
|----------|------------|-------------|
| `client.teammates` | `create` `list` `get` `update` `delete` `enable_webhook` `enable_email_inbox` | Agent personas with tools and instructions |
| `client.runs` | `create` `poll` `create_and_wait` `reply` `reply_and_wait` `stream_text` `get` `list` `cancel` `approve` `answer` `update_permission_mode` `list_files` `download_file` | Execute teammates and stream results |
| `client.tasks` | `create` `list` `get` `update` `delete` `run` | Reusable task definitions |
| `client.tasks.triggers` | `create` `list` `delete` | Schedule, webhook, and email triggers |
| `client.apps` | `list` `connect` `connect_oauth` `connect_api_key` `connect_complete` `disconnect` | Tool catalog and end-user app connections |
| `client.memories` | `create` `list` `delete` | Per-user persistent memory |
| `client.permissions` | `create` `list` `delete` | Pre-approve tools for end-users |
| `client.users` | `create` `list` `get` `update` `delete` | End-user profile management |
| `client.webhooks` | `create` `list` `get` `update` `delete` `list_deliveries` `verify_signature` | Webhook endpoints and delivery tracking |
| `client.settings` | `get` `update` | Account configuration |
| `client.auth` | `get_usage` `resend_verify` | Account usage and verification helpers |

## Pagination

```python
# standard page
page = client.runs.list(limit=50)
for run in page.data:
    print(run.id, run.status)

# auto-paginate through all results
for run in client.runs.list().auto_paging_iter():
    print(run.id, run.status)
```

## Webhooks

```python
# register an endpoint
hook = client.webhooks.create(
    url="https://example.com/hook",
    events=["run.completed", "run.failed"],
)
secret = hook.secret  # save this -- only shown once

# verify incoming webhooks (e.g. in Flask/FastAPI)
from m8tes import Webhooks

is_valid = Webhooks.verify_signature(
    body=request.body,
    headers=dict(request.headers),
    secret=secret,
)
```

## Files

```python
files = client.runs.list_files(run_id=42)
for f in files:
    print(f.name, f.size)

content = client.runs.download_file(run_id=42, filename="report.csv")
```

## Error handling

```python
from m8tes import M8tes, NotFoundError, RateLimitError, AuthenticationError

try:
    client.teammates.get(999)
except NotFoundError:
    print("teammate not found")
except RateLimitError as e:
    print(f"rate limited, retry after {e.retry_after}s")
except AuthenticationError:
    print("invalid API key")
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `M8TES_API_KEY` | API key for authentication | — |
| `M8TES_BASE_URL` | API endpoint | `https://m8tes.ai` |

```python
client = M8tes(api_key="m8_...", timeout=300)  # custom timeout in seconds
```

## CLI

```bash
m8tes auth login                    # authenticate
m8tes auth usage                    # account limits and current usage
m8tes apps connect-api-key gemini KEY
m8tes run set-permission-mode 42 approval
m8tes mate task ID "message"        # run a task
m8tes mate chat ID                  # interactive chat
```

See [CLI documentation](https://m8tes.ai/docs/cli) for all commands and options.

## Testing

Use the fastest layer that matches the change you made.

| Layer | Command | What it proves |
|------|---------|----------------|
| Unit | `make test-unit` | Request/response serialization, parsing, pagination, helper behavior |
| SDK integration | `make test-v2-integration` | Real FastAPI backend parity for the public V2 SDK surface |
| Backend V2 integration | `cd ../../fastapi && make test-v2-integration` | Route + DB behavior for V2 endpoints |
| Full V2 check from repo root | `make check-v2` | Backend V2 integration plus SDK V2 integration |
| Full deterministic repo gate | `make check` | Backend, runtime, SDK, frontend, and V2 integration in one command |
| E2E / smoke | `make test-e2e` / `make test-smoke` | Live runtime/provider confidence for expensive end-to-end flows |

## License

MIT License — see [LICENSE](LICENSE) for details.

## Links

- Documentation: [m8tes.ai/docs](https://m8tes.ai/docs)
- Developers: [m8tes.ai/developers](https://m8tes.ai/developers)
- PyPI: [pypi.org/project/m8tes](https://pypi.org/project/m8tes/)
- Email: support@m8tes.ai
