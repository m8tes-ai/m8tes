# m8tes Python SDK

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Python SDK for [m8tes.ai](https://m8tes.ai) — build autonomous AI agents.

## Install

```bash
pip install m8tes
```

## Quick Start

```python
from m8tes import M8tes

client = M8tes()  # uses M8TES_API_KEY env var

for event in client.runs.create(message="Summarize the latest AI news"):
    print(event.type, event.raw)
```

## SDK Usage

### Create a teammate

```python
bot = client.teammates.create(
    name="Support Bot",
    tools=["gmail", "slack"],
    instructions="Handle customer tickets",
)
```

### Run (streaming)

```python
for event in client.runs.create(
    teammate_id=bot.id,
    message="Close resolved tickets",
):
    print(event.type, event.raw)
```

### Run (non-streaming)

```python
run = client.runs.create(
    teammate_id=bot.id,
    message="Close resolved tickets",
    stream=False,
)
print(run.output)
```

### Reply to a run

```python
for event in client.runs.reply(run_id=42, message="Also archive them"):
    print(event.type, event.raw)
```

### Schedule recurring work

```python
# Create a reusable task, then attach a trigger
task = client.tasks.create(
    teammate_id=bot.id,
    instructions="Generate weekly report",
)
client.tasks.triggers.create(task.id, type="schedule", cron="0 9 * * 1")
```

### Manage per-user memory

```python
client.memories.create(user_id="customer_123", content="Prefers email over Slack")

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

## CLI Reference

### Authentication

```bash
m8tes auth register              # Register new account
m8tes auth login                 # Login to existing account
m8tes auth status                # Check authentication status
m8tes auth logout                # Logout and clear credentials
```

### Teammate Management

```bash
m8tes mate create               # Create new teammate (interactive)
m8tes mate list                 # List all your teammates
m8tes mate get ID               # Get teammate details
m8tes mate update ID            # Update teammate configuration
m8tes mate archive ID           # Archive teammate (with confirmation)
```

### Execute Tasks & Chat

```bash
m8tes mate task ID "message"    # Execute task with teammate
m8tes mate chat ID              # Start interactive chat session
```

#### Streaming Output Modes

Control how much detail you see with `--output`:

- `verbose` _(default)_ — Rich incremental view with tool usage, thinking, and Markdown summary.
- `compact` — Final text only.
- `json` — Raw event envelopes (one JSON object per line) for scripting.

```bash
m8tes mate task 27 "Summarize campaign metrics" --output compact
```

### Run Inspection

```bash
m8tes run get RUN_ID             # Comprehensive run details
m8tes run list                   # List all your runs
m8tes run list-mate MATE_ID      # List runs for specific teammate
m8tes run conversation RUN_ID    # View conversation messages
m8tes run usage RUN_ID           # View token usage and costs
m8tes run tools RUN_ID           # View tool executions
m8tes run tools RUN_ID -v        # Verbose tool execution details
```

### Development Mode

```bash
m8tes --dev mate list            # Use local backend (port 8000)
m8tes --base-url URL mate list   # Custom backend URL
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `M8TES_API_KEY` | API key for authentication | — |
| `M8TES_BASE_URL` | API endpoint | `https://m8tes.ai` |

The CLI also supports keychain-based credentials via `m8tes auth login`.

## Development

```bash
make install       # Install dependencies via uv
make check         # Format + lint + type-check + test with coverage
make quick         # Fast loop: format + lint + unit tests
make build         # Build distributable package
```

### Testing

```bash
make test          # All tests (excludes e2e/smoke by default)
make test-unit     # Unit tests only
make test-cov      # Tests with coverage report
make test-e2e      # E2E tests (requires backend running)
```

## License

MIT License — see [LICENSE](LICENSE) for details.

## Support

- Documentation: [m8tes.ai/docs](https://m8tes.ai/docs)
- Email: support@m8tes.ai
