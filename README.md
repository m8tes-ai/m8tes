# m8tes Python SDK

[![PyPI](https://img.shields.io/pypi/v/m8tes.svg)](https://pypi.org/project/m8tes/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Build agents. Skip the infrastructure.**

Hosted runtime, 150+ integrations, scheduling, memory, and optional email inboxes. Ship autonomous agents to production in minutes.

## Install

```bash
pip install m8tes
```

## Quick start

```python
from m8tes import M8tes

client = M8tes()  # uses M8TES_API_KEY env var

result = client.runs.create_and_wait(
    message="pull last week's Stripe MRR and post to #revenue on Slack",
    tools=["stripe", "slack"],
    instructions="you are a finance ops assistant",
    permission_mode="autonomous",
    email_inbox=True,
)
print(result.output)
print(f"inbox: {result.email_address}")  # forward emails here to trigger future runs
```

Set `task_setup_tools=False` on `client.runs.create(...)`, `client.runs.reply(...)`, or `client.tasks.run(...)` when you do not want the agent to receive the internal same-scope management tools for teammates, tasks, runs, approvals, files, memories, inboxes, webhooks, and app connections during that execution.

When you pass `user_id`, the run is scoped to that end user. If you target an existing teammate or task that is already scoped, the `user_id` you pass must match that resource's scope. If you omit `user_id`, runs and tasks inherit the scope from the targeted teammate or task.

→ Full docs and examples at [m8tes.ai/docs](https://m8tes.ai/docs)

## Auth & usage

Rotate your API key with `POST /api/v2/token`. That endpoint returns a new API key and invalidates the previous one.

Check current plan, run usage, and cost limits with `client.auth.get_usage()` or `m8tes auth usage`.

Need email-triggered runs? Opt in with `email_inbox=True` on `client.teammates.create(...)` or call `client.teammates.enable_email_inbox(teammate_id)` later.

## What you skip

| Build it yourself | With m8tes |
|---|---|
| Sandboxed execution environment | ✅ Hosted runtime, zero infra |
| OAuth for every app you connect | ✅ 150+ integrations with managed OAuth |
| Scheduling, webhook, and email triggers | ✅ Built in — set once, runs forever |
| Human-in-the-loop approval flows | ✅ Three modes: autonomous, approval, plan |
| Memory that persists across executions | ✅ Per-user memory out of the box |
| Real-time streaming to your UI | ✅ SSE events, works today |
| File output and delivery | ✅ Generated files downloadable via API |
| Webhook infrastructure for agent events | ✅ Outbound webhooks built in |
| Per-user data isolation | ✅ Set `user_id`, we handle the rest |
| An email inbox for your agent | ✅ Enable an @m8tes.ai inbox per teammate |

## What's included

- **Hosted agent runtime** — agents run in isolated sandboxes. You ship the workflow, not the infra.
- **150+ managed integrations** — Gmail, Slack, Notion, HubSpot, Stripe, Linear, Google Ads. OAuth and token refresh handled.
- **Human-in-the-loop** — require approval before sensitive actions. Keep the speed without giving up control.
- **Scheduled runs, webhooks, and email triggers** — set the cadence once. Daily, weekly, or hourly runs happen automatically.
- **Persistent memory** — agents remember past conversations and build on them. Per-user scoping for multi-tenant apps.
- **Permission modes** — autonomous, approval-required, or plan-then-execute. Start locked down, loosen as you gain confidence.
- **Per-user isolation** — set `user_id` on any run. Memory, history, and tools are strictly scoped.
- **Real-time streaming** — SSE events for text output, tool calls, files, and completion.
- **File handling** — agents generate reports and spreadsheets, downloadable through the API.

## Use cases

**Revenue reporting.** Pull MRR from Stripe, update the tracking sheet, post weekly delta to Slack. No more manual Monday reporting.

**Support triage.** Classify inbound tickets, draft replies, escalate blockers. Runs 24/7 on a schedule.

**Ad spend monitoring.** Check Google Ads weekly, pause low-converting campaigns, alert the team.

**Customer-facing agents.** Give each user their own agent with isolated memory, tools, and permissions. Multi-tenant without custom plumbing.

## vs. LangChain, CrewAI, and other SDKs

LangChain, CrewAI, and the OpenAI Agents SDK are orchestration frameworks. They help you coordinate model calls and tool use — but execution, OAuth, scheduling, memory, and approval flows are all yours to build and host.

| | LangChain / CrewAI / OpenAI SDK | m8tes |
|---|---|---|
| Agent execution | Local — you host it | Hosted sandbox |
| Tool integrations | Build and maintain | 150+ with managed OAuth |
| Scheduling & triggers | Write your own | Built in |
| Memory | DIY persistence layer | Per-user memory out of the box |
| Human-in-the-loop | Build approval flows | Three modes built in |
| Real-time streaming | Roll your own | SSE out of the box |
| Infrastructure | Your problem | Our problem |

m8tes is not a framework. It's the hosted runtime layer. The Python SDK is the client on top.

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
    task_setup_tools=False,      # keep this run limited to public tools only
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
run = client.runs.update_permission_mode(run.id, permission_mode="approval")
print(run.permission_mode)  # "approval"
```

## Triggers

```python
# schedule — every weekday at 9am (shortcut on tasks.create, no separate call needed)
task = client.tasks.create(teammate_id=..., instructions="...", schedule="0 9 * * 1-5")

# webhook — POST to a URL to trigger runs
task = client.tasks.create(teammate_id=..., instructions="...", webhook=True)
print(task.webhook_url)  # POST here to trigger (shown once)

# email — give the teammate an inbox at creation time
mate = client.teammates.create(name="inbox bot", email_inbox=True)
print(mate.email_address)  # forward emails here

# on demand — run a saved task directly
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

# run on their behalf — memory, permissions, history, and internal management tools all scoped
run = client.runs.create_and_wait(
    teammate_id=bot.id,
    message="check inbox for urgent items",
    user_id="cust_123",
)
```

The same rule applies to saved tasks and follow-up runs:

```python
task = client.tasks.create(
    teammate_id=bot.id,
    instructions="review urgent inbox items",
)

# inherits cust_123 from the scoped teammate
run = client.tasks.run(task.id, stream=False)
assert run.user_id == "cust_123"
```

## Apps & connections

Inspect the app catalog first, then use the helper that matches the app's auth type.

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

## Resources

| Resource | Key methods | Description |
|----------|------------|-------------|
| `client.teammates` | `create` `list` `get` `update` `delete` `enable_webhook` `disable_webhook` `enable_email_inbox` `disable_email_inbox` | Agent personas with tools and instructions |
| `client.runs` | `create` `poll` `wait` `create_and_wait` `reply` `reply_and_wait` `stream_text` `get` `list` `cancel` `permissions` `approve` `answer` `update_permission_mode` `list_files` `download_file` | Execute teammates and stream results |
| `client.tasks` | `create` `list` `get` `update` `delete` `run` `run_and_wait` | Reusable task definitions |
| `client.tasks.triggers` | `create` `list` `delete` | Schedule, webhook, and email triggers |
| `client.apps` | `list` `is_connected` `connect` `connect_oauth` `connect_api_key` `connect_complete` `disconnect` | Tool catalog and end-user app connections |
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
secret = hook.secret  # save this — only shown once

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

## Links

- [Documentation](https://m8tes.ai/docs)
- [Developer hub](https://m8tes.ai/developers)
- [Examples](./examples/)
- [Changelog](./CHANGELOG.md)
- [PyPI](https://pypi.org/project/m8tes/)
- support@m8tes.ai

## License

MIT — see [LICENSE](LICENSE) for details.
