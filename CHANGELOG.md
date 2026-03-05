# Changelog

All notable changes to the m8tes Python SDK will be documented in this file.

## [1.5.1] - 2026-03-05

### Added
- `teammates.enable_fetchmail(teammate_id)` — enable read-only email inbox; returns `FetchmailInbox` with `enabled` and `address`
- `teammates.disable_fetchmail(teammate_id)` — disable read-only inbox
- `FetchmailInbox` dataclass in `_types.py`
- `Teammate.fetchmail_enabled` and `Teammate.fetchmail_address` fields

## [1.5.0] - 2026-03-02

### Added
- `runs.create(email_inbox=True)` — enable email inbox on the auto-created teammate in one call
- `runs.create_and_wait(email_inbox=True)` — same; the returned `Run` has `email_address` set
- `Run.email_address` — email address for triggering future runs (set when `email_inbox=True` on creation)

## [1.4.2] - 2026-03-02

### Added
- `tasks.create(email_notifications=False)` — disable email on scheduled run completion (default: `True`)
- `tasks.update(task_id, email_notifications=False)` — toggle email notifications on existing tasks
- `Task.email_notifications` — field on the `Task` dataclass reflecting the current setting

## [1.4.1] - 2026-02-28

### Added
- `Task.webhook_enabled` — indicates if webhook trigger is active on `tasks.get()` and `tasks.list()`

## [1.4.0] - 2026-02-28

### Added
- `tasks.create(schedule="0 9 * * 1-5")` — set a cron schedule at creation time (no separate `triggers.create()` call needed)
- `tasks.create(schedule=..., schedule_timezone="America/New_York")` — timezone support for inline schedule
- `tasks.create(webhook=True)` — enable webhook trigger at creation time; `Task.webhook_url` is returned once
- `Task.webhook_url` — webhook URL shown once at creation when `webhook=True`
- `teammates.create(name=None)` — `name` is now optional; auto-generates a random name if omitted
- `client.apps.connect_oauth()` — explicit helper for OAuth app connections
- `client.apps.connect_api_key()` — explicit helper for API key app connections

### Changed
- README and test docs now document `client.runs.update_permission_mode()`, explicit app-connection helpers, and the layered V2 test workflow

## [1.3.0] - 2026-02-28

### Added
- `teammates.create(email_inbox=True)` — enable email inbox at creation time; `Teammate.email_address` is set immediately
- `teammates.create(webhook=True)` — enable webhook trigger at creation time; `Teammate.webhook_url` is returned once
- `Teammate.webhook_enabled` — indicates if webhook is active when fetching a teammate via `teammates.get()` or `teammates.list()`
- `RunStream.run_id` — run ID extracted from the metadata event; available after the first event arrives
- `RunStream.iter_text()` — yields only text chunks from the stream; no event type filtering needed. Use when you need both live output and `stream.run_id` / `stream.text` after iteration
- `App.needs_oauth` — boolean property on `App`; `True` for OAuth integrations (Gmail, Slack, etc.), `False` for API key integrations (Gemini, OpenAI, etc.). Use to pick the right `apps.connect()` branch

## [1.2.0] - 2026-02-28

### Added
- `client.runs.wait(run_id, *, on_approval, on_question)` — wait for a run to complete with human-in-the-loop callback support. Handles `awaiting_approval` pauses inline; raises `RuntimeError` if the run pauses without a callback.
- `client.runs.create_and_wait()` now accepts `on_approval=` and `on_question=` callbacks
- `client.runs.reply_and_wait()` now accepts `on_approval=` and `on_question=` callbacks
- `client.tasks.run_and_wait(task_id, *, on_approval, on_question)` — run a task and wait, with HITL callback support
- `client.apps.is_connected(app_name, *, user_id=None) -> bool` — one-line check for integration connection status
- `client.apps.connect()` now accepts `api_key=` parameter for API key integrations (Gemini, OpenAI, etc.)
- `PermissionRequest.is_plan_approval` — `True` when the request is a plan mode approval pause
- `PermissionRequest.plan_text` — the proposed plan text, extracted from the approval request
- New examples: `examples/plan-mode.py`, `examples/file-report.py`, `examples/embed-oauth.py`

## [1.1.0] - 2026-02-27

### Added
- `m8tes.signup(email, password, first_name)` — create an account and receive an API key without instantiating a client
- `m8tes.get_token(email, password)` — exchange credentials for a new API key (invalidates previous key)
- `client.auth.get_usage()` — returns `Usage` with plan, runs used/limit, cost used/limit, and period_end
- `client.auth.resend_verify()` — resend the email verification link for the authenticated user
- New types exported from `m8tes`: `SignupResult`, `TokenResult`, `Usage`, `Auth`

## [1.0.2] - 2026-02-27

### Added
- `BillingError` exception class for 402 billing limit and subscription errors
- `X-RateLimit-Remaining` and `X-RateLimit-Reset` headers on run creation responses

### Fixed
- Billing limit errors on v2 routes now return the standard error envelope
  instead of the legacy v1 format with root-level `detail`/`status_code` fields

## [1.0.1] - 2026-02-23

### Added
- `M8TES_BASE_URL` environment variable support for `M8tes()` client
- Developer dashboard now shows API key inline (no need to navigate to Account)
- Copy button added to masked API key display in Account settings

### Fixed
- CLI `--api-key m8_...` was broken — V1 agent routes now accept API keys
- CLI shows correct error guidance when API key authentication fails

## [1.0.0] - 2026-02-22

### Added
- Initial stable release of the V2 SDK
- Resource client: teammates, runs, tasks, apps, memories, permissions, webhooks, users
- Streaming support via `RunStream` context manager
- Human-in-the-loop: approval mode, plan mode, `AskUserQuestion`
- Multi-tenancy via `user_id` / `end_user_id`
- Auto-paging iterator for list endpoints
- Typed exceptions: `NotFoundError`, `RateLimitError`, `AuthenticationError`, `ConflictError`

## [0.2.0] - 2026-02-18

### Added
- V2 SDK with resource pattern (`client.resource.method()`)
- Resources: teammates, runs, tasks, apps, memories, permissions, webhooks
- Streaming support via `RunStream` context manager
- Auto-paging iterator for list endpoints
- Multi-tenancy via `user_id` parameter
- Typed exceptions: `NotFoundError`, `RateLimitError`, `AuthenticationError`, etc.
- Automatic retry on 429/5xx with `Retry-After` support
- Task triggers: schedule (cron/interval), webhook, email

## [0.1.0] - 2024-12-01

### Added
- Initial release with CLI and legacy SDK client
- OAuth authentication flow
- SSE streaming for task and chat execution
