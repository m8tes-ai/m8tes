# Changelog

All notable changes to the m8tes Python SDK will be documented in this file.

## [1.9.2] - 2026-06-13

### Added
- `RateLimitError.retry_after` (a field on every `M8tesError`, set on 429s) — the `Retry-After` header parsed to seconds, so you can back off precisely instead of guessing. `None` when the response carried no such header. This also makes the rate-limit example in the README run as written.

### Fixed
- Packaging and community metadata: added an `Issues` URL to the project metadata (so the PyPI sidebar links to the bug tracker), a `SECURITY.md`, and an issue-template `config.yml`; corrected the `CONTRIBUTING.md` clone URL and bug/feature-request links, which pointed at a repository that does not exist.

## [1.9.1] - 2026-06-11

### Added
- `Run.auto_retry_count` and `Run.next_retry_at` fields — observability for scheduled-run auto-retry (the backend has returned these since the auto-retry feature shipped; the dataclass was missing them).

### Fixed
- Default `base_url` now points at `https://api.m8tes.ai/api/v2` (was `https://m8tes.ai/api/v2`). The apex host redirects to the marketing site, so `M8tes()` without an explicit `base_url` failed every request with a `NotFoundError` containing an HTML page. Same fix for module-level `m8tes.signup()`/`m8tes.get_token()` and the legacy v1 client used by the CLI. If you worked around this with `M8TES_BASE_URL` or `base_url=`, your override still wins.
- HTML error responses (e.g. a wrong base_url host answering with a web page) now raise a clear "check your base_url" message that names the URL that answered, instead of dumping the raw HTML document into the exception text.

## [1.9.0] - 2026-06-04

### Added
- `client.runs.retry(run_id, confirm=False)` — retry a failed or cancelled run. Creates and returns a NEW run (poll the returned `.id`, not the original) linked to the one it retried. Idempotent while a retry is in flight. If the run already performed actions, raises `ConflictError` (code `retry_needs_confirmation`); pass `confirm=True` to proceed.
- `Run.retryable`, `Run.error_code`, `Run.retry_of_run_id`, `Run.retry_count` fields on the `Run` dataclass — check `run.retryable` before retrying.
- CLI: `m8tes run retry <id>` (alias `rerun`), with `--confirm`.

### Fixed
- SDK exceptions now preserve the v2 envelope's app-level string `code` (e.g. `run_not_retryable`) on `error.code`, instead of dropping it.

## [1.8.0] - 2026-05-28

### Added
- Apple Messages (BlueBubbles) channel via per-account bridges. Configure a `BlueBubblesBridge` for the account (server URL, password, webhook secret), bind a teammate to a chat with `inbound_imessage_enabled=True` + `imessage_chat_guid="..."`, and the teammate auto-replies after each run.
- `teammates.update(teammate_id, inbound_imessage_enabled=..., imessage_chat_guid=..., allowed_imessage_senders=[...])` — enable or reconfigure iMessage on an existing teammate, including a sender allowlist.
- `Teammate.inbound_imessage_enabled`, `Teammate.imessage_chat_guid`, `Teammate.allowed_imessage_senders` fields on the `Teammate` dataclass
- CLI: `m8tes mate task` now shows iMessage channel indicator; `m8tes mate config` supports `--imessage-chat-guid` flag
- New example [`imessage-bluebubbles.py`](./examples/imessage-bluebubbles.py) — full end-to-end setup walkthrough

## [1.7.0] - 2026-05-28

### Added
- `client.apps.provision("twilio", user_id="cust_123")` — provision a platform-managed resource (a dedicated Twilio phone number) for the account or a specific end-user. Returns `AppProvisionResult` with `phone_number`. For apps with `auth_type='platform_provisioned'`.
- `client.apps.release("twilio", user_id="cust_123")` — release a provisioned resource back to the provider (semantic alias of `disconnect()` for platform-provisioned apps).
- `AppProvisionResult` dataclass in `_types.py` (exported from the package root).
- Per-end-user numbers are strictly isolated at run time: a run scoped to `user_id` only ever sees that end-user's number, never the account-level one.

## [1.6.0] - 2026-05-20

### Added
- `client.teammates.create(from_template="ppc-manager")` — enable a verticalized teammate template (PPC Manager for Google Ads is the first). Other body fields except `user_id` + `metadata` may not co-exist; backend rejects them with 400 `from_template_conflict`. The teammate stays linked to the template via `template_slug`; future improvements we ship to the template flow through automatically to fields the user hasn't customized.
- `client.teammates.reset(teammate_id, fields=[...])` — clear customer overrides on a template-linked teammate, re-enabling automatic propagation of template defaults for the named fields. `fields=None` resets every override. Non-templated teammates return an empty list (nothing to reset).
- Integration tests covering from_template enable (happy path + 400 missing integration), conflict rejection (400 from_template_conflict), 404 on unknown slug, and reset semantics on both linked and unlinked teammates.

## [1.5.2] - 2026-03-19

### Added
- `examples/reddit-outreach.py` — Reddit community engagement + Google Sheets tracking example; configure `SPREADSHEET_ID` and `TARGET_AUDIENCE`, run outreach sessions that log each comment to a tracking sheet

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
