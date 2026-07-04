# Changelog

All notable changes to the m8tes Python SDK will be documented in this file.

## [2.1.1] - 2026-07-04

### Fixed
- **`m8tes run get` / `usage` / `conversation` / `tools` and the `mate task` run summary work again.** The legacy run service called four endpoints that don't exist (`/details`, `/conversation`, `/usage`, `/tools`) — every one of these commands died with "Resource not found", and `run get` parsed a nested response shape the API never had. Rewired to the real endpoints: `/detail` (flat aggregated metrics) and `/messages` (transcript); tool calls are now derived from message content blocks (the API tracks no per-call success/duration, so those columns are gone from the output).
- `m8tes google connect --browser` was a silently ignored flag; it now forces auto-open (and wins over `--no-browser`).
- Docstring corrections (no behavior change): `teammates.create(from_template=…)` also allows `default_permission_mode` and `model` alongside `user_id`/`metadata`; `runs.answer` 409s on ANY non-awaiting status (not only terminal); `memories.create`, `users.create`, and `keys.create/rotate` now document their 409/429/403 error cases; `ValidationError` covers 400 as well as 422.

## [2.1.0] - 2026-07-03

### Added
- Managed iMessage (Blooio) provisioning: `client.bridges.provision_blooio(number, api_key=None, user_id=None)` connects a dedicated Blooio iMessage number to your account (registers the inbound webhook, stores the encrypted key/secret). `Bridge` now exposes `provider_number` (the connected number). Bring your own Blooio account with `api_key`, or bind a line to an end-user with `user_id`.

## [2.0.0] - 2026-07-03

### Removed
- **BREAKING**: `client.settings.update(company_research=...)` and `AccountSettings.company_research`. The background company-research pipeline was removed — company context is now researched agentically by the Company Agent (platform product) or set directly on the profile. Remove the kwarg/field from your code; all other settings (`retention_mode`, per-end-user sub-caps) are unchanged.

## [1.26.2] - 2026-07-03

### Fixed
- `runs.reply(...)` docstring corrected: a follow-up continues the **same** run (re-opens it, keeps context, no new run-count slot) — it does not create a new run. Docs-only; behavior is unchanged.

## [1.26.1] - 2026-07-02

### Added
- `client.teammates.get/update/delete(...)` and `client.tasks.get/update/delete(...)` accept `user_id` — scope a by-id operation to one end-user. The server now enforces it: a mismatched or account-level resource 404s (mirroring the list filter), so a multi-tenant integration can't reach another end-user's teammate/task by id. Omit `user_id` for the account-operator view (unchanged).

## [1.26.0] - 2026-07-02

### Added
- Single-use hosted iMessage link codes: `client.bridges.regenerate_link_code(bridge_id, single_use=True)` issues a one-shot code consumed on the first phone that links (the safest way to hand a code to one person on the shared m8tes number); the default stays multi-use for team onboarding. `Bridge` now exposes `link_code_single_use`.
- `client.tasks.enable_webhook(task_id)` / `client.tasks.disable_webhook(task_id)` — enable, disable, or rotate a task's webhook trigger (parity with the teammate methods). Previously a task webhook could only be created; a leaked `whk_` URL kept starting billable runs until the task itself was deleted. Calling `enable_webhook` again rotates the token, invalidating the previous URL.

### Changed
- CLI help copy: `m8tes --help` now reads "m8tes SDK - Ship agents. Skip the infrastructure." and the `mate` group reads "Manage teammates" (dropped the off-voice "AI teammates").

