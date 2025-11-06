"""
Integration tests for streaming functionality.

These tests verify the full streaming pipeline from CLI -> SDK -> Worker -> Response.
"""

import pytest

from m8tes.streaming import (
    StreamAccumulator,
    ToolCallStartEvent,
    ToolResultEndEvent,
)


class TestStreamingIntegration:
    """Integration tests for streaming execution."""

    def test_execute_task_streaming(self, authenticated_client, test_instance):
        """Test task execution with streaming."""
        # Execute task with streaming
        accumulator = StreamAccumulator()
        event_count = 0

        for event in test_instance.execute_task(
            "Show me campaigns for customer 1234567890", stream=True, format="events"
        ):
            accumulator.process(event)
            event_count += 1

            # Verify events are StreamEvent instances
            assert hasattr(event, "type")
            assert hasattr(event, "raw")

        # Should have received some events
        assert event_count > 0

        # Should have accumulated some text
        text = accumulator.get_text()
        assert len(text) > 0

        # Should have completed
        assert not accumulator.has_errors()

    def test_execute_task_text_format(self, authenticated_client, test_instance):
        """Test task execution with text-only format."""
        text_parts = []

        for text in test_instance.execute_task("Show me campaigns", stream=True, format="text"):
            assert isinstance(text, str)
            text_parts.append(text)

        # Should have received text chunks
        assert len(text_parts) > 0

        # Combine into full text
        full_text = "".join(text_parts)
        assert len(full_text) > 0

    def test_execute_task_json_format(self, authenticated_client, test_instance):
        """Test task execution with JSON format."""
        json_events = []

        for event in test_instance.execute_task("Show me campaigns", stream=True, format="json"):
            assert isinstance(event, dict)
            json_events.append(event)

        # Should have received JSON events
        assert len(json_events) > 0

    def test_chat_session_streaming(self, authenticated_client, test_instance):
        """Test chat session with streaming."""
        # Start chat session
        chat_session = test_instance.start_chat_session()

        # Send first message
        accumulator = StreamAccumulator()
        for event in chat_session.send("Hello, who are you?", stream=True, format="events"):
            accumulator.process(event)

        # Should have response
        assert len(accumulator.get_text()) > 0

        # Send second message (tests history preservation)
        accumulator2 = StreamAccumulator()
        for event in chat_session.send("What was my first question?", stream=True, format="events"):
            accumulator2.process(event)

        # Should have response
        assert len(accumulator2.get_text()) > 0

        # Cleanup
        chat_session.end()

    def test_chat_session_clear_history(self, authenticated_client, test_instance):
        """Test clearing chat history."""
        # Start chat session
        chat_session = test_instance.start_chat_session()

        # Send message
        accumulator = StreamAccumulator()
        for event in chat_session.send("Remember this: apple", stream=True, format="events"):
            accumulator.process(event)

        assert len(accumulator.get_text()) > 0

        # Clear history
        chat_session.clear_history()

        # Send new message asking about previous context
        accumulator2 = StreamAccumulator()
        for event in chat_session.send(
            "What did I tell you to remember?", stream=True, format="events"
        ):
            accumulator2.process(event)

        # Agent should not remember (history was cleared)
        response = accumulator2.get_text().lower()
        assert "apple" not in response or "don't" in response or "didn't" in response

        # Cleanup
        chat_session.end()

    def test_streaming_with_tool_calls(self, authenticated_client, test_instance):
        """Test streaming with tool calls."""
        accumulator = StreamAccumulator()
        has_tool_call = False
        has_tool_result = False

        for event in test_instance.execute_task(
            "Run a GAQL query to show campaigns for customer 1234567890",
            stream=True,
            format="events",
        ):
            accumulator.process(event)

            if isinstance(event, ToolCallStartEvent):
                has_tool_call = True
                # Verify tool call has metadata
                assert event.tool_name is not None

            if isinstance(event, ToolResultEndEvent):
                has_tool_result = True
                # Verify tool result has data
                assert event.result is not None

        # Should have seen tool calls
        assert has_tool_call
        assert has_tool_result

        # Should have text response
        assert len(accumulator.get_text()) > 0

        # Should have tool call records
        tool_calls = accumulator.get_tool_calls()
        assert len(tool_calls) > 0

    def test_streaming_error_handling(self, authenticated_client, test_instance):
        """Test error handling in streaming."""
        # Test with invalid input that might cause errors
        accumulator = StreamAccumulator()

        try:
            for event in test_instance.execute_task(
                "",  # Empty message might cause error
                stream=True,
                format="events",
            ):
                accumulator.process(event)
        except Exception:
            # Should gracefully handle errors
            pass

        # Check if any errors were captured in stream
        if accumulator.has_errors():
            errors = accumulator.get_errors()
            assert len(errors) > 0
            assert all(isinstance(e, str) for e in errors)

    def test_streaming_keyboard_interrupt(self, authenticated_client, test_instance):
        """Test that streaming can be interrupted."""
        event_count = 0

        try:
            for _event in test_instance.execute_task(
                "Show me campaigns", stream=True, format="events"
            ):
                event_count += 1
                # Simulate interrupt after first event
                if event_count == 1:
                    raise KeyboardInterrupt()
        except KeyboardInterrupt:
            pass

        # Should have received at least one event before interrupt
        assert event_count >= 1


# Fixtures for integration tests
@pytest.fixture
def test_instance(authenticated_client):
    """Create a test instance for integration tests."""
    try:
        # Try to get existing instance or create new one
        instances = authenticated_client.instances.list()

        if instances:
            # Use first available instance
            return instances[0]
        else:
            # Create new test instance
            return authenticated_client.instances.create(
                name="Test Streaming Instance",
                tools=["run_gaql_query"],
                instructions="You are a helpful Google Ads assistant for testing streaming functionality.",  # noqa: E501
            )
    except Exception as e:
        pytest.skip(f"Cannot create test instance - backend may not be available: {e}")


@pytest.fixture
def authenticated_client():
    """Get authenticated M8tes client."""
    from m8tes import M8tes

    # This requires M8TES_API_KEY to be set in environment
    client = M8tes()

    # Verify authentication works
    try:
        client.instances.list()
    except Exception as e:
        pytest.skip(f"Authentication failed - skipping integration tests: {e}")

    return client
