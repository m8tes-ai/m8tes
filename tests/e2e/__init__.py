"""
E2E tests for m8tes SDK.

End-to-end tests that verify the complete stack:
    Python SDK → FastAPI backend → agent runtime → agent execution

Tests use hybrid approach:
- Real internal stack (SDK, backend, runtime)
- Mocked external APIs by default (OpenAI, Google Ads, Meta)
- Optional real API testing with E2E_USE_REAL_APIS=true

Prerequisites:
    1. Backend server running: cd fastapi && uv run uvicorn main:app --reload --port 8000
    2. Runtime-backed tests need a working backend/runtime environment

Run tests:
    make test-e2e              # Mocked external APIs (fast, free)
    make test-smoke            # Real external APIs (slow, costs money!)
"""
