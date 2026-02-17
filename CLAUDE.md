# SDK CLAUDE.md

Python SDK + CLI that let users create, inspect, and run mates against the FastAPI backend. It wraps authentication, SSE streaming, and typed payloads so every integration sees the same behaviour as the CLI.

## Responsibilities

- Manage auth: API key env (`M8TES_API_KEY`) or stored CLI credentials.
- Provide ergonomic helpers to create mates, run tasks, and start chats.
- Stream Claude Agent SDK events from FastAPI and expose them as Python generators / CLI output.
- Keep payload contracts aligned with FastAPI schemas (generate/update whenever backend changes).

## Structure

```
sdk/py/
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
for event in client.runs.create(teammate_id=bot.id, task="Close tickets"):
    print(event.data)
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
- Integration tests in `tests/integration/` run against a live FastAPI instance for end-to-end coverage.
- Use `pytest -k streaming` for focused SSE tests; `make check` before sharing work.

## Patterns & Guardrails

- Keep CLI commands thin—delegate to `client.py` methods.
- Emit structured errors (status, code, message, request_id) so users can debug quickly.
- Streaming helpers should return iterables of typed events (`MessageEvent`, `ToolEvent`, `ErrorEvent`).
- Any change to FastAPI payloads must update `types.py` and regenerate documentation/snippets.
- Always support both `task` and `chat` modes when adding new mate commands or SDK methods.

## Release Checklist

- Version bump in `pyproject.toml`.
- `make check` clean, integration suite green.
- CLI help (`m8tes --help`) reflects new commands/flags.
- Changelog entry summarizing mate/API changes.

## References

- Backend contract: `fastapi/CLAUDE.md`
- Platform overview: `/CLAUDE.md` and `AGENT.md`