### Fixed
- `m8tes task ...` and `m8tes run ...` now work with API-key auth. The backend's v1 task/run endpoints (which the CLI uses) were JWT-only and rejected every `m8_` key — `m8tes task list` failed "Invalid API key" with a valid key while `mate list` worked. (Server-side fix; ships with the same release.)
- `m8tes auth status` no longer reports a valid API key as invalid — and no longer deletes the saved keychain token on that false positive. It probed the JWT-only legacy `/api/v1` user endpoint, which rejects every `m8_` key; it now validates against the v2 API (`GET /verify/status`) and reports the email-verified state. A status command never mutates credentials.
- `m8tes auth usage` no longer crashes with "Unknown format code 'f'" — `cost_used`/`cost_limit` arrive as decimal strings and are now converted before formatting.
- CLI failure paths now always exit non-zero. Previously several interactive helpers printed the error and swallowed it, so the command exited 0 — `m8tes mate list && deploy` would proceed on an auth failure. Affected: `mate list/get/create/update/enable/disable/archive/task/chat`, `task list/get/create/execute/update/enable/disable/archive`, and `auth login/register`. A run that finishes with streamed errors (`mate task`, `task execute`) now also exits 1. Non-numeric IDs raise a clear `ValidationError` ("Teammate ID must be a number, got 'abc'") instead of being swallowed after a raw `int()` error message.

## [1.25.0] - 2026-06-29

### Added
- `client.models.list()` — discover the models you can pass as `model` (on a teammate or a run), with their USD price per million tokens, instead of hardcoding an alias. Each `Model` has `id` (the alias to pass), `name`, `description`, `provider` (`anthropic`/`openai`/…), `default` (used when `model` is omitted), and `pricing` (`input_per_mtok` / `output_per_mtok` / `cache_read_per_mtok` / `cache_write_per_mtok`). **Today the list is `sonnet` + `opus`; more (non-Anthropic + open-source) appear here as they go live** — `model` stays a plain string, so no SDK change is needed.
- One-click m8tes-hosted iMessage: `client.bridges.provision()` connects Apple Messages without running your own BlueBubbles server — m8tes hosts it. The returned `bridge.m8tes_handle` is the number your users text and `bridge.link_code` is the code each user texts once to link their phone (inbound routes by verified handle). Manage linked handles with `client.bridges.list_handles(bridge_id)` / `remove_handle(bridge_id, handle_id)`, and rotate the code with `regenerate_link_code(bridge_id)`. `Bridge` now exposes `kind` ("hosted" | "self_hosted"), `m8tes_handle`, `link_code`, and `link_code_expires_at`; new `HandleLink` type. The existing `bridges.create(...)` (bring-your-own-server) is unchanged. `provision()` raises if the platform's central server isn't configured (HTTP 503).

## [1.24.0] - 2026-06-23

### Added
- `AppTriggerType` (from `client.apps.list_triggers(app)`) now exposes `payload` — the JSON schema of the event data a trigger delivers when it fires — so you can reference event fields when writing task instructions, alongside the existing `config` (the setup schema).
- Self-improving teammates: `client.teammates.create/update(...)` accept `enable_self_improvement`. When true, the teammate runs a weekly review-and-improve task — it reads its own recent runs and improves itself: rewriting its instructions, refining/creating its tasks, and recording lessons and memory. Reversible self-edits apply autonomously; destructive moves (disabling a task, connecting an integration) are surfaced for human approval. Enabling it implies the task-setup, history, and memory tools. `Teammate` now exposes the field. Multi-tenant safe — the review stays within the teammate's `user_id` scope.
- `signup(...)` / `signup_and_wait(...)`: `password` is now optional and there's a new `product` arg ("api" or "platform"). Omit `password` for a passwordless, agent-created account — m8tes emails the person a link to set their own password and activate, and the returned key is setup-only until then (revoked on activation). This is the recommended flow when an agent onboards a human: the agent never holds a login credential. `product="platform"` provisions the team product (Company Agent + onboarding); `product="api"` (default) the developer product.

### Changed
- An unverified account now gets a small preview-run allowance before email verification is required (previously API signups were blocked at 0 runs), so a delegated agent can get started before the human activates. Backward compatible: existing `signup(email, password, first_name)` calls work unchanged.

## [1.23.0] - 2026-06-23

### Added
- Slack inbound: `client.teammates.create/update(...)` accept `inbound_slack_enabled`, `slack_slug` (the `@m8tes <handle>` keyword), and `allowed_slack_senders`. Give a teammate a handle and your team triggers it from any Slack channel; replies in-thread continue the run. Enabling without a handle returns `422`; a duplicate handle returns `409`. `Teammate` now exposes all three fields. (Email and iMessage already had this; Slack was the missing inbound channel.)
- `client.tasks.create/update(...)` accept `enable_lessons` — toggle whether a task's teammate accumulates self-improvement lessons across its runs (task-level, default on).

