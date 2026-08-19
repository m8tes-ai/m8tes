# Changelog

All notable changes to the m8tes Python SDK will be documented in this file.

## [Unreleased]

### Added

- **`RunOutcome.delivery_channel` and `RunOutcome.needs_reply_count`** — mirror
  `GET /runs/{id}/outcome` after agentic scheduled delivery (`set_run_delivery`).
## [4.10.0] - 2026-08-19

### Added

- `client.agents.update(..., visibility="organization")` can share an agent with its organization.

## [4.9.1] - 2026-08-19

### Changed

- **`runs.get` / `poll` / `wait` / `create_and_wait` / `reply_and_wait` /
  `cancel` forward `user_id`.** Strict multi-tenant mode requires `?user_id=`
  on every by-ID GET and on cancel; `create_and_wait` / `reply_and_wait` /
  `tasks.run_and_wait` fall back to the response's stamped `user_id` when the
  caller omitted it (agent-inherited scope). When both are present, poll prefers
  the stamped owner.

### Changed

- **`signup()` docstring and README install pin tell the real funding story.** New
  accounts start at $0 (fund before the first run); the 25-run preview is a
  verification gate on *funded* runs, not free credit. Install pin is now
  `m8tes>=4.8` (was `>=3.2`) so `MockM8tes` and `exc.error_code` are in range.
### Added

- **`Usage.unlimited_runs`** — mirrors `GET /api/v2/usage` so clients can tell when
  run/cost gates are bypassed (internal/test accounts).
- **`SyncPage.next_starting_after`** — cursor from the list envelope for the next
  `starting_after` page request.
- **`client.apps.connections.list(app_name, user_id=...)`** — list connection status,
  provider connection ID, account label, scopes, and update time without exposing internal
  database IDs. `App.logo_url` now carries catalog display metadata.

## [4.9.0] - 2026-08-18

### Added

- **`PermissionRequest.remember_default`** — `False` when the "always allow" control
  should start unticked (force-ask floor: spend, access, destroy). The control stays
  available; the default is opt-in per click. Defaults to `True` for older servers.
- **`PermissionPolicy.source`** — which surface minted a standing grant
  (`"run_approval"` / `"api"`; `None` on rows created before provenance existed).
- **`client.github_app.setup_url(org=…, name=…)`** — create your own GitHub App via
  GitHub's App Manifest flow (browser URL). **`complete_setup(ticket=…)`** binds the
  credentials after GitHub redirects with a claim ticket, then returns the install URL.
- **`client.github_app.clear_identity()`** — remove own-App credentials after disconnect
  (revert to the m8tes GitHub App).
- **`GitHubAppStatus.branded` / `app_slug` / `setup_pending`** — whether the account
  uses its own App vs the m8tes GitHub App.

## [4.8.1] - 2026-08-17

### Fixed
- Classify runtime `permission_auto_allowed` as an internal stream type so SDK
  consumers no longer see a spurious "Upgrading the m8tes SDK may add support"
  warning for the platform Auto · timeline annotation.

## [4.8.0] - 2026-08-16

### Added

- **`client.github_app`** — status, install_url, claim, list_repos, disconnect for m8tes Code.
- **`client.agents` repo methods** — list_repos, configure_repo, approve_repo_commands,
  clear_repo_commands, remove_repo.
- **`user_id` end-user scoping on every sub-resource method.** `agents.reset /
  enable_webhook / set_webhook_enabled / disable_webhook / enable_email_inbox /
  disable_email_inbox / enable_fetchmail / disable_fetchmail`, `tasks.enable_webhook /
  set_webhook_enabled / disable_webhook`, and `tasks.triggers.create / list / update /
  delete` all accept `user_id=` and send it as the query param the API enforces
  (404 on mismatch, like the by-id methods). Previously these methods could not
  stay inside an end-user scope at all.
- **`client.mcp_servers.create(..., kind="script", script_source=...)`** —
  persist a Python custom tool. Source is write-only; the response carries
  `script_sha256` and `script_allowlist`. `user_id` is rejected on `kind=script`.
  `PermissionRequest.script` carries origin + sha256 on the create gate (never the source).
- **`client.model_connections.complete_authorization("gemini", state, code=...)`** —
  paste-code completion for Gemini CLI OAuth. `authorize("gemini")` starts the Google
  PKCE session (`user_code` is null); list/disconnect treat `gemini` as a first-class
  provider alongside Claude, Codex, and Grok.
- **`m8tes.testing`** — test your integration offline, with no spend and no side
  effects. `MockM8tes` (or `MockTransport().install(client)`) answers the SDK's
  real HTTP client from registered fixtures, so request building, retries, typed
  error mapping, and SSE parsing are all the production code paths.
  `agent_payload` / `run_payload` / `task_payload` / `page_payload` build
  realistic v2 wire payloads; `StreamBuilder` builds SSE streams the SDK's own
  parser consumes (including failure streams with a semantic `error_code`);
  `error_envelope` builds v2 error responses for exception-path tests. Zero
  extra dependencies. Recorded headers are credential-redacted (`Authorization`
  is never retained verbatim — `install()` mounts on clients holding real
  keys), and a query string on a fixture makes it query-aware: the request
  must send those params, so a tenant-isolation test fails when code drops
  `user_id` instead of silently matching; `RecordedCall.params` carries the
  parsed query for assertions.
- **`exc.error_code`** on every SDK exception — the semantic error code (e.g.
  `RUN_LIMIT_REACHED`, `TOKEN_BALANCE_DEPLETED`), read from the envelope's
  top-level `error.error_code` (newer backends) with fallback to
  `error.details.error_code` (current backends). Branch on it instead of
  parsing messages; `exc.status_code` stays the int HTTP status.

