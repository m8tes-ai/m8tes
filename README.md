# m8tes Python SDK

[![PyPI](https://img.shields.io/pypi/v/m8tes.svg)](https://pypi.org/project/m8tes/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Python SDK for [m8tes.ai](https://m8tes.ai) — build autonomous AI teammates that run tasks, manage workflows, and integrate with your tools.

## Install

```bash
pip install m8tes
```

## Quick start

```python
from m8tes import M8tes

client = M8tes()  # uses M8TES_API_KEY env var

for event in client.runs.create(message="summarize the latest AI news"):
    print(event.type, event.raw)
```

## SDK usage

### Create a teammate

```python
bot = client.teammates.create(
    name="support bot",
    tools=["gmail", "slack"],
    instructions="handle customer tickets",
)
```

### Run (streaming)

```python
for event in client.runs.create(
    teammate_id=bot.id,
    message="close resolved tickets",
):
    print(event.type, event.raw)
```

### Run (non-streaming)

```python
run = client.runs.create(
    teammate_id=bot.id,
    message="close resolved tickets",
    stream=False,
)
print(run.output)
```

### Reply to a run

```python
for event in client.runs.reply(run_id=42, message="also archive them"):
    print(event.type, event.raw)
```

### Schedule recurring work

```python
task = client.tasks.create(
    teammate_id=bot.id,
    instructions="generate weekly report",
)
client.tasks.triggers.create(task.id, type="schedule", cron="0 9 * * 1")
```

### Manage per-user memory

```python
client.memories.create(user_id="customer_123", content="prefers email over Slack")

memories = client.memories.list(user_id="customer_123")
for m in memories.data:
    print(m.content)
```

### Pre-approve tools (permissions)

```python
client.permissions.create(user_id="customer_123", tool="gmail")
```

### Register webhooks

```python
client.webhooks.create(url="https://example.com/hook", events=["run.completed"])
```

### List available integrations

```python
apps = client.apps.list()
for app in apps.data:
    print(f"{app.display_name} ({app.category}) — connected: {app.connected}")
```

## Resources

```python
client.teammates    # CRUD + webhook enable/disable
client.runs         # create (streaming/non-streaming), list, get, cancel, reply
client.tasks        # CRUD + triggers (schedule, webhook, email)
client.apps         # list tools, manage OAuth connections
client.memories     # pre-populate end-user memories
client.permissions  # pre-approve tools for end-users
client.webhooks     # webhook endpoint CRUD + delivery tracking
```

## Multi-tenancy

Isolate data per end-user with `user_id`:

```python
bot = client.teammates.create(name="user bot", user_id="cust_123")
client.memories.create(user_id="cust_123", content="prefers dark mode")
client.permissions.create(user_id="cust_123", tool="gmail")
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

## CLI

The package also includes a CLI:

```bash
m8tes auth login                    # authenticate
m8tes mate task ID "message"        # run a task
m8tes mate chat ID                  # interactive chat
m8tes --dev mate list               # use local backend
```

### CLI commands

```bash
# Auth
m8tes auth register / login / status / logout

# Teammates
m8tes mate create / list / get ID / update ID / archive ID

# Execution
m8tes mate task ID "message"        # streaming task
m8tes mate chat ID                  # interactive chat

# Runs
m8tes run get RUN_ID / list / list-mate MATE_ID
m8tes run conversation RUN_ID / usage RUN_ID / tools RUN_ID
```

Streaming output modes: `--output verbose` (default), `compact`, or `json`.

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `M8TES_API_KEY` | API key for authentication | — |
| `M8TES_BASE_URL` | API endpoint | `https://m8tes.ai` |

## Development

```bash
make install          # install dependencies via uv
make check            # format + lint + type-check + tests
make quick            # fast loop: format + lint + unit tests
make test-integration # integration tests (requires backend at localhost:8000)
make build            # build distributable package
```

## License

MIT License — see [LICENSE](LICENSE) for details.

## Links

- Documentation: [m8tes.ai/docs](https://m8tes.ai/docs)
- PyPI: [pypi.org/project/m8tes](https://pypi.org/project/m8tes/)
- Email: support@m8tes.ai
