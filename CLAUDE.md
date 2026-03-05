# CLAUDE.md

Python SDK + CLI for [m8tes.ai](https://m8tes.ai). Wraps authentication, SSE streaming, and typed payloads for building autonomous AI teammates.

## Responsibilities

- Manage auth: API key env (`M8TES_API_KEY`) or stored CLI credentials.
- Provide ergonomic helpers to create mates, run tasks, and start chats.
- Stream Claude Agent SDK events from FastAPI and expose them as Python generators / CLI output.
- Keep payload contracts aligned with FastAPI schemas (generate/update whenever backend changes).

## Structure

```
m8tes-python/
├── m8tes/
│   ├── _client.py        # V2 SDK entry point (M8tes class)
│   ├── _http.py          # Thin requests wrapper (auth, base_url, errors)
│   ├── _exceptions.py    # Typed error hierarchy (M8tesError, AuthenticationError, etc.)
│   ├── _types.py         # Dataclasses: Teammate, Run, Task, Trigger, App
│   ├── _streaming.py     # RunStream context manager (wraps AISDKStreamParser)
│   ├── _resources/       # Resource classes: Teammates, Runs, Tasks, Apps
│   ├── client.py         # Legacy CLI HTTP client + auth middleware
│   ├── agent.py          # Legacy mate models + execution helpers
│   ├── cli/
│   │   ├── main.py       # Entry point (`m8tes`)
│   │   └── commands/     # auth, mate task/chat, scheduling commands
│   ├── auth/             # Credential store + login flows
│   ├── streaming.py      # SSE parsing utilities (shared by V2 + legacy)
│   ├── types.py          # Legacy Pydantic request/response models
│   └── exceptions.py     # Legacy error hierarchy
├── tests/                # Unit + integration tests
└── Makefile              # Dev commands
```

### V2 SDK vs Legacy

- **V2 SDK** (`_client.py`, `_resources/`): Stripe-style `client.resource.method()` pattern, API key auth, targets `/api/v2/`. Used by developers.
- **Legacy** (`client.py`, `agent.py`): OAuth/keychain auth, targets `/api/v1/`. Used by CLI.

### V2 SDK Architecture

The V2 SDK follows a Stripe-style resource pattern:

```
M8tes (entry point)
├── teammates   → Teammates CRUD + webhook enable/disable
├── runs        → Create (streaming/non-streaming), list, get, cancel, reply
├── tasks       → Tasks CRUD + triggers (schedule, webhook, email)
├── apps        → List tools, manage OAuth connections
├── memories    → Pre-populate end-user memories
├── permissions → Pre-approve tools for end-users
└── webhooks    → Webhook endpoint CRUD + delivery tracking
```

**Key files:**
- `_client.py` — Entry point, initializes all resources
- `_http.py` — Auth, retries (429/5xx), structured error parsing
- `_types.py` — Dataclasses: Teammate, Run, Task, Trigger, App, etc.
- `_exceptions.py` — Typed hierarchy: M8tesError → NotFoundError, AuthenticationError, etc.
- `_streaming.py` — RunStream context manager wrapping SSE parser
- `_resources/` — One module per resource (teammates.py, runs.py, tasks.py, etc.)

**Conventions:**
- All list methods return `ListResponse` with `.data`, `.has_more`, and `.auto_paging_iter()`
- Methods that accept `user_id` map to `end_user_id` internally for multi-tenancy
- Create/update methods accept keyword args matching the V2 API schema
- HTTP errors are parsed into typed exceptions with `.status_code`, `.message`, `.request_id`

## Setup & Daily Commands

```bash
make install                    # Install via uv
make check                      # Ruff + MyPy + pytest
m8tes --help                    # CLI overview
m8tes --dev auth login          # Dev login against localhost API
m8tes --dev mate task "Prep weekly recap"
```

V2 SDK usage (developer):

```python
from m8tes import M8tes

client = M8tes(api_key="m8_...")
bot = client.teammates.create(name="Ops Mate", tools=["gmail"])
for event in client.runs.create(teammate_id=bot.id, message="Close tickets"):
    print(event.type, event.raw)
```

Legacy CLI usage:

```python
from m8tes.client import M8tes as LegacyM8tes

client = LegacyM8tes(api_url="http://127.0.0.1:8000")
mate = client.create_agent(name="Ops Mate", instructions="Close tickets")
for event in client.execute_agent(instance_id=mate.id, task="Close open tickets", stream=True):
    print(event.type, event.payload)
```

## Testing Strategy

- **TDD**: Write failing unit tests around clients/commands before implementation.
- Unit tests mock HTTP + SSE to validate parsing and error handling.
- Integration tests in `tests/integration/` run against a live FastAPI instance.
- **Every new V2 resource or method MUST have integration tests** in `tests/integration/test_v2_integration.py`. Follow existing patterns: try/finally cleanup, `_uid()` for unique user_ids, test both success and error paths.
- Run `make test-integration` with the backend running at localhost:8000 to verify.
- Use `pytest -k streaming` for focused SSE tests; `make check` before sharing work.

### Before Pushing

```bash
make check                    # lint + type-check + tests (must pass)
make test-integration         # requires backend running at localhost:8000
```

## Patterns & Guardrails

- Keep CLI commands thin—delegate to `client.py` methods.
- Emit structured errors (status, code, message, request_id) so users can debug quickly.
- Streaming helpers should return iterables of typed events (`MessageEvent`, `ToolEvent`, `ErrorEvent`).
- Any change to FastAPI payloads must update `types.py` and regenerate documentation/snippets.
- Chat and task are the same flow (both create a Task + Run). Ensure new commands/methods work consistently for both patterns.

## After Every SDK Change

**Always do these after any change to SDK behavior, API surface, or bug fixes:**

1. Add a changelog entry in `CHANGELOG.md` describing what changed and why.
2. Bump the version in `pyproject.toml` following semver (`patch` for fixes, `minor` for new features, `major` for breaking changes).

Skipping these makes it impossible for users to know what version they need or what changed.

## Release Checklist

- Version bump in `pyproject.toml`.
- `CHANGELOG.md` updated with a clear entry for this release.
- `make check` clean, integration suite green.
- CLI help (`m8tes --help`) reflects new commands/flags.

## References

- API documentation: [m8tes.ai/docs](https://m8tes.ai/docs)
- Backend API: [github.com/m8tes](https://github.com/m8tes)