### Changed
- **`signup()` docstring now states the funding model correctly.** Runs are
  prepaid: a new account starts at $0, so top up (https://m8tes.ai/developer) or
  connect a model subscription before the first run — an unfunded run fails with
  `TOKEN_BALANCE_DEPLETED` and a `topup_url`. The old wording framed the
  email-verification allowance as free funding; verification and funding are
  separate gates (the verification threshold is stated by the docstring and may
  change server-side — 25 completed runs at time of writing).
- **`CONTRIBUTING.md` matches the actual contribution path** (issues +
  support@m8tes.ai; the repo is synced from an internal monorepo and doesn't
  take external PRs), and `SECURITY.md`'s supported-versions table was replaced
  with version-agnostic prose so it can't drift again.
- **CLI finishes the agent-era vocabulary sweep.** `m8tes run list-mate` is now
  `m8tes run list-agent` (old spellings `list-mate`/`lm` keep working as
  unadvertised aliases), user-visible positionals say `agent_id` (not
  `mate_id`), and subcommand group help (`m8tes agent --help`, `m8tes run
  --help`, …) gets the same clean `<subcommand>` treatment the top level got —
  no more raw `{create,c,list,ls,...}` choice dump.

### Removed
- **The repo's own CodeQL workflow.** GitHub's default-setup code scanning has
  owned this repository since day one and rejects SARIF from committed CodeQL
  workflows by design ("analyses from advanced configurations cannot be
  processed when the default setup is enabled"), so the committed workflow
  failed on every push — 78 runs, zero successes — while default setup already
  scans a superset (Python + Actions) on every push. Do not re-add a
  `codeql.yml` here while default setup is enabled.

## [4.7.1] - 2026-08-16

### Added
- **`Run.closing_preview`.** Short board/list card excerpt of the run's closing
  message (HEADLINE preferred, else marker-stripped latest prose). Null when
  there is nothing scannable.

## [4.7.0] - 2026-08-15

### Added
- **`client.model_connections.apply_default(provider)`** — set a connected model
  plan as the account default for platform mates with no explicit model.

## [4.6.1] - 2026-08-15

### Added
- **`Memory.created_by_agent_instance_id`.** Which Mate wrote a memory, distinct from
  `agent_instance_id` (visibility). Account-wide agent-saved facts keep
  `agent_instance_id=None` so every Mate reads them, but still name their author.

## [4.6.0] - 2026-08-13

### Added
- **`client.channels` GitHub App identity.** `list()` now returns Slack and GitHub.
  `upsert_identity(channel="github", github_app_id=..., github_app_slug=...,
  github_private_key=...)` stores a white-label GitHub App (OAuth client + webhook
  secret + PEM). `install_links()` includes `github.install_url` when GitHub is
  configured (the call still 503s if Slack is unavailable). Secrets are never
  returned.

### Changed
- **`Channel` field order.** `webhook_url` was inserted before `identity_id` /
  `client_id`. Keyword construction is unchanged; positional `Channel(...)`
  callers from 4.5.0 should switch to keywords.
## [4.5.0] - 2026-08-13

### Added
- **`client.channels`** — list Slack channel identity, mint Add-to-Slack
  install links (`install_links(user_id=...)`), and store a white-label Slack
  app (`upsert_identity`). Accounts with no identity keep the shared `@m8tes`
  app. `user_id` on install-links is strict-mode bookkeeping only — it does
  not stamp the workspace install.
## [4.4.0] - 2026-08-13

### Added
- **`billing.usage_timeseries(settled_meter=...)`** scopes the series to where a run
  actually settled: `"wallet"` (prepaid ledger), `"plan"`, `"released"`, or `"own_sub"`.
  `surface=` is still creation intent; pass both when you want embedding work that hit
  the wallet (`surface="api", settled_meter="wallet"`).
- **`slack_channels` on create/update/read.** Bind a Mate to Slack rooms so `@m8tes`
  in those channels reaches it. Unbound channels and DMs still reach the Company
  Agent — there is no typed `@m8tes ppc` handle. Pass `[]` to unbind.

## [4.3.0] - 2026-08-12

### Added
- **`client.model_connections`** — list account model plans, start and poll native
  OpenAI/Codex or xAI/Grok device authorization, and disconnect a provider. Runs can now
  use Claude, Codex, or Grok subscriptions through the same typed SDK surface.

## [4.2.0] - 2026-08-11

### Added
- **`apps.list_tools("github")`** — the tools an app exposes, each labeled `read_only`
  and `approval_mode` (`never`, `depends_on_input`, or `always`).
  Returns the standard `SyncPage[AppTool]`; inspect its `.data` and `.has_more` fields.
  The twin of `apps.list_triggers`: triggers are what wake an agent up, tools are what it
  may then call. Side effects and approval are separate, and a tool's approval verdict can
  depend on its input. A call that may mutate, mint access, or spend money is never labeled
  read-only, even when its vendor metadata or read-shaped name says otherwise. Together the
  two calls answer
  "what can this app do, and which parts of it need me?" before you connect it.
## [4.1.0] - 2026-08-11

### Added
- **`agents.set_webhook_enabled(agent_id, enabled=...)`** — pause or resume a mate webhook
  WITHOUT rotating its token, so the URL you already gave an external system keeps working.
  Previously the only way to stop one was `disable_webhook()`, which destroys the token: to
  pause for an afternoon you had to mint a new URL afterwards and re-distribute it. Matches
  `tasks.set_webhook_enabled`, and the three verbs now mean the same thing on both
  resources — POST mints or rotates, PATCH pauses, DELETE revokes.

### Changed
- **A mate read now tells you whether a webhook exists.** `webhook_url` on an agent used to
  be null on every read (it was returned once, at creation), which made "does this agent
  have a webhook?" unanswerable through the API — and answering it wrong is expensive,
  because the natural fallback is to mint a token over the one already in use. Reads now
  carry the MASKED url; the live token is still shown exactly once.

## [4.0.0] - 2026-08-11

### Changed

- **BREAKING: `Trigger.id` is a string, and `tasks.triggers.update()` / `.delete()` take
  `trigger_id: str`.** Ids are namespaced by trigger type — `schedule_5`, `app_5`, and
  `webhook` / `email` for the two a task has at most one of.

  This is a correctness fix, not a cosmetic one. A task's schedules and its Composio app
  triggers live in separate tables with independent id sequences, so `schedule_5` and
  `app_5` both existed routinely and both used to be published as `5`. `update()` and
  `delete()` resolved that by trying schedules first — so deleting an app trigger by the
  id `list()` had just handed you deleted your **schedule** instead, returned 204, and
  told you nothing.

  **Migration:** pass back whatever `list()` gave you and you are done. If you stored a
  bare integer, prefix it with the type it was: `f"schedule_{n}"` or `f"app_{n}"`. A bare
  id is now refused with a 422 that names the format — deliberately, since the alternative
  is the server guessing which of two triggers you meant.

  ```python
  for t in client.tasks.triggers.list(task.id):
      print(t.id)                                    # -> "schedule_5", "app_5", "webhook"
  client.tasks.triggers.update(task.id, "schedule_5", enabled=False)
  client.tasks.triggers.delete(task.id, "app_5")
  ```
## [3.2.0] - 2026-08-11

### Added
- **`runs.stream_text(..., raise_on_error=True)`** — raises `RunFailedError` when the run
  failed, instead of returning quietly. Off by default, so nothing existing changes.
  **The docs quickstart now passes it, so this release is what makes the documented
  snippet runnable.** Worth setting: `stream_text` yields only text deltas, so an error
  frame is not among the things it yields — without the flag a run that fails outright
  produces zero chunks and your `for` loop exits normally (indistinguishable from a
  successful empty answer), and a run that fails midway leaves a truncated reply that
  reads as complete. Note the check runs after the stream is exhausted, so `break`-ing
  out early skips it.
- **15 new `StreamEventType` members you can match on** instead of receiving as `unknown`:
  `PERMISSION_REQUEST`, `PERMISSION_RESOLVED`, `AWAITING_APPROVAL`, `CANCELLED`,
  `SDK_ERROR`, `AGENT_RUNNER_DIED`, `SANDBOX_BOOT_TIMEOUT`, `SANDBOX_QUOTA_EXHAUSTED`,
  `SANDBOX_UNAVAILABLE`, `SNAPSHOT_VERSION_MISMATCH`, `MCP_ERROR`, `MCP_AUTH_FAILED`,
  `RATE_LIMIT`, `DESKTOP_READY`, plus `RUNNER_LIFECYCLE_ERROR` (reserved upstream; no
  producer emits it yet). Two worth knowing: `CANCELLED` is terminal *alongside* `done`,
  so a loop that only knew `done` could wait forever on a cancelled run; and
  `SANDBOX_QUOTA_EXHAUSTED` is the one sandbox failure you should not retry.
  **If you branch on `StreamEventType.UNKNOWN`,** these frames no longer land there.

  Four further members exist for completeness but **do not fire on current streams**, so
  do not write code expecting them: `TASK_NOTIFICATION` (the runtime rewrites it to a
  `system_message` subtype), and `CLAUDE_THINKING` / `CLAUDE_REASONING` /
  `CLAUDE_PLAN_DELTA` (these arrive nested inside `content_block_delta`, not at top
  level). They are named so the runtime↔SDK parity guard can classify them rather than
  leaving them to surface as spurious "upgrade your SDK" warnings.
- `streaming.TERMINAL_FAILURE_TYPES` — the frames that mean the run is over and it
  failed. `has_errors()` and `raise_on_error` now count these, not just `type: "error"`.
  On a hosted runtime a dead runner or an exhausted sandbox quota is the likely way a run
  dies, and none of those is an `error` frame, so the previous behaviour missed the common
  case. `MCP_ERROR` is deliberately excluded — a broken MCP server is non-fatal and the
  run continues.

- **`client.account.change_password(current_password=..., new_password=...)`** — change the
  account password by proving you know the current one. Returns a fresh session
  (`access_token` + `refresh_token`), or an MFA challenge when 2FA is on.

  This is the NON-destructive path, and that is the point of it. A password *reset* can only
  prove control of the mailbox, so it is treated as an account takeover and revokes every
  credential on the account — API keys included. Proving the current password does not, so
  your keys and webhook triggers keep working. Reach for reset only when the password is
  genuinely lost.

### Fixed
- **The SDK no longer tells you to upgrade when you are already current.** A brand-new
  account's first documented run printed `Unrecognized stream event type 'RUNNER_DIAG' …
  Upgrading the m8tes SDK may add support` three times, on the latest release, before any
  agent output. Infrastructure frames are now classified and pass through quietly, with
  the payload still on `event.raw`.
- `m8tes --help` lists 6 commands instead of dumping 15 alias tokens. Every alias still
  resolves and unknown commands still get a did-you-mean suggestion.
- `CommandRegistry.auto_discover_commands()` is idempotent per package. It previously
  raised `ValueError: Command 'auth' is already registered` on a second call, and a first
  attempt at fixing that keyed on "the registry is non-empty" — which made every built-in
  silently vanish if a host registered its own command first.

### Changed
- A password **reset** (and account claim, and account deletion) now revokes every bearer
  credential, not just sessions: both API-key shapes, the webhook tokens on tasks and
  agents, and iMessage bridges. Previously an `m8_` key minted before a reset kept working
  after it. If your integration survives a customer's password reset today, it will need a
  freshly minted key after this.

## [3.1.0] - 2026-08-11

### Added
- **`PermissionRequest.timeout_seconds`** — how long an approval gate stays open, so a
  client can tell a fresh gate from a stale one without inventing its own window.
  Published by `GET /runs/{id}/permissions` (`client.runs.list_permissions`); defaults to
  the platform window when an older server omits it, so upgrading is safe against any
  backend.

  Deliberately **not** a countdown to render: three separate clocks act on a gate — the
  sandbox's poll, the reaper, and late approval, which stays valid while the run is paused
  — so a timer drawn from this one number would be wrong, and it would manufacture urgency
  on a consent surface.

## [3.0.1] - 2026-08-09

### Security
- **A caller-supplied value can no longer steer a request off the route its method
  names.** Every value interpolated into a request path — an end-user `user_id`, an app
  slug, a run filename, and every resource id, ~88 sites across `_resources/` — now goes
  through `m8tes._http.seg`. Interpolated raw, a tenant-controlled value ran as the OWNER
  of the API key: verified against a live backend, `users.get("../account/export")`
  returned the account's full export (200) and `users.delete("../account")` requested
  deletion of the entire account (202). **If your ids come from your own tenants,
  upgrade.**
- **`seg` refuses rather than escapes what stays structural after the server decodes.**
  Percent-encoding alone is not sufficient and this is the part worth reading: uvicorn
  sets the ASGI path to the percent-DECODED path and Starlette routes on that, so `%2F`
  is a separator to the server even though it is not one to `requests`. Measured against
  an ASGI app with the production route shapes, `runs.get("5/messages")` encoded to
  `/runs/5%2Fmessages` still reached the messages route — so `tasks.delete("5/webhook")`
  would have destroyed a webhook token instead of archiving the task. A segment
  containing `/`, or equal to `""`, `"."`, `".."` or `None`, now raises
  `m8tes.ValidationError` (a `M8tesError`, so an existing catch-all still works).
  Everything else is percent-encoded as before, **including a backslash** — it is a
  legal character in an id, it was measured not to act as a separator here, and
  refusing it would break a call that works. Partial dots are unaffected too: `..foo`,
  `a..b` and `...` all encode normally.
- **`runs.download_file`'s filename follows the same rule.** Its route reads
  `{filename:path}`, but the handler behind it sanitizes the filename to a basename and
  rejects anything else, so a nested name could never resolve — the filename is one
  segment like every other.

### Note on the TypeScript client
The equivalent hardening for `@m8tes/sdk` is tracked and not yet released, so this entry
describes the Python client only. A shared corpus now pins both clients' behaviour so the
two cannot drift silently.

## [3.0.0] - 2026-08-09

The CLI is now a plain v2 API customer: every `m8tes` command runs through the same
v2 SDK client a developer uses, and the legacy v1 SDK is gone.

### Added
- `tasks.update(id, status="enabled"|"disabled")` — enable/disable a task. Disabling
  pauses its schedules and event triggers; re-enabling re-arms the paused schedules,
  but event triggers stay off until re-enabled explicitly. Archiving remains
  `tasks.delete()`.
- `tasks.list(include_archived=True)` — surface archived tasks (off by default).
- `M8tes` now exposes `.api_key` and `.base_url` as public attributes.

### Changed
- **CLI commands run on the v2 API.** `m8tes mate|task|run` CRUD, streaming task
  execution, and chat all go through `/api/v2` — same surface, same fixes, as the SDK.
  Session auth (`m8tes auth login|register|logout`) and the Google OAuth link
  flow remain on the platform's session endpoints, now via `m8tes.auth.http`.
- `m8tes.Agent` is now the v2 `Teammate` alias (it was the legacy v1 agent class).
- Two deliberate CLI semantic changes: `m8tes task enable` re-arms only the schedules
  its own disable paused (a schedule you paused yourself stays paused; the old verb
  re-enabled every disabled schedule unconditionally), and `m8tes mate task` now
  inherits the mate's task-setup-tools default instead of forcing it on (pass
  `--no-task-setup-tools` to pin it off; the old CLI always sent an explicit `true`,
  stomping the mate-level setting).

### Removed
- **The legacy v1 SDK**: `m8tes.client`, `m8tes.agent`, `m8tes.instance`,
  `m8tes.chat`, `m8tes.task`, `m8tes.run`, `m8tes.services`, `m8tes.http`.
  Use the v2 client (`from m8tes import M8tes`). `m8tes.Deployment` is gone.
- CLI niceties with no v2 twin: `mate create --integrations`, `run_count` display
  lines, and auto-detect's "last used" heuristic (now most-recently-created).
- The `m8tes meta` command group (`cli/meta.py`, `auth/meta.py`): the backend's
  `/integrations/meta-ads` endpoints no longer exist, so the commands could never
  work. Google's flow remains.

## [2.17.0] - 2026-08-08

### Added
- `runs.check()` — cheap "has anything changed?" probe returning aggregate counters (`RunCheck`: `total_count`, `latest_run_id`, `awaiting_count`, `latest_change_at`). Poll this instead of re-listing runs; scoped exactly like `runs.list()` via `user_id`.
- `runs.share(id)` / `runs.unshare(id)` — create or revoke a public read-only link for a run (`RunShare`: `share_token`, `share_url`). Share is idempotent; unshare 404s the old URL immediately.
- `runs.archive(id)` — soft-delete a run out of the default list. Idempotent.
- `tasks.set_webhook_enabled(id, enabled=)` — pause or resume a task webhook WITHOUT rotating the token, so the distributed URL survives. Enabling with no minted token is a 400 (`enable_webhook()` mints one).

  These five endpoints already existed on the API, and the generated docs already advertised these exact SDK methods — the methods themselves were never written. A new repo-side guard (`test_v2_sdk_coverage.py`) now diffs the live V2 surface against the SDK's call sites and every `x-sdk-method` doc claim, so an SDK-less V2 endpoint or a phantom doc claim fails CI instead of shipping.

## [2.16.0] - 2026-08-05

### Added
- `agents.unarchive(id)` — restore an archived (deleted) agent. It comes back `disabled` (paused) with its schedules still off: call `enable()` and re-enable schedules deliberately to resume work. Archive is no longer a one-way door.
- `agents.list(include_archived=True)` — include archived agents in the listing (status `"archived"`), so they can be found and unarchived.
- `Teammate.display_order` + `agents.update(id, display_order=N)` — manual roster position, persisted server-side. `None` until the user places the agent; sort rosters by `COALESCE(display_order, id)` ascending so unplaced agents keep creation order and new agents append at the bottom.

## [2.15.0] - 2026-08-04

### Added
- `PermissionRequest.remembered` — set only by `runs.approve()`: `True` when an allow+`remember=True` decision persisted a cross-run always-allow policy, `False` when it did not (remember not requested, or the backend refused — e.g. a force-gated tool, whose stored policy the runtime would never consult). `None` on listings and on older servers. `status == "allowed"` alone never means "always allowed from now on" — check this before saying so.
- `runs.approve(..., reason=...)` — optional steering in your own words, mainly with `decision="deny"` (e.g. `"use the staging board instead"`). The agent reads it and adapts rather than silently skipping the action. Omitted from the request when not given, so older backends see no unknown field.
## [2.14.1] - 2026-08-04

### Fixed
- A 4xx or 5xx error now reports the server's message instead of a stringified dict. The backend wraps every error — v1 included — in `{"error": {"code", "message", "request_id"}}`, and the legacy client read the outer `error` value, so it raised `ValidationError`/`NetworkError` whose text was the whole dict. Errors written to be acted on arrived as punctuation: the strict-multi-tenant 422 tells you to call `/api/v2` and pass `user_id`, and the CLI printed it as `{'code': ..., 'message': ...}`. A 4xx also now carries the server's own `code` (e.g. `OVERAGE_UNAVAILABLE`) rather than the generic `validation_error`, and `details` is the same shape on 4xx and 5xx, so `details["request_id"]` resolves on both.

## [2.14.0] - 2026-08-04

### Added
- `Run.repeats_actions` — would retrying this run repeat an action it already took (an email sent, a Slack message posted)? Read it before offering a retry, and treat the three values as distinct: `True` means confirm first, `False` means the run only read and a retry is safe, and `None` means **not computed**, never "no actions".

  Only `runs.get()` computes it, and only for a run that can actually be retried (`failed` or `cancelled`). `runs.list()` always returns `None` for it — the answer costs one query per run, so a list would pay that per row. Fetch the single run before acting on the answer.

- `Run.notified_at` — when the run's result was delivered out-of-band, e.g. a scheduled run that emailed its summary. Pair it with `last_viewed_at` to ask "has the owner caught up on this run?": either one alone answers wrong, because a run that was emailed and never opened in-app has still been read.

## [2.13.0] - 2026-08-03

### Added
- `memories.create(audience=...)` and `memories.update(audience=...)`, plus `Memory.audience`. Records whether an account-level memory is about the **person** (`"personal"`) or about their **business** (`"company"`).

  Until now `user_id=None` meant both at once. With one human per account they are the same thing; the moment a second human shares one they are not, and splitting rows that have already mixed is far harder than recording the distinction as you write it.

  `Memory.scope` comes back on every response — `personal`, `company`, `account` or `teammate`. Read it rather than `audience` to tell a memory nobody has classified (`audience=None`, `scope="account"`) from one an agent keeps for itself (`audience=None`, `scope="teammate"`), which can never carry a classification; asking to classify one is refused rather than quietly ignored.

  Optional, and nothing about injection changes today: both audiences are read by every agent, exactly as before. Omitting it sends no field at all, so existing calls are unaffected and existing memories read back `audience=None` — a permanent "unclassified" state, not a gap awaiting a backfill. A content-only `update()` leaves the classification alone; pass `audience` to correct one.
## [2.12.1] - 2026-08-03

### Fixed
- A stream frame whose `type` is not a string (a list or dict) raised `TypeError` out of the enum lookup — `except ValueError` never caught it, and `parse_sse_line` catches only `JSONDecodeError`, so one malformed frame ended the caller's entire stream iteration. It now degrades to `unknown` like any other unrecognized frame, keyed on the type NAME rather than a `repr()` of the payload. Pre-existing; found reviewing the warning below.

- An unrecognized stream event type is now logged once (`WARNING`, logger `m8tes.streaming`) instead of being collapsed into `type="unknown"` in silence. A live run streams frames this SDK has no enum member for; callers `match` on `event.type`, so an unnamed frame was indistinguishable from a bug, and nothing recorded which type it had been. The frame still degrades to `unknown` and the full payload is still on `event.raw` — only the silence changed. Warned once per distinct type, since one run emits hundreds of frames.

- `keywords` in `pyproject.toml` said `ai-teammates`, which PyPI renders on the project page and indexes for search. "AI teammate" is banned product voice (the entity is an agent, or a Mate); it had shipped on every release through 2.12.0. Two guards already scanned for voice errors — one reads CLI display literals, the other README/examples prose — and neither opens `pyproject.toml`, so the packaging metadata was the one published surface nothing checked. `test_pypi_metadata_uses_product_voice` now reads it.

## [2.12.0] - 2026-08-02

### Added
- `Run` now carries the operational fields the API previously only exposed on the legacy v1 surface: `task_name`, `trigger_source`, `channel`, `run_mode`, `archived`, `share_token`, `sandbox_state`, `started_at`, `last_activity_at`. What a run *is* operationally — what it was called, how it was triggered, whether it is shared or archived, and where its sandbox got to.
- `RunMessage` now carries per-turn cost and timing: `input_tokens`, `output_tokens`, `cache_creation_tokens`, `cache_read_tokens`, `claude_cost_usd`, `sandbox_cost_usd`, `execution_time_ms`, `error_message`. This is the only place spend is attributable to a single turn.

  Both are additive, so existing code is unaffected. Internals (`sandbox_id`, `claude_session_id`, `sandbox_metrics`, `last_sequence`) stay unpublished on purpose — implementation details should not become public contract.


### Added
- `client.permissions` now reaches the **account-level scope**: `user_id` is optional on `create()`, `list()`, and `delete()`, and omitting it targets the policies that apply to runs carrying no `user_id`. Same convention `client.memories` already used.

  This closes a real hole rather than adding a convenience. Account-level policies are written by the product itself — every time someone picks "always allow" on a first-party run, the backend stores one with `end_user_id` NULL, and every later run reads it back to auto-approve that tool. But `user_id` was a **required** query parameter on list and delete, so those policies could be granted and then never listed or revoked through the API. A standing auto-approval you cannot see or take back.

  `PermissionPolicy.user_id` is now `str | None` for the same reason — an account-level policy has no end-user id.

### Fixed
- Listing permissions no longer fails on an account-level policy. The API's response model typed `user_id` as a required string, so a NULL `end_user_id` raised a validation error server-side (500) instead of returning the row.
- `billing.usage_timeseries(surface=...)` scopes the series to one billing surface: `"api"` for end-user-scoped (embedding) work, `"platform"` for first-party work. Omitting it returns every surface, which is the existing behaviour and still the default.

  This filters the surface a run was **created** on (`Run.billing_surface`), not the meter it finally settled on — settlement can differ for own-subscription turns and plan finalisation. Cost in this series is also the same estimate `usage().cost_used` uses, not reconciled ledger debits, so read it as usage rather than as a wallet statement.

- `Run.billing_surface` and `Run.channel`. These answer different questions and you usually want both: a first-party API-key call is `channel="api"` but `billing_surface="platform"`, because the surface keys off embedding while the channel records transport. Filtering a "show me my API traffic" view on `billing_surface` alone silently hides your own calls.

- `Balance.starter_credit_cents` and `Balance.has_paid_topup`, so a client can tell a new account its starter grant is free and stop saying so once real money has been added, without hardcoding the amount. `TokenTransaction` gained `id` and `receipt_url` — the Stripe receipt now rides on the ledger row it belongs to, so one table can show both (`billing.receipts()` is unchanged and still available).

## [2.11.0] - 2026-08-01

### Added
- `runs.create()`, `runs.reply()`, and `tasks.run()` now send an `Idempotency-Key` on every call, so those POSTs are safe to retry. Previously they were not retried at all: a request that timed out might already have started a billable run, so re-sending risked charging twice — the SDK chose the opposite failure (a dropped request) on your behalf. With a key the server replays the run the first attempt created, so neither failure applies.

  A key is generated per call. Pass `idempotency_key=` to supply your own when a retry must survive a process restart — a job runner re-driving the same unit of work should pass its job id. Reusing a key with a *different* request is a `409` (`exc.code == "idempotency_key_reuse"`), never a silent replay of a call you did not make.

### Changed
- POSTs carrying an `Idempotency-Key` are now retried on network errors and `429`/`5xx`, with the same backoff as `GET`. Any POST without one still fails immediately, unchanged.
- A replayed streaming `create`/`reply`/`tasks.run` is answered as JSON rather than SSE (a run that already exists has no fresh stream), and the SDK transparently joins that run's stream instead — you still get a `RunStream`. If the run has already finished there is nothing to join, so it raises `ConflictError` with `code="idempotent_replay_terminal"` and the run id in `.details`; fetch the result with `runs.get(id)`. You are charged once either way.

## [2.10.1] - 2026-08-01

### Fixed
- "a agent" → "an agent" in 20 developer-facing places: `README.md` (which renders on PyPI), `examples/` (9, including `examples/README.md` and `demo.py`), `_types.py` (6), and `_resources/` (`models.py`, `mcp_servers.py`, `bridges.py`). Left over from the 2.7.1 teammate→agent sweep and published since.

  A guard for this exact string already existed and was green: `test_release_hygiene.py`'s CLI check greps display literals for `\ba agent\b`, but it walks only `m8tes/cli` and inspects only `ast` display-string nodes — so it could not see a docstring, a comment, or a markdown table, and it was pointed at the one directory where the error had not occurred. A second guard now reads raw file text across the whole published tree (`m8tes/**/*.py`, `README.md`, `examples/**`). Verified by reintroducing the error in `examples/demo.py`: the new guard fails, the old one still passes.

## [2.10.0] - 2026-07-31

### Added
- `auth=` on `audit_logs.list()` and `--auth` on `m8tes run audit-logs`. Filters the trail by how each request was authenticated: `api_key` for calls made with an `m8_` key (your SDK and CLI traffic), `dashboard` for web-app sessions and auth events, `all` for everything.

  Useful because `audit_logs` is a shared table: the backend records every `/api/v2` request regardless of auth method, so an unfiltered list mixes your integration's calls with whatever the m8tes web app did while you were logged in. `auth="api_key"` is the view you want when answering "what did MY code do". The server default stays `all`, so existing calls are unchanged.

## [2.9.0] - 2026-07-27

### Added
- `raise_on_error=` on `runs.poll()`, `runs.wait()`, and `runs.create_and_wait()`. When true, a run that finishes `failed` raises `RunFailedError` instead of being returned, with `.details` carrying `run_id`, `error`, and `error_code` so you can branch on the machine token instead of parsing prose. This mirrors `runs.create(..., raise_on_error=True)` on the streaming path, and it is **off by default** so nothing existing changes behavior.

  Worth turning on. Without it `create_and_wait` returns normally on a failed run, so the documented `print(result.output)` prints the platform's failure sentence in exactly the spot the agent's answer belongs — a failed run reads as a successful one with a strange answer. Server-side, the run's `error`/`error_code` are now populated for in-stream failures (they were previously null on genuinely failed runs), so there is real detail to raise with.

## [2.8.0] - 2026-07-27

### Added
- `client.runs.reply()` / `reply_and_wait()` accept `tools=` — override the app toolset for this and later replies on the run (names from `client.apps.list()`; omitted or `[]` inherits the run's current set). Same resolver and 422 behavior as `runs.create`.
- `client.runs.reply()` / `reply_and_wait()` accept `permission_mode=` — override the execution mode for this and later replies (omitted inherits the run's persisted mode). Restores V1 follow-up parity for mode switches on finished runs.
- `client.runs.reply()` / `reply_and_wait()` accept `files=` — attach documents to a follow-up (same path/tuple/file-object shapes as `create`). Uploads use the new multipart `POST /runs/{id}/reply/with-files` endpoint; earlier uploads keep their names (same-named re-uploads get a collision suffix).

## [2.7.3] - 2026-07-27

### Fixed
- `client.runs.poll()` and `client.runs.wait()` now treat `closed` as a terminal status. The server's `TERMINAL_RUN_STATUSES` has four members; both helpers hardcoded three, each with its own private copy of the set, so a run the server had already finished never satisfied the exit condition and the caller waited out the full `timeout` (300s by default) before getting a `TimeoutError` for a run that was done. The set is now one module-level constant, `runs.TERMINAL_STATUSES`, and a test compares it against `fastapi/app/models/run.py` on every run so the two cannot drift again. Comparing the Python and TypeScript SDKs to each other could never have found this — both shipped the identical three-element set.

## [2.7.2] - 2026-07-26

### Fixed
- `client.apps.list()` no longer SENDS `limit` or `starting_after`. `GET /apps/` takes only `user_id` and returns the whole catalog, so a non-default value came back as a 422 `Unknown query parameter`. Not every call was affected: `_build_params` drops `limit` at its old default of 20, so `apps.list()` and `apps.list(limit=20)` both worked while `apps.list(limit=50)` did not. Both parameters therefore stay in the signature as accepted-and-ignored no-ops with a `DeprecationWarning` — deleting them in a patch release would have broken calls that were succeeding. They will be removed in the next major. `apps.list()`, `apps.list(user_id=...)`, `is_connected()`, and `auto_paging_iter()` are unchanged.
- Integration coverage for the above: the parameterized forms are asserted to raise, the scoped call is exercised against a real server, and auto-paging is asserted to terminate on the unpaginated catalog. Found by building the TypeScript SDK against the same endpoint.

## [2.7.1] - 2026-07-21

### Changed
- CLI help and display copy now says "agent" everywhere (141 strings across `m8tes mate/task/run/auth` help text, prompts, and output) — matching the canonical `agents` terminology from 2.6.0. All command names, aliases (`mate`, `teammate`, `m`), and API fields are unchanged; nothing breaks.

### Added
- Release-hygiene CI guards: every `pyproject.toml` version bump must have a matching CHANGELOG entry (2.7.0 initially shipped without one), and CLI display strings are pinned to "agent" terminology.

## [2.7.0] - 2026-07-17

### Added
- `effort=` — user-settable reasoning effort (`"low" | "medium" | "high" | "xhigh" | "max"`) as a first-class execution knob alongside `model=`:
  - `agents.create(effort=…)` sets the agent-level default; `agents.update(effort=None)` clears it back to the platform default (same null-reset semantics as `model=`).
  - Per-run override on `runs.create`, `runs.create_and_wait`, `runs.stream_text`, and `tasks.create` — follow-ups and resumes inherit it.
  - `Model.max_effort` on `client.models.list()` — the highest tier each model accepts (`"max"` on Claude models, `"high"` on others). Higher requested effort is clamped, never rejected.

## [2.6.0] - 2026-07-17

### Added
- **`client.agents` is the canonical resource accessor** (the API's canonical paths are now `/api/v2/agents` and `/api/v2/agent-templates`). `client.teammates` and `client.teammate_templates` remain permanent aliases of the same objects — nothing breaks.
- `agent_id=` accepted as the canonical kwarg on `runs.create`, `runs.create_and_wait`, `runs.stream_text`, `runs.list`, `tasks.create`, and `tasks.list` (`teammate_id=` still accepted; passing conflicting values raises `ValueError`).
- `Run.agent_id` / `Task.agent_id` properties mirroring the wire field `teammate_id`; `m8tes._types.Agent` aliases `Teammate` (not re-exported at top level — the legacy v1 `m8tes.Agent` class keeps that name).

## [2.5.1] - 2026-07-17

### Added
- `M8tesError.doc_url` — every typed exception now carries the API's new `error.doc_url` docs deep link (e.g. a 401 points at m8tes.ai/docs/api-introduction#authentication). `None` when the server omits it; fully backward compatible.

## [2.5.0] - 2026-07-14

### Added
- `client.billing.usage_timeseries(start_date=…, end_date=…, user_id=…, teammate_id=…)` — daily token + USD usage buckets (`UsageTimeseries` / `UsageBucket` / `UsageTotals`), zero-filled over the window (default: last 30 UTC days). Cost mirrors `usage().cost_used` semantics, so the series reconciles with period totals and prepaid ledger debits.
- `client.billing.receipts(limit=…, starting_after=…)` — prepaid top-up payment history with Stripe-hosted receipt links (`Receipt`), newest first, cursor-paginated.
- `Run.usage` (`RunUsage`) — per-run token counts and USD cost on every run response; `None` until metrics arrive.
- `client.billing.usage_timeseries(group_by="model")` — per-model slices (`UsageModelSlice`) inside each day bucket, for model-level cost attribution.
- `client.billing.set_auto_reload(enabled=…, threshold_cents=…, amount_cents=…)` — auto top-up: when the balance falls below the threshold, the saved card is charged off-session and credited. `Balance` gains `auto_reload_enabled` / `auto_reload_threshold_cents` / `auto_reload_amount_cents`. Enabling without a saved card raises `BillingError` (`NO_SAVED_PAYMENT_METHOD`).

## [2.4.0] - 2026-07-14

### Added
- `files=` on `runs.create()` — attach input files (path strings, `(filename, bytes)` tuples, or open binary files) for the agent to read; routes through the new multipart `POST /runs/with-files` endpoint with every other argument unchanged.
- `runs.outcome(run_id)` — condensed run result in one call: the agent's closing `summary` (transport markers stripped), `headline`, `needs_reply`, structured `output_data`, token counts, and the run's metered `cost_usd`.
- `teammates.enable()` / `teammates.disable()` — pause a teammate without archiving it (schedules stop firing, reversibly) and re-enable it later.
- `teammates.list_documents()` / `teammates.get_document()` — read the teammate's persistent documents (e.g. `latest-report`), the polished deliverables it maintains across runs.
- `memories.update(memory_id, content=...)` — correct a memory in place, and account-level memory scope: omit `user_id` on `memories.create/list/update/delete` to manage memories seen by runs that carry no `user_id`.
- `tasks.triggers.update(task_id, trigger_id, enabled=..., cron=..., interval_seconds=..., timezone=...)` — pause/resume or reshape a schedule (or app) trigger in place; schedule triggers returned by `triggers.list()` now populate `next_run`.
- Strict multi-tenant mode: requests that would land in the account-level scope because `user_id` was omitted are rejected (422) instead of silently assuming the global account scope. **On by default for new API-product signups**; choose at signup (`m8tes.signup(..., require_end_user_id=False)` for single-tenant use) or toggle any time with `settings.update(require_end_user_id=...)`.

### Changed
- Cancelled runs now fire their own `run.cancelled` webhook event instead of arriving as `run.failed` with `data.status: "cancelled"`. New webhooks subscribe to it by default; add `run.cancelled` to older subscriptions that need cancellation notifications.
## [2.3.0] - 2026-07-13

### Added
- `Run.task_id` — every run now reports the task it executed (every run belongs to exactly one task; ad-hoc runs get an auto-created one).
- `client.runs.list(task_id=...)` — pull one task's run history and outputs. This closes the loop for scheduled/webhook tasks: create the task, then retrieve its results — no webhook receiver required.

### Fixed
- A bare JSON 404 (`{"detail": "Not Found"}`, no API error envelope) now raises a `NotFoundError` explaining the base_url is likely missing its `/api/v2` prefix, instead of an unactionable "Not Found". Real resource-not-found responses (proper envelope) are untouched.

## [2.2.1] - 2026-07-13

### Changed
- Removed five unused dependencies (`anthropic`, `aiohttp`, `cryptography`, `pygments`, `python-dotenv`) — `pip install m8tes` is now much lighter with an identical API surface.

### Fixed
- The test suite passes in a standalone checkout of the public repo: the backend schema-contract test now skips cleanly instead of crashing collection when the backend source isn't present.
- Repo hygiene for public contributors: CI (lint + type-check + offline tests on Python 3.11/3.12) runs on every PR, `SECURITY.md` reflects the 2.x line, and the stale `AGENTS.md` (it described the legacy module layout) was removed in favor of `CLAUDE.md`.

## [2.2.0] - 2026-07-04

### Added
- `PermissionRequest.auto_resolved` — `True` when the platform resolved the request itself. Agents can now mark a question option as recommended (its label ends with `"(Recommended)"`); if nobody answers within ~10 minutes the run proceeds with that option instead of pausing forever, and the merged answer values in `tool_input["answers"]` end with an `"[auto-selected …]"` marker. A question with no recommended option still blocks until answered (unchanged), and plan approvals and tool permission gates never auto-continue. Calling `runs.answer()` on an auto-resolved question returns HTTP 409 (`auto_continued`) — send a follow-up message via `runs.reply()` to redirect instead. Non-blocking asks never enter `awaiting_approval`; deferrable ones pause for up to ~10 minutes before resuming on their own, so a run can complete with questions nobody answered.

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