### Changed
- `client.tasks.update(...)`: the four `enable_*` built-in tool defaults now reset to inherit-from-teammate when passed `None` (sends JSON null), matching `teammates.update`. Omit to leave unchanged; pass True/False to pin.

## [1.22.0] - 2026-06-22

### Added
- Built-in tool discovery: `client.built_in_tools.list(teammate_id=..., user_id=...)` enumerates the platform's own tools (memory, task history, task setup, feedback, notify, Slack DM, computer use, and more) with each one's resolved `enabled` state, `multi_tenant_safe` flag, and whether it's `configurable`. These tools are NOT passed in the `tools=[...]` array. New `BuiltInTool` type.
- Teammate- and task-level defaults for the four configurable built-in tools: `client.teammates.create/update(...)` and `client.tasks.create/update(...)` accept `enable_memory`, `enable_history`, `enable_task_setup_tools`, and `enable_feedback`. A teammate's default now applies to every run of that teammate — including scheduled, webhook, and inbound runs — unless a task or run overrides it. `Teammate` and `Task` expose all four fields.

### Changed
- The four built-in tool toggles on `runs.create(...)` and `tasks.run(...)` (`memory`, `history`, `task_setup_tools`, `feedback`) now default to `None` (inherit the task/teammate default) instead of `True`. Omitting them previously forced the tools on for that run; they now resolve `run > task > teammate > platform default (enabled)`. Pass `True`/`False` explicitly to force a per-run override. Behavior is unchanged for teammates with no configured default.
- `client.teammates.update(...)`: passing `enable_memory=None` (or any of the four) now resets that toggle to the platform default (inherit), mirroring how `model=None` clears to the default. Omit the argument to leave it unchanged.

## [1.21.0] - 2026-06-22

### Added
- `RunStream.errors` / `RunStream.has_errors` and a `raise_on_error=True` option on `client.runs.create(...)`: a streaming run that fails mid-flight (expired credential, model rate limit, quota) no longer looks like a successful empty response. With `raise_on_error=True` the stream raises the new `RunFailedError` (carrying `.details["errors"]`) once iteration ends; otherwise check `stream.has_errors` after iterating.
- `client.runs.stream(run_id)`: join an in-progress run's live SSE stream to reconnect/resume after a dropped connection. Capture `run_id` from a `create(...)` stream's metadata event, then `stream(run_id)` to re-attach — it replays the run's full history then streams live deltas (reset local accumulation on reconnect). 409 if the run is no longer executing — use `get(run_id)` for the result. The server now also emits a 15s keepalive on the streaming path so a long-silent tool call doesn't trip the SDK read timeout.

### Fixed
- POST requests are no longer retried on a timeout / connection error. A `POST /runs` that times out may have already started a billable run server-side, so the connection-layer retry now honors the same `_SAFE_RETRY_METHODS` guard as the 5xx path and fails fast instead of re-POSTing (which could create duplicate billable runs). GET/HEAD/PUT/DELETE still retry.

## [1.20.0] - 2026-06-20

