# m8tes Python SDK

[![PyPI](https://img.shields.io/pypi/v/m8tes.svg)](https://pypi.org/project/m8tes/)
[![Tests](https://github.com/m8tes-ai/m8tes/actions/workflows/test.yml/badge.svg)](https://github.com/m8tes-ai/m8tes/actions/workflows/test.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Ship autonomous agents. Skip the infrastructure.**

Hosted runtime, 150+ integrations, scheduling, memory, and optional email or iMessage inboxes. Ship autonomous agents to production in minutes.

## Install

```bash
pip install m8tes
```

## Quick start

```python
from m8tes import M8tes, PermissionMode

client = M8tes()  # uses M8TES_API_KEY env var

result = client.runs.create_and_wait(
    message="pull last week's Stripe MRR and post to #revenue on Slack",
    tools=["stripe", "slack"],
    instructions="you are a finance ops assistant",
    permission_mode=PermissionMode.AUTONOMOUS,
    email_inbox=True,
)
print(result.output)
print(f"inbox: {result.email_address}")  # forward emails here to trigger future runs
```

Set `task_setup_tools=False` on `client.runs.create(...)`, `client.runs.reply(...)`, or `client.tasks.run(...)` when you do not want the agent to receive the internal same-scope management tools for teammates, tasks, runs, approvals, files, memories, inboxes, webhooks, and app connections during that execution. Set `feedback=False` on those same V2 calls to disable the internal issue-reporting feedback tool (`report_issue`) for that execution.

When you pass `user_id`, the run is scoped to that end user. If you target an existing teammate or task that is already scoped, the `user_id` you pass must match that resource's scope. If you omit `user_id`, runs and tasks inherit the scope from the targeted teammate or task.

→ Full docs and examples at [m8tes.ai/docs](https://m8tes.ai/docs)

## Auth & usage

Rotate your API key with `POST /api/v2/token`. That endpoint returns a new API key and invalidates the previous one.

Check current plan, run usage, and cost limits with `client.billing.usage()` (or `client.auth.get_usage()`). A billable run is one execution that completes with output — manual, scheduled, webhook, email, reply, or retry. Self-meter spend and control overage:

```python
usage = client.billing.usage()
print(usage.plan, usage.runs_used, usage.runs_limit, usage.overage_used_cents)

# Browse the plan catalog (pro / max_5x / max_20x)
for plan in client.billing.plans():
    print(plan.slug, plan.display_name, plan.included_runs, plan.monthly_price_cents)

# Opt in to usage overage with a monthly spend cap so runs keep going past the plan limit
client.billing.set_overage(enabled=True, monthly_cap_cents=5000)  # $50 cap
```

New accounts start on a time-boxed `trial` (no free tier); upgrade to a paid plan to raise run limits.

Need email-triggered runs? Opt in with `email_inbox=True` on `client.teammates.create(...)` or call `client.teammates.enable_email_inbox(teammate_id)` later.

Need iMessage-triggered runs? Configure BlueBubbles on your account, then set `inbound_imessage_enabled=True` and `imessage_chat_guid="..."` on `client.teammates.create(...)` or `client.teammates.update(...)`. Use a dedicated 1:1 chat unless you intentionally want everyone in that thread to trigger the teammate and receive its replies.

Inspect account request history with `client.audit_logs.list(...)`:

```python
page = client.audit_logs.list(method="POST", resource_type="run", limit=10)
for log in page.data:
    print(log.created_at, log.method, log.path, log.status_code)
```

## What you skip

| Build it yourself | With m8tes |
|---|---|
| Sandboxed execution environment | ✅ Hosted runtime, zero infra |
| OAuth for every app you connect | ✅ 150+ integrations with managed OAuth |
| Scheduling, webhook, email, and iMessage triggers | ✅ Built in — set once, runs forever |
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
- **Scheduled runs, webhooks, email, and iMessage triggers** — set the cadence once. Daily, weekly, or hourly runs happen automatically.
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

## Models

Pick the model per teammate or per run via `model=`. List what's available (with prices) instead of hardcoding:

```python
for m in client.models.list().data:
    print(m.id, m.provider, m.pricing.input_per_mtok, "→", m.pricing.output_per_mtok, "/Mtok")

bot = client.teammates.create(name="Ops", model="sonnet")   # or per run: runs.create(..., model="opus")
```

Today that's the Claude models `sonnet`, `opus` (default), and `fable` (most capable, ~2x cost), plus `gpt-5.5`, `glm-5.2`, and `deepseek-v3-2` served through the zero-data-retention gateway. `models.list()` is the live source of truth; omit `model` to use the `default`.

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

### Detect a failed stream

A run can fail mid-stream (expired credential, model rate limit, quota). The default
`iter_text()` / `stream.text` path drops error events, so either opt into raising or check
after iterating:

```python
# Raise RunFailedError if the run fails mid-stream
for event in client.runs.create(message="...", raise_on_error=True):
    ...

# Or check without raising
with client.runs.create(message="...") as stream:
    for chunk in stream.iter_text():
        print(chunk, end="")
    if stream.has_errors:
        print("run failed:", stream.errors)
```

### Resume a dropped stream

If the connection drops mid-run (proxy idle-timeout, network blip), rejoin with the
`run_id` captured from the metadata event. `runs.stream(run_id)` replays the run's full
history then live deltas, so reset any local accumulation on reconnect:

```python
stream = client.runs.create(message="long autonomous task")
run_id = None
try:
    for event in stream:
        run_id = stream.run_id
        ...
except Exception:  # connection dropped mid-run
    if run_id:
        for event in client.runs.stream(run_id):  # re-attach and replay
            ...
```

The server emits a 15s keepalive on the streaming path so a long-silent tool call doesn't
trip the read timeout; raise it for very long runs with `M8tes(timeout=...)`.

## Human-in-the-loop

Pass callbacks to `wait()`. Approval pauses are handled inline:
Use `PermissionMode` constants to avoid string typos.

```python
from m8tes import PermissionMode

run = client.runs.create(
    message="draft and send the weekly report",
    human_in_the_loop=True,
    permission_mode=PermissionMode.APPROVAL,
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
    permission_mode=PermissionMode.APPROVAL,
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
run = client.runs.update_permission_mode(run.id, permission_mode=PermissionMode.APPROVAL)
print(run.permission_mode)  # "approval"
```

Switch mode while the run is still active, including `awaiting_approval`. Switching to
`PermissionMode.AUTONOMOUS` auto-approves pending tool approval requests and resumes a paused
tool approval run. `AskUserQuestion` and plan approvals still wait for `client.runs.answer()`.

## Computer use

When your account has sandbox execution enabled, agents run inside a full Linux desktop. No changes to your code — you get the same run API. The agent gains three extra tools automatically: `computer` (mouse/keyboard/screenshots), `bash` (shell), and `str_replace_based_edit_tool` (file editing).

```python
with client.runs.create(
    teammate_id=...,
    message="open chromium, go to example.com, and return the page title",
) as stream:
    for event in stream:
        if event.type == "tool_result":
            for block in event.content or []:
                if block.get("type") == "image":
                    # base64 PNG screenshot after each desktop action
                    screenshot_data = block["source"]["data"]
        if event.type == "text-delta":
            print(event.delta, end="")
```

Extra events in the stream:

| Event | When |
|-------|------|
| `sandbox-connecting` | Desktop environment starting |
| `sandbox-connected` | Desktop ready (`duration_ms` included) |

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

# iMessage — route one BlueBubbles chat to a teammate
messages_bot = client.teammates.create(
    name="messages bot",
    inbound_imessage_enabled=True,
    imessage_chat_guid="iMessage;-;+15551231234",
)
print(messages_bot.imessage_chat_guid)  # use a dedicated 1:1 chat unless group access is intended

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

# Platform-provisioned app (auth_type "platform_provisioned", e.g. twilio):
# the platform allocates a dedicated resource (a phone number) for you.
result = client.apps.provision("twilio", user_id="cust_123")
print(result.phone_number)              # "+15551234567"
client.apps.release("twilio", user_id="cust_123")  # release it back
```

## Resources

| Resource | Key methods | Description |
|----------|------------|-------------|
| `client.teammates` | `create` `list` `get` `update` `delete` `reset` `enable_webhook` `disable_webhook` `enable_email_inbox` `disable_email_inbox` `enable_fetchmail` `disable_fetchmail` | Agent personas with tools and instructions |
| `client.teammate_templates` | `list` | Pre-built teammate template catalog (slugs for `teammates.create(from_template=...)`) |
| `client.runs` | `create` `stream` `poll` `wait` `create_and_wait` `reply` `reply_and_wait` `stream_text` `get` `list` `cancel` `retry` `permissions` `approve` `answer` `update_permission_mode` `list_files` `download_file` | Execute teammates and stream results |
| `client.audit_logs` | `list` | Account-scoped API request history |
| `client.tasks` | `create` `list` `get` `update` `delete` `run` `run_and_wait` `lessons` `delete_lesson` `clear_lessons` | Reusable task definitions (+ lesson curation) |
| `client.tasks.triggers` | `create` `list` `delete` | Schedule, webhook, and email triggers |
| `client.apps` | `list` `is_connected` `connect` `connect_oauth` `connect_api_key` `connect_complete` `provision` `release` `list_triggers` `disconnect` | Tool catalog and end-user app connections |
| `client.bridges` | `create` `list` `get` `update` `rotate_secret` `delete` | Per-account BlueBubbles (iMessage) bridges |
| `client.memories` | `create` `list` `delete` | Per-user persistent memory |
| `client.permissions` | `create` `list` `delete` | Pre-approve tools for end-users |
| `client.users` | `create` `list` `get` `update` `delete` | End-user profile management |
| `client.webhooks` | `create` `list` `get` `update` `delete` `list_deliveries` `verify_signature` | Webhook endpoints and delivery tracking |
| `client.settings` | `get` `update` | Account configuration |
| `client.billing` | `usage` `plans` `set_overage` | Run usage, plan catalog, and opt-in overage controls |
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

### Run-level failures

Exceptions above cover problems *reaching* the API. A run can also fail
*upstream* — an expired Claude credential, an exhausted plan quota, a model rate
limit. The HTTP call succeeds, so no exception is raised, but the run carries the
failure: `status` is `"completed"`, the message is in `run.output`, and
`run.error_code` holds a machine-readable class (e.g. `oauth_revoked`,
`subscription_quota_exhausted`, `rate_limited`). Check `error_code` before
trusting `output`:

```python
run = client.runs.create_and_wait(teammate_id=mate.id, message="...")
if run.error_code:
    print(f"run failed upstream: {run.error_code} — {run.output}")
else:
    print(run.output)
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `M8TES_API_KEY` | API key for authentication | — |
| `M8TES_BASE_URL` | API endpoint | `https://api.m8tes.ai/api/v2` |

```python
client = M8tes(api_key="m8_...", timeout=300)  # custom timeout in seconds
```

## CLI

```bash
m8tes auth login                    # authenticate
m8tes auth usage                    # account limits and current usage
m8tes apps connect-api-key gemini KEY
m8tes mate create --non-interactive --name "messages bot" --tools gmail --instructions "Help via iMessage" --enable-imessage --imessage-chat-guid "iMessage;-;+15551231234"
m8tes run set-permission-mode 42 approval
m8tes mate task ID "message"        # run a task
m8tes mate chat ID                  # interactive chat
```

`m8tes run set-permission-mode` also works while a run is paused. Switching to `autonomous`
resumes pending tool approvals, but `AskUserQuestion` still waits for an explicit answer.

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
