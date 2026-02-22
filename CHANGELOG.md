# Changelog

All notable changes to the m8tes Python SDK will be documented in this file.

## [1.0.0] - 2026-02-22

### Added

### Changed

### Fixed

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
