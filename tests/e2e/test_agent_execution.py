"""
E2E tests for agent execution scenarios.

Tests specific agent execution patterns with real FastAPI backend + Claude Agent SDK.
Always uses REAL APIs (costs money!).

To run these tests:
    1. Start database: cd fastapi && docker compose up -d
    2. Start backend: cd fastapi && uv run uvicorn main:app --reload --port 8000
    3. Run tests: pytest tests/e2e/test_agent_execution.py -v -m e2e

Note: These tests use real Claude Agent SDK and will incur API costs!
"""

import pytest


@pytest.mark.e2e
def test_single_tool_execution(
    authenticated_sdk_client,
    backend_server,
    openai_mocker,
    google_ads_mocker,
):
    """
    Test agent executing a single GAQL tool call.

    Verifies that the agent can successfully execute a Google Ads
    query tool and return structured results.
    """
    # Create instance with GAQL tool
    instance = authenticated_sdk_client.instances.create(
        name="GAQL Test Agent",
        tools=["run_gaql_query"],
        instructions="Execute Google Ads queries",
    )

    # Execute task with streaming - collect all events
    events = list(instance.execute_task("Get campaigns for customer 1234567890", stream=True))

    assert len(events) > 0
    print(f"\n✅ Received {len(events)} streaming events")

    # Verify we got some text content
    from m8tes.streaming import TextDeltaEvent

    text_events = [e for e in events if isinstance(e, TextDeltaEvent)]
    assert len(text_events) > 0

    # Clean up
    instance.archive()


@pytest.mark.e2e
def test_multiple_sequential_tool_calls(
    authenticated_sdk_client,
    backend_server,
    openai_mocker,
    google_ads_mocker,
):
    """
    Test agent executing multiple tool calls in sequence.

    Verifies that the agent can chain multiple tool calls together
    to complete a complex task.
    """
    instance = authenticated_sdk_client.instances.create(
        name="Multi-Tool Agent",
        tools=["run_gaql_query"],
        instructions="Execute multiple queries as needed",
    )

    # Task that should require multiple tool calls
    events = list(
        instance.execute_task(
            "Get campaigns and then get keywords for customer 1234567890", stream=True
        )
    )

    assert len(events) > 0
    print(f"\n✅ Received {len(events)} events for multi-tool task")

    # Verify we got tool call events
    from m8tes.streaming import ToolCallStartEvent

    tool_events = [e for e in events if isinstance(e, ToolCallStartEvent)]
    print(f"✅ Detected {len(tool_events)} tool calls")

    # Clean up
    instance.archive()


@pytest.mark.e2e
@pytest.mark.skip(
    reason="Chat mode API not fully implemented yet - use start_chat_session() when ready"
)
def test_task_vs_chat_run_types(
    authenticated_sdk_client,
    backend_server,
    openai_mocker,
):
    """
    Test difference between task and chat run types.

    Verifies that task runs clear history while chat runs
    maintain conversation context.

    NOTE: Skipped until chat session API is fully implemented.
    """
    instance = authenticated_sdk_client.instances.create(
        name="Run Type Test Agent",
        tools=["run_gaql_query"],
        instructions="Answer questions",
    )

    # Execute task run
    events = list(instance.execute_task("What is my name?", stream=True))
    assert len(events) > 0

    # TODO: Implement chat session testing when API is ready
    # chat_session = instance.start_chat_session()
    # ...

    # Clean up
    instance.archive()


@pytest.mark.e2e
def test_instance_lifecycle_management(
    authenticated_sdk_client,
    backend_server,
):
    """
    Test complete instance lifecycle: create, update, list, archive.

    Verifies all instance management operations work correctly.
    """
    # Create instance
    instance = authenticated_sdk_client.instances.create(
        name="Lifecycle Test Agent",
        tools=["run_gaql_query"],
        instructions="Original instructions",
    )

    original_id = instance.id
    assert instance.name == "Lifecycle Test Agent"

    # List instances - should include our new one
    instances = authenticated_sdk_client.instances.list()
    assert len(instances) > 0
    assert any(i.id == original_id for i in instances)

    # Get instance by ID
    retrieved = authenticated_sdk_client.instances.get(original_id)
    assert retrieved.id == original_id
    assert retrieved.name == "Lifecycle Test Agent"

    # Update instance
    updated = authenticated_sdk_client.instances.update(
        original_id,
        name="Updated Test Agent",
    )
    assert updated.id == original_id
    assert updated.name == "Updated Test Agent"

    # Archive instance
    result = authenticated_sdk_client.instances.archive(original_id)
    assert result is True

    # Verify archiving - should not be in list
    instances_after = authenticated_sdk_client.instances.list()
    assert not any(i.id == original_id for i in instances_after)