### Added
- Named / multiple API keys on `client.keys`: `create(name=..., expires_in_days=...)` mints a separately-revocable key (the secret is returned ONCE), `list()` returns every managed key (prefix/created/last-used/expiry/active — never the secret), and `rotate(key_id)` / `revoke(key_id)` operate on a single named key by id (the no-arg `rotate()` / `revoke()` still manage the account's default key). New `ApiKeyCreated` / `NamedApiKey` types. Useful for per-environment (prod/staging/CI) keys you can rotate independently without breaking the others.

## [1.19.0] - 2026-06-20

### Added
- Per-end-user (multi-tenant) sub-caps on `client.settings`: `per_end_user_run_limit` and `per_end_user_cost_limit_cents` cap each end-user's monthly runs / metered cost so one end-user can't drain your account budget (set an int, `None` to clear, or omit). Exceeding a cap fails the run with `402` (`END_USER_RUN_LIMIT_REACHED` / `END_USER_COST_LIMIT_REACHED`). `AccountSettings` exposes both fields.
- `client.keys` for API key hygiene: `rotate()` (returns a fresh key; the old one dies immediately), `revoke()` (ends API-key access), `info()` (masked prefix). Both mutations are audit-logged. New `ApiKeyInfo` / `ApiKeyRotated` types.
- Zero data retention: `client.settings.update(retention_mode="metadata_only")` switches the account to a no-store mode — m8tes never persists conversation content, tool I/O, model reasoning, run output, or generated reports; only metadata (token/cost metrics, tool names, status) survives. Surfaced on `AccountSettings.retention_mode`. (Governs what *we* store; upstream Anthropic zero-retention is a separate org-level agreement.)

## [1.18.0] - 2026-06-19

### Added
- iMessage bridges: `client.bridges.create(...)` accepts `owner_handle` (your own iMessage phone/email) so you can text your Company Agent right away without editing an allowlist. `Bridge` now carries `owner_handle`, and the create result carries `connection_ok` / `connection_error` from a one-shot reachability check run at registration.
- `client.bridges.test(bridge_id)` — pings the bridge's BlueBubbles server (no message sent) and returns `{"ok": bool, "detail": str | None}` to debug a bridge that isn't receiving or sending.

### Notes
- iMessage 1:1 chats now have bounded-context conversation continuity (a follow-up within 72h resumes the same run; group chats are rejected) — server-side, no SDK change required. See the iMessage Inbox docs.

## [1.17.0] - 2026-06-20

### Added
- Configurable prepaid low-balance warnings: `client.billing.set_alert_threshold(low_balance_threshold_cents=...)` sets the balance at which the low-balance warning fires (the critical tier is 20% of it; 0 warns only on depletion) and returns the refreshed `Balance`. `Balance` now exposes `low_balance_threshold_micros` and `critical_balance_threshold_micros`. Warnings are delivered both by email and as new `balance.low` / `balance.critical` / `balance.depleted` webhook events, so a developer's production systems can react before runs start failing. Backend-gated by `prepaid_billing_enabled`.

## [1.16.0] - 2026-06-20

### Added
- `client.memories.list(user_id=..., query="...")` keyword-filters an end-user's memories by content (case-insensitive substring). The filter is scoped to that end-user and pagination applies to the filtered set; omit `query` for the full list.

## [1.15.0] - 2026-06-19

### Added
- `signup_and_wait(...)` — create an account, then block until the user clicks the one-tap activation link m8tes emails them, and return the `SignupResult`. Onboards a user end to end in one call; raises `TimeoutError` if they don't activate in time.
- `client.auth.is_verified()` — poll whether the account has verified its email (API accounts can't run until verified). Backed by the new `GET /api/v2/verify/status`.
- `SignupResult.verification` — `"pending"` until the user activates, then `"verified"`. Backward-compatible default for older backends.

### Security
- The activation link is emailed to the user and is never returned to the API caller, so a key holder (e.g. a third-party agent onboarding its user) cannot obtain a login-as-the-user link. `signup_and_wait`/`is_verified` only observe activation status.

## [1.14.0] - 2026-06-19

### Added
- Prepaid token balance for the API/developer product: `client.billing.balance()` returns your `Balance` (micro-USD `balance_micros`, a rounded `balance_usd`, currency, and recent `TokenTransaction` ledger entries), and `client.billing.topup(amount_cents=...)` starts a Stripe Checkout and returns a URL to send the buyer to (the balance is credited once payment completes). New `Balance` and `TokenTransaction` types. Backend-gated by `prepaid_billing_enabled` (off until prepaid billing is enabled).

## [1.13.0] - 2026-06-16

### Added
- `client.billing` resource for self-metering spend: `billing.usage()` (same as `auth.get_usage()`, now with overage fields), `billing.plans()` (the public plan catalog — `pro`/`max_5x`/`max_20x` with display names, included runs, monthly/annual price, overage rate), and `billing.set_overage(enabled=, monthly_cap_cents=)` to opt in/out of usage overage and set a monthly spend cap. New `Plan` type.
- `Usage` now carries opt-in overage state: `overage_enabled`, `overage_used_cents`, `overage_cap_cents`, `overage_rate_cents`, and `trial_ends_at` (all backward-compatible defaults; tolerant of older backends that omit them).
- `BillingError` (and every SDK error) now exposes `.details` — the full `error.details` object with actionable fields like `runs_used`, `runs_limit`, `overage_cap_cents`, `period_end`, and `trial_ends_at`.

### Fixed
- **`BillingError.code` was always `None`.** The backend nests the machine-readable code in `error.details.error_code` (the top-level `error.code` is the int HTTP status), but the SDK only read the top level. A `402` now correctly surfaces `exc.code == "RUN_LIMIT_REACHED"` / `"OVERAGE_CAP_REACHED"` / `"TRIAL_EXPIRED"`. Top-level string codes (e.g. `retry_needs_confirmation`) still work as a fallback.
## [1.12.1] - 2026-06-17

### Added
- `client.mcp_servers.create(..., auto_approve=True)` and `.update(id, auto_approve=...)` — mark a custom tool **trusted** so it runs unattended (skips the per-call approval gate) in scheduled/webhook/API runs. Defaults to `False` (a tool pauses for approval until trusted). `McpServer.auto_approve` is returned on every response.

## [1.12.0] - 2026-06-16

### Added
- `client.account.delete()` — request deletion of the current account. Soft-delete: the account is deactivated immediately (sessions and API key revoked, billing canceled, automation stopped) and its data is erased after a grace period.
- `client.account.export()` — export all of the current account's data (GDPR/CCPA right to access): profile, teammates, tasks, runs, documents, memories, and integration metadata. Secrets are never included.

## [1.11.0] - 2026-06-16

### Added
- `client.mcp_servers` — register your own REST endpoints as custom agent tools (BYO tools). `create()` takes `name`, `url`, typed `tool_defs` (name/method/path/arg_schema), an `auth_type` (none/bearer/custom_header/api_key_in_url/oauth_token) and a write-only `secret`; plus `list()`, `get()`, `update()`, `delete()`. New `McpServer` type (the auth secret is never returned — `has_secret` reports whether one is stored). Egress runs server-side, IP-pinned, with the secret injected and never exposed to the agent. Attach a server to a teammate by passing its `.slug` in `teammates.create/update(tools=[...])`.

## [1.10.0] - 2026-06-14

### Added
- `client.teammate_templates.list()` — the pre-built teammate template catalog (slug, name, role, required integrations, default tasks). Use a returned `.slug` with `teammates.create(from_template=...)` instead of hardcoding it. New `TeammateTemplate` type.
- Task lesson curation on the Tasks resource: `tasks.lessons(task_id)`, `tasks.delete_lesson(task_id, lesson_id)`, and `tasks.clear_lessons(task_id)` — read, prune, and reset what a task's teammate has learned across runs. New `Lesson` and `LessonList` types. (`clear_lessons` sends the backend's required `confirm=true`.)

### Fixed
- Collection calls (`runs`, `tasks`, `teammates`, `memories`, `permissions`, `users`, `webhooks`, `apps`, `audit-logs`, `usage`, `settings`, and task `triggers`) now request the canonical trailing-slash URL directly. Previously every list/create hit a `307` redirect — an extra round-trip, and a latent failure mode where a proxy that dropped the request body or `Authorization` header on the redirect would break `POST` creates.
- Examples `revenue-report.py`, `seo-monitor.py`, and `support-triage.py` called `tasks.create()` without the required `instructions=` (an immediate `TypeError`). `file-report.py` passed a non-existent `stream=` kwarg to `create_and_wait` and read `event.tool_input` off `tool-call-start`, which doesn't carry it — both now fixed.

### Docs
- README resource table now lists previously-undocumented shipped methods: the `client.bridges` resource, `apps.provision`/`release`/`list_triggers`, `runs.retry`, `teammates.reset`, plus the new `teammate_templates` and task-lessons surfaces.
- Documented run-level failure detection: a run can return `status="completed"` with an upstream failure in `run.output` and a machine-readable `run.error_code` (e.g. `oauth_revoked`, `subscription_quota_exhausted`, `rate_limited`); check `error_code` before trusting `output`.

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
