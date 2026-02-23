# Changelog

All notable changes to the m8tes Python SDK will be documented in this file.

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
- Stripe-style resource client: teammates, runs, tasks, apps, memories, permissions, webhooks, users
- Streaming support via `RunStream` context manager
- Human-in-the-loop: approval mode, plan mode, `AskUserQuestion`
- Multi-tenancy via `user_id` / `end_user_id`
- Auto-paging iterator for list endpoints
- Typed exceptions: `NotFoundError`, `RateLimitError`, `AuthenticationError`, `ConflictError`

## [0.2.0] - 2026-02-18

### Added
- V2 SDK with Stripe-style resource pattern (`client.resource.method()`)
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
