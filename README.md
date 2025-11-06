# m8tes Python SDK

[![CI/CD Pipeline](https://github.com/m8tes/python-sdk/workflows/CI%2FCD%20Pipeline/badge.svg)](https://github.com/m8tes/python-sdk/actions)
[![Smoke Tests](https://github.com/m8tes/python-sdk/workflows/Smoke%20Tests/badge.svg)](https://github.com/m8tes/python-sdk/actions)
[![codecov](https://codecov.io/gh/m8tes/python-sdk/branch/main/graph/badge.svg)](https://codecov.io/gh/m8tes/python-sdk)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Python SDK for [m8tes.ai](https://m8tes.ai) - AI teammates that handle paid ads automation.

## 🚀 Quick Start

```bash
# Install
uv add m8tes  # or pip install m8tes

# Authenticate
m8tes auth register  # or: m8tes auth login
m8tes auth status

# Create your first teammate
m8tes mate create

# Use your teammate
m8tes mate task 1 "What campaigns do I have?"
m8tes mate chat 1
```

## 📋 CLI Reference

### Authentication

```bash
m8tes auth register              # Register new account
m8tes auth login                 # Login to existing account
m8tes auth status                # Check authentication status
m8tes auth logout                # Logout and clear credentials
```

### Teammate Management

```bash
# Create and manage teammates
m8tes mate create               # Create new teammate (interactive)
m8tes mate list                 # List all your teammates
m8tes mate get ID               # Get teammate details
m8tes mate update ID            # Update teammate configuration
m8tes mate archive ID           # Archive teammate (with confirmation)
m8tes mate archive ID --force   # Archive without confirmation

# Execute tasks
m8tes mate task ID "message"    # Execute task with teammate

# Interactive chat
m8tes mate chat ID              # Start chat session with teammate
```

#### Streaming Output Modes

Most `mate` commands stream responses live. Choose how much detail you want with `--output`:

- `verbose` _(default)_ – Rich, incremental view that shows generated text as it appears, highlights thinking/plan sections, renders tool usage with live spinners/result panels, and now finishes with a Markdown-formatted summary of the response.
- `compact` – Prints only the assistant’s final text without intermediates; useful when you just want the answer.
- `json` – Emits raw event envelopes (one JSON object per line) for scripting or piping to another process.

Example:

```bash
m8tes mate task 27 "Summarize the latest campaign metrics" --output compact
```

### Run Inspection & Analytics

```bash
# View run details
m8tes run get RUN_ID             # Comprehensive run details (conversation + usage + tools)
m8tes run list                   # List all your runs
m8tes run list-mate MATE_ID      # List runs for specific teammate

# Inspect specific aspects
m8tes run conversation RUN_ID    # View conversation messages
m8tes run usage RUN_ID           # View token usage and costs
m8tes run tools RUN_ID           # View tool executions
m8tes run tools RUN_ID -v        # Verbose tool execution details
```

### Google Ads Integration

```bash
m8tes google connect             # Connect Google Ads account
m8tes google status              # Check connection status
```

## Installation

```bash
uv add m8tes     # or: pip install m8tes
```

## Python Usage

### Quick Start

```python
from m8tes import M8tes

# Initialize client
client = M8tes()  # Uses M8TES_API_KEY env var or saved credentials

# Create a teammate
instance = client.instances.create(
    name="Campaign Optimizer",
    instructions="Analyze Google Ads campaigns and suggest optimizations"
)

# Execute a task
run = instance.execute_task("What campaigns do I have for customer 1234567890?")
print(run.metrics.get("result"))

# Start chat session
with instance.start_chat_session() as chat:
    response = chat.send("Show me my top performing keywords")
    print(response)

    response = chat.send("What's the average CPC?")
    print(response)
```

### Working with Teammates

```python
# List all teammates
instances = client.instances.list()
for instance in instances:
    print(f"{instance.id}: {instance.name} - {instance.run_count} runs")

# Get specific teammate
instance = client.instances.get(1)
print(f"Teammate: {instance.name}")
print(f"Tools: {', '.join(instance.tools)}")

# Execute task with specific teammate
run = instance.execute_task("Analyze my ad performance")
print(f"Status: {run.status}")
print(f"Result: {run.metrics.get('result')}")

# Chat with specific teammate
chat = instance.start_chat_session()
response = chat.send("Hello!")
print(response)
chat.end()
```

### Working with Runs

```python
# Get all runs for current user
runs = client.runs.list_user_runs(limit=20)
for run in runs:
    print(f"Run {run.id}: {run.run_type}")

# Get runs for specific teammate
runs = client.runs.list_for_instance(instance_id=1, limit=10)

# Get specific run
run = client.runs.get(123)

# Access run data
conversation = run.get_conversation()  # Get conversation messages
usage = run.get_usage()                # Get token usage & costs
tools = run.get_tool_executions()      # Get tool execution history
details = run.get_details()            # Get everything in one call
```

## Features

- 🤝 **Create AI Teammates**: Build marketing teammates with natural language instructions
- 🔧 **Tool Integration**: Google Ads Query (GAQL) tool built-in
- 📊 **Task Execution**: One-off tasks with isolated context and run tracking
- 💬 **Chat Sessions**: Multi-turn conversations with preserved history
- 🏃 **Run Analytics**: View conversation history, token usage, costs, and tool executions
- 🔍 **Detailed Inspection**: CLI commands for comprehensive run data analysis
- ✏️ **Teammate Management**: Update, archive, and organize your teammates
- 🔐 **Secure OAuth**: Google Ads authentication via OAuth flow
- 🛠️ **CLI & SDK**: Full-featured command-line and Python library
- 🎨 **Beautiful Output**: Clean formatting, emoji status, relative timestamps

## CLI Usage Examples

### Teammate Workflow

```bash
# 1. Create a teammate
m8tes mate create
# Follow prompts to configure name, tools, instructions

# 2. List your teammates
m8tes mate list
# ✅ Campaign Optimizer
#    ID: 1
#    Tools: run_gaql_query
#    Instructions: Analyze campaigns and suggest optimizations
#    Runs: 5 • Last: 2 hours ago

# 3. Get teammate details
m8tes mate get 1

# 4. Execute a task
m8tes mate task 1 "Show me my top 5 campaigns by spend"
# 🎯 Task: Show me my top 5 campaigns by spend
# 🤝 Using: Campaign Optimizer (ID: 1)
# ✅ Task completed (Run ID: 42)
# 📊 Result: [teammate response]
# ⏱️  Completed in 3.2s

# 5. Start chat session
m8tes mate chat 1
# 🤝 Chatting with: Campaign Optimizer (ID: 1)
# 📝 Session Run ID: 43
# > What's my total ad spend this month?
# > Which campaigns have the best ROAS?
# > /exit

# 6. Update teammate configuration
m8tes mate update 1
# Follow prompts to update name, description, or instructions

# 7. Archive teammate
m8tes mate archive 1
# Confirms before archiving, run history preserved
```

### Google Ads Setup

```bash
# Connect your Google Ads account
m8tes google connect
# Opens browser for OAuth flow

# Check status
m8tes google status
```

### Run Inspection & Analytics

```bash
# After executing a task, you get a Run ID
m8tes mate task 1 "Analyze my campaigns"
# ✅ Task completed (Run ID: 42)

# View comprehensive run details
m8tes run get 42
# 📊 Run Details - ID: 42
# ==========================================
# 🔹 Basic Info:
#    Type: task
#    Instance ID: 1
# 💬 Conversation: 5 messages
# 💰 Token Usage:
#    Total Cost: $0.0234
#    Total Tokens: 1,245
# 🔧 Tool Executions: 2
#    ✅ run_gaql_query (1,234ms)
#    ✅ run_gaql_query (890ms)

# View just the conversation
m8tes run conversation 42
# 💬 Conversation - Run ID: 42
# 👤 User:
#    Analyze my campaigns
# 🤖 Assistant:
#    I'll analyze your campaigns...

# Check token usage and costs
m8tes run usage 42
# 💰 Token Usage - Run ID: 42
# 📊 Summary:
#    Total Cost: $0.0234
#    Total Tokens: 1,245

# See what tools were executed
m8tes run tools 42
# 🔧 Tool Executions - Run ID: 42
# 2 tool executions:
# 1. run_gaql_query
#    Status: ✅ Success
#    Duration: 1234ms

# Get detailed tool execution info
m8tes run tools 42 -v
# Shows arguments, results, and errors

# List all your runs
m8tes run list --limit 20
# 🏃 Your Runs (showing 20)
# ✅ Run 42 - task
#    Agent ID: 1
#    ...

# List runs for specific teammate
m8tes run list-mate 1 --limit 10
```

### Development Mode

```bash
# Use local backend (port 5000)
m8tes --dev mate list
m8tes --dev mate task 1 "test message"

# Custom backend URL
m8tes --base-url http://localhost:8080 mate list
```

## Configuration

### Environment Variables

```bash
export M8TES_API_KEY="your-api-key"          # API authentication
export M8TES_BASE_URL="https://www.m8tes.ai" # API endpoint
export M8TES_AGENT_URL="http://localhost:8787" # Agent worker URL (dev)
```

### Credentials Storage

The SDK automatically stores credentials in your system keychain after login:

```bash
# Login stores credentials
m8tes auth login

# Future commands use stored credentials
m8tes mate list  # No need to specify API key
```

## Key Concepts

### Teammates vs Runs

- **Teammate**: A persistent configuration (name, tools, instructions)
- **Run**: A single execution of a teammate (task or chat session)

### Task vs Chat

- **Task Mode**: One-off execution, clears history before running

  ```bash
  m8tes mate task 1 "Analyze my campaigns"
  ```

- **Chat Mode**: Multi-turn conversation, preserves history
  ```bash
  m8tes mate chat 1
  > Tell me about my campaigns
  > What's the average CTR?
  ```

## Examples

See the [examples](examples/) directory for more detailed examples:

- [basic_usage.py](examples/basic_usage.py) - Basic SDK usage
- More examples coming soon!

## Development

### Quick Setup

```bash
pip install -e ".[dev]"
make pre-commit-install
```

### Testing

```bash
# Fast unit tests (< 1 second)
pytest -m unit

# All tests with coverage
pytest --cov=m8tes --cov-report=term

# E2E tests (requires backend + worker running)
make test-e2e

# Run exactly what CI runs
make ci-test

# Quick feedback loop (< 10 seconds)
make quick-check
```

**📖 See [TESTING.md](TESTING.md) for complete testing guide**

### Code Quality

```bash
# Format code
make format

# Lint
make lint

# Type check
make type-check

# All checks (what CI runs)
make check
```

### Pre-Commit Hooks

Pre-commit hooks automatically run on every commit:

- ✅ Black formatting
- ✅ Ruff linting
- ✅ mypy type checking
- ✅ Fast unit tests
- ✅ Security checks

```bash
# Install hooks (one-time)
make pre-commit-install

# Run manually
make pre-commit
```

### Building and Publishing

```bash
# Build package (creates both wheel and sdist)
python -m build

# Check package contents
twine check dist/*

# Upload to PyPI (requires credentials)
twine upload dist/*

# Upload to Test PyPI first (recommended)
twine upload --repository testpypi dist/*
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Support

- Documentation: [https://docs.m8tes.ai](https://docs.m8tes.ai)
- Issues: [GitHub Issues](https://github.com/m8tes/python-sdk/issues)
- Email: support@m8tes.ai
