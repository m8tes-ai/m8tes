"""
E2E tests for m8tes SDK.

End-to-end tests that verify the complete stack:
    Python SDK → Flask Backend → Cloudflare Worker → Agent Execution

Tests use hybrid approach:
- Real internal stack (SDK, backend, worker)
- Mocked external APIs by default (OpenAI, Google Ads, Meta)
- Optional real API testing with E2E_USE_REAL_APIS=true

Prerequisites:
    1. Backend server running: cd backend && flask run
    2. Agent worker running: cd cloudflare/m8tes-agent && npm run dev

Run tests:
    make test-e2e              # Mocked external APIs (fast, free)
    make test-smoke            # Real external APIs (slow, costs money!)
"""