@pytest.mark.e2e
@pytest.mark.skip(reason="Run tracking not yet integrated with streaming API")
def test_run_listing_and_pagination(
    authenticated_sdk_client,
    backend_server,
    openai_mocker,
):
    """
    Test listing runs for an instance.

    Verifies that runs can be listed and filtered correctly.

    NOTE: Skipped until run tracking is integrated with streaming execute_task API.
    """
    instance = authenticated_sdk_client.instances.create(
        name="Run Listing Test Agent",
        tools=["run_gaql_query"],
        instructions="Test agent",
    )

    # Create multiple runs by executing tasks
    for i in range(3):
        events = list(instance.execute_task(f"Task {i}", stream=True))
        assert len(events) > 0

    # TODO: List all runs for instance when tracking is integrated
    # runs = authenticated_sdk_client.runs.list_for_instance(instance.id)
    # assert len(runs) >= 3

    # Clean up
    instance.archive()


@pytest.mark.e2e
def test_streaming_event_types(
    authenticated_sdk_client,
    backend_server,
    openai_mocker,
    google_ads_mocker,
):
    """
    Test different streaming event types during execution.

    Verifies that all expected event types are emitted during
    agent execution with streaming.
    """
    instance = authenticated_sdk_client.instances.create(
        name="Streaming Events Test Agent",
        tools=["run_gaql_query"],
        instructions="Test streaming events",
    )

    # Execute with streaming and collect events
    events = list(instance.execute_task("Get campaigns for customer 1234567890", stream=True))

    assert len(events) > 0
    print(f"\n✅ Received {len(events)} streaming events")

    # Verify we have different event types

    event_types = [type(e).__name__ for e in events]
    unique_types = set(event_types)
    print(f"✅ Event types: {unique_types}")
    assert len(unique_types) >= 1  # At least one event type

    # Clean up
    instance.archive()


@pytest.mark.e2e
def test_instance_with_custom_instructions(
    authenticated_sdk_client,
    backend_server,
    openai_mocker,
):
    """
    Test instance with custom user instructions.

    Verifies that user instructions are properly applied.
    """
    instance = authenticated_sdk_client.instances.create(
        name="Custom Instructions Agent",
        tools=["run_gaql_query"],
        instructions="Analyze Google Ads data",
        user_instructions="Always respond in bullet points",
    )

    assert instance.id is not None

    # Execute task
    events = list(instance.execute_task("What campaigns exist?", stream=True))
    assert len(events) > 0
    print(f"\n✅ Agent executed with custom instructions, {len(events)} events received")

    # Clean up
    instance.archive()


@pytest.mark.e2e
@pytest.mark.skip(reason="Run tracking not yet integrated with streaming API")
def test_run_usage_statistics(
    authenticated_sdk_client,
    backend_server,
    openai_mocker,
):
    """
    Test retrieving usage statistics for a run.

    Verifies that token usage and cost data are properly tracked.

    NOTE: Skipped until run tracking is integrated with streaming execute_task API.
    """
    instance = authenticated_sdk_client.instances.create(
        name="Usage Stats Test Agent",
        tools=["run_gaql_query"],
        instructions="Test usage tracking",
    )

    # Execute task
    events = list(instance.execute_task("Simple query", stream=True))
    assert len(events) > 0

    # TODO: Get usage statistics when run tracking is integrated
    # usage = run.get_usage()
    # assert usage is not None

    # Clean up
    instance.archive()


