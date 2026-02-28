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

Create a teammate, deploy it on a schedule. Everything else is handled.

```python
from m8tes import M8tes

client = M8tes()  # uses M8TES_API_KEY env var

# create a reusable teammate
teammate = client.teammates.create(
    name="revenue-report",
    instructions="Pull last week's Stripe charges, compare to the prior week, "
                 "post a summary to #finance on Slack.",
    tools=["stripe", "slack"],
)

# schedule it — runs every Monday at 9am in a hosted sandbox, OAuth managed for you
task = client.tasks.create(teammate_id=teammate.id)
client.tasks.triggers.create(task.id, type="schedule", cron="0 9 * * 1")

# or run it right now
for event in client.runs.create(teammate_id=teammate.id, message="run now"):
    if event.type == "text-delta":
        print(event.delta, end="")
```

Or skip the setup and run a one-off:

```python
run = client.runs.create(
    name="support triage",
    instructions="triage inbound support emails. create Linear tickets "
                 "for bugs. escalate urgent issues to #support-escalations.",
    tools=["gmail", "linear", "slack"],
    message="process all unread support emails from today",
    stream=False,
)
run = client.runs.poll(run.id)
print(run.output)
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

## Human-in-the-loop

```python
run = client.runs.create(
    message="draft and send the weekly report",
    human_in_the_loop=True,
    permission_mode="approval",  # or "plan", "autonomous"
    stream=False,
)

# check pending permission requests
pending = client.runs.permissions(run.id)

# approve a tool use
client.runs.approve(run.id, request_id="req_123", decision="allow")

# answer an agent question
client.runs.answer(run.id, answers={"Which channel?": "#general"})
```

## Triggers

```python
# schedule -- every weekday at 9am
client.tasks.triggers.create(task.id, type="schedule", cron="0 9 * * 1-5")

# webhook -- POST to a URL to trigger runs
trigger = client.tasks.triggers.create(task.id, type="webhook")
print(trigger.url)  # POST here to trigger

# email -- forward emails to trigger runs
trigger = client.tasks.triggers.create(task.id, type="email")
print(trigger.address)  # forward emails here

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

## Resources

| Resource | Key methods | Description |
|----------|------------|-------------|
| `client.teammates` | `create` `list` `get` `update` `delete` `enable_webhook` `enable_email_inbox` | Agent personas with tools and instructions |
| `client.runs` | `create` `poll` `create_and_wait` `reply` `reply_and_wait` `stream_text` `get` `list` `cancel` `approve` `answer` `list_files` `download_file` | Execute teammates and stream results |
| `client.tasks` | `create` `list` `get` `update` `delete` `run` | Reusable task definitions |
| `client.tasks.triggers` | `create` `list` `delete` | Schedule, webhook, and email triggers |
| `client.apps` | `list` `connect` `connect_complete` `disconnect` | Tool catalog and OAuth connections |
| `client.memories` | `create` `list` `delete` | Per-user persistent memory |
| `client.permissions` | `create` `list` `delete` | Pre-approve tools for end-users |
| `client.users` | `create` `list` `get` `update` `delete` | End-user profile management |
| `client.webhooks` | `create` `list` `get` `update` `delete` `list_deliveries` `verify_signature` | Webhook endpoints and delivery tracking |
| `client.settings` | `get` `update` | Account configuration |

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
m8tes mate task ID "message"        # run a task
m8tes mate chat ID                  # interactive chat
```

See [CLI documentation](https://m8tes.ai/docs/cli) for all commands and options.

## License

MIT License — see [LICENSE](LICENSE) for details.

## Links

- Documentation: [m8tes.ai/docs](https://m8tes.ai/docs)
- Developers: [m8tes.ai/developers](https://m8tes.ai/developers)
- PyPI: [pypi.org/project/m8tes](https://pypi.org/project/m8tes/)
- Email: support@m8tes.ai
