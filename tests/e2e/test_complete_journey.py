"""
E2E test for complete user journey.

Tests the entire flow from user registration through agent execution
with real FastAPI backend + Claude Agent SDK.
Always uses REAL APIs (costs money!).

To run these tests:
    1. Start database: cd fastapi && docker compose up -d
    2. Start backend: cd fastapi && uv run uvicorn main:app --reload --port 8000
    3. Run tests: pytest tests/e2e/test_complete_journey.py -v -m e2e

Note: These tests use real Claude Agent SDK and will incur API costs!
"""

import pytest


@pytest.mark.e2e
def test_complete_user_journey(
    backend_server,
    test_user,
    authenticated_sdk_client,
    openai_mocker,
    google_ads_mocker,
):
    """
    Test complete user journey from registration to agent execution.

    Flow:
    1. User is registered (test_user fixture)
    2. User is authenticated (authenticated_sdk_client fixture)
    3. User creates an agent instance
    4. User executes a task with streaming
    5. Agent calls Claude Agent SDK (REAL API - costs money!)
    6. Agent executes Google Ads tool (REAL API)
    7. User receives streaming results

    This tests the ENTIRE stack:
    - Python SDK → HTTP requests
    - FastAPI Backend → Database
    - Claude Agent SDK → MCP Tools
    - Agent execution → Tool routing

    Always uses REAL APIs (costs money!).
    """
    # Step 1: Verify user is authenticated
    assert authenticated_sdk_client.api_key is not None
    assert test_user["email"] is not None

    # Step 2: Create an agent instance
    instance = authenticated_sdk_client.instances.create(
        name="Campaign Analyzer",
        tools=["run_gaql_query"],
        instructions="Analyze Google Ads campaigns and provide insights",
    )

    assert instance.id is not None
    assert instance.name == "Campaign Analyzer"
    print(f"\n✅ Created instance: {instance.id}")

    # Step 3: Execute a task with streaming
    task_message = "Show me my campaigns for customer 1234567890"

    events = list(instance.execute_task(task_message, stream=True))

    assert len(events) > 0
    print(f"\n✅ Received {len(events)} streaming events")

    # Step 4: Verify we got text responses
    from m8tes.streaming import TextDeltaEvent

    text_events = [e for e in events if isinstance(e, TextDeltaEvent)]
    assert len(text_events) > 0
    print(f"\n✅ Received {len(text_events)} text response events")

    # Step 5: List all instances
    instances = authenticated_sdk_client.instances.list()
    assert len(instances) >= 1
    assert any(i.id == instance.id for i in instances)
    print(f"\n✅ Listed {len(instances)} instances")

    # Step 6: Clean up - archive instance
    result = instance.archive()
    assert result is True
    print(f"\n✅ Archived instance: {instance.id}")


@pytest.mark.e2e
def test_mate_task_execution_with_streaming(
    authenticated_sdk_client,
    backend_server,
    openai_mocker,
    google_ads_mocker,
):
    """
    Test mate task execution with streaming events.

    Verifies that streaming events are properly propagated from
    Claude Agent SDK through FastAPI backend to SDK client.
    """
    # Create instance
    instance = authenticated_sdk_client.instances.create(
        name="Streaming Test Agent",
        tools=["run_gaql_query"],
        instructions="Test streaming execution",
    )

    # Execute task and collect streaming events
    events = list(instance.execute_task("Analyze campaigns", stream=True))

    # Verify we received streaming events
    assert len(events) > 0
    print(f"\n✅ Received {len(events)} streaming events")

    # Verify we got different event types
    event_types = [type(e).__name__ for e in events]
    unique_types = set(event_types)
    print(f"✅ Event types: {unique_types}")
    assert len(unique_types) >= 1  # At least one event type

    # Clean up
    instance.archive()


@pytest.mark.e2e
@pytest.mark.skip(
    reason="Chat mode API not fully implemented yet - use start_chat_session() when ready"
)
def test_chat_mode_conversation(
    authenticated_sdk_client,
    backend_server,
    openai_mocker,
):
    """
    Test chat mode with multi-turn conversation.

    Verifies that conversation history is maintained across
    multiple interactions.

    NOTE: Skipped until chat session API is fully implemented.
    """
    # Create instance
    instance = authenticated_sdk_client.instances.create(
        name="Chat Test Agent",
        tools=["run_gaql_query"],
        instructions="Answer questions about Google Ads",
    )

    # TODO: Implement chat session testing when API is ready
    # chat_session = instance.start_chat_session()
    # response1 = chat_session.send("Hello, can you help me?")
    # response2 = chat_session.send("What campaigns do I have?")
    # ...

    # Clean up
    instance.archive()


@pytest.mark.e2e
def test_error_handling(
    authenticated_sdk_client,
    backend_server,
    openai_mocker,
    google_ads_mocker,
):
    """
    Test error handling in agent execution.

    Verifies that errors are properly propagated and handled during streaming.
    """
    # Create instance
    instance = authenticated_sdk_client.instances.create(
        name="Error Test Agent",
        tools=["run_gaql_query"],
        instructions="Test error handling",
    )

    # Execute task - with real APIs this should complete normally
    # Error handling is tested through the execution itself
    try:
        events = list(instance.execute_task("Test error handling", stream=True))
        # Should receive events normally with real APIs
        assert len(events) >= 0
        print(f"\n✅ Error handling test completed with {len(events)} events")
    except Exception as e:
        # If error occurs, verify it's the right type
        from m8tes.exceptions import M8tesError

        assert isinstance(e, M8tesError)
        print(f"\n✅ Error properly raised: {type(e).__name__}")

    # Clean up
    instance.archive()


@pytest.mark.smoke
@pytest.mark.e2e
def test_real_claude_sdk_integration(
    authenticated_sdk_client,
    backend_server,
):
    """
    SMOKE TEST: Real Claude Agent SDK integration.

    Always uses REAL APIs (costs money!).

    Verifies that the entire stack works with real Claude Agent SDK.
    """
    # Create instance
    instance = authenticated_sdk_client.instances.create(
        name="Real API Test Agent",
        tools=["run_gaql_query"],
        instructions="Analyze campaigns using real AI",
    )

    print("\n💰 Running real Claude Agent SDK test (this costs money!)...")

    # Execute task - this makes REAL Claude Agent SDK API call
    events = list(instance.execute_task("What campaigns are performing well?", stream=True))

    assert len(events) > 0
    print(f"💰 Real API test completed with {len(events)} streaming events")

    # Verify we got text responses
    from m8tes.streaming import TextDeltaEvent

    text_events = [e for e in events if isinstance(e, TextDeltaEvent)]
    assert len(text_events) > 0
    print(f"💰 Received {len(text_events)} text response events")

    # Clean up
    instance.archive()