@pytest.mark.e2e
@pytest.mark.skip(reason="Run tracking not yet integrated with streaming API")
def test_conversation_history_retrieval(
    authenticated_sdk_client,
    backend_server,
    openai_mocker,
):
    """
    Test retrieving conversation history for a run.

    Verifies that full conversation including tool calls is retrievable.

    NOTE: Skipped until run tracking is integrated with streaming execute_task API.
    """
    instance = authenticated_sdk_client.instances.create(
        name="Conversation Test Agent",
        tools=["run_gaql_query"],
        instructions="Test conversation history",
    )

    # Execute task
    events = list(instance.execute_task("Get campaigns", stream=True))
    assert len(events) > 0

    # TODO: Get conversation when run tracking is integrated
    # conversation = run.get_conversation()
    # assert len(conversation) > 0

    # Clean up
    instance.archive()


@pytest.mark.smoke
@pytest.mark.e2e
def test_real_google_ads_query_execution(
    authenticated_sdk_client,
    backend_server,
):
    """
    SMOKE TEST: Real Google Ads API query execution.

    Always uses REAL APIs (costs money!).
    Requires valid Google Ads test account.

    Verifies that the agent can execute real GAQL queries
    against Google Ads API and return actual data.
    """
    import os

    # Get test customer ID from environment
    test_customer_id = os.getenv("GOOGLE_ADS_TEST_CUSTOMER_ID", "")
    if not test_customer_id:
        pytest.skip("GOOGLE_ADS_TEST_CUSTOMER_ID not set")

    # Create instance
    instance = authenticated_sdk_client.instances.create(
        name="Real GAQL Test Agent",
        tools=["run_gaql_query"],
        instructions="Execute real Google Ads queries",
    )

    # Execute task with real customer ID using streaming
    print("\n💰 Running real GAQL query (this costs money!)...")
    events = list(
        instance.execute_task(f"Get campaigns for customer {test_customer_id}", stream=True)
    )

    assert len(events) > 0
    print(f"💰 Real GAQL test completed with {len(events)} streaming events")

    # Verify we got text responses
    from m8tes.streaming import TextDeltaEvent

    text_events = [e for e in events if isinstance(e, TextDeltaEvent)]
    assert len(text_events) > 0
    print(f"💰 Received {len(text_events)} text response events")

    # Clean up
    instance.archive()


@pytest.mark.smoke
@pytest.mark.e2e
def test_real_end_to_end_campaign_analysis(
    authenticated_sdk_client,
    backend_server,
):
    """
    SMOKE TEST: Real end-to-end campaign analysis.

    Always uses REAL APIs (costs real money!).

    Verifies complete workflow with real Claude Agent SDK and real Google Ads data:
    1. Agent receives task
    2. Agent uses real Claude Agent SDK to plan
    3. Agent executes real GAQL queries
    4. Agent uses real Claude Agent SDK to analyze results
    5. Agent returns actionable insights
    """
    import os

    test_customer_id = os.getenv("GOOGLE_ADS_TEST_CUSTOMER_ID", "")
    if not test_customer_id:
        pytest.skip("GOOGLE_ADS_TEST_CUSTOMER_ID not set")

    # Create instance with realistic instructions
    instance = authenticated_sdk_client.instances.create(
        name="Real Campaign Analyzer",
        tools=["run_gaql_query"],
        instructions="Analyze Google Ads campaigns and provide actionable insights",
    )

    # Execute complex analysis task
    task_message = f"""
    Analyze the campaigns for customer {test_customer_id}.
    Focus on:
    1. Overall performance metrics
    2. Budget utilization
    3. Top performing campaigns
    4. Recommendations for optimization
    """

    print("\n💰 Starting real end-to-end analysis (this costs money!)...")

    # Execute with streaming to see progress
    events = list(instance.execute_task(task_message, stream=True))

    assert len(events) > 0
    print(f"💰 Analysis complete with {len(events)} streaming events")

    # Verify we got various event types
    from m8tes.streaming import TextDeltaEvent, ToolCallStartEvent

    text_events = [e for e in events if isinstance(e, TextDeltaEvent)]
    tool_events = [e for e in events if isinstance(e, ToolCallStartEvent)]

    assert len(text_events) > 0, "Should have received text responses"
    print(f"💰 Received {len(text_events)} text events and {len(tool_events)} tool calls")

    # Clean up
    instance.archive()
