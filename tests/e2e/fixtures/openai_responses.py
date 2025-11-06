"""
OpenAI API mock responses for E2E tests.

Provides realistic OpenAI API responses captured from real interactions,
frozen in time for consistent, fast, free testing.
"""

import json
import re


def get_openai_mock(rsps):
    """
    Add OpenAI API mocks to responses object.

    Args:
        rsps: responses.RequestsMock instance
    """
    # Mock chat completions endpoint
    rsps.add(
        rsps.POST,
        re.compile(r"https://api\.openai\.com/v1/chat/completions"),
        json=get_campaign_analysis_response(),
        status=200,
    )

    # Mock embeddings endpoint (if used)
    rsps.add(
        rsps.POST,
        re.compile(r"https://api\.openai\.com/v1/embeddings"),
        json={
            "data": [
                {
                    "embedding": [0.1] * 1536,  # Simplified embedding vector
                    "index": 0,
                }
            ],
            "model": "text-embedding-ada-002",
            "usage": {"prompt_tokens": 8, "total_tokens": 8},
        },
        status=200,
    )


def get_campaign_analysis_response():
    """
    Realistic OpenAI response for campaign analysis task.

    This is based on a real OpenAI API response and provides:
    - Thought process
    - Tool call to run_gaql_query
    - Follow-up analysis
    """
    return {
        "id": "chatcmpl-test123",
        "object": "chat.completion",
        "created": 1704067200,
        "model": "gpt-4-0125-preview",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "I'll help you analyze your Google Ads campaigns. Let me query your campaign data using the GAQL tool.",  # noqa: E501
                    "tool_calls": [
                        {
                            "id": "call_abc123",
                            "type": "function",
                            "function": {
                                "name": "run_gaql_query",
                                "arguments": json.dumps(
                                    {
                                        "customer_id": "1234567890",
                                        "query": "SELECT campaign.id, campaign.name, campaign.status, "  # noqa: E501
                                        "metrics.impressions, metrics.clicks, metrics.cost_micros "
                                        "FROM campaign WHERE segments.date DURING LAST_30_DAYS",
                                    }
                                ),
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {
            "prompt_tokens": 150,
            "completion_tokens": 75,
            "total_tokens": 225,
        },
    }


def get_campaign_creation_response():
    """
    OpenAI response for campaign creation task.

    Shows the AI deciding to create a campaign with specific parameters.
    """
    return {
        "id": "chatcmpl-test456",
        "object": "chat.completion",
        "created": 1704067200,
        "model": "gpt-4-0125-preview",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "I'll create a new Search campaign for you with the specified settings.",  # noqa: E501
                    "tool_calls": [
                        {
                            "id": "call_def456",
                            "type": "function",
                            "function": {
                                "name": "create_campaign",
                                "arguments": json.dumps(
                                    {
                                        "customer_id": "1234567890",
                                        "campaign_name": "Summer Sale 2024",
                                        "budget_amount_micros": 50000000,  # $50
                                        "campaign_type": "SEARCH",
                                    }
                                ),
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {
            "prompt_tokens": 200,
            "completion_tokens": 100,
            "total_tokens": 300,
        },
    }


def get_simple_text_response(content="I've analyzed your data and here are my findings."):
    """
    Simple text response without tool calls.

    Args:
        content: Response content

    Returns:
        OpenAI API response dict
    """
    return {
        "id": "chatcmpl-test789",
        "object": "chat.completion",
        "created": 1704067200,
        "model": "gpt-4-0125-preview",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 50,
            "completion_tokens": 25,
            "total_tokens": 75,
        },
    }


def get_error_response():
    """
    OpenAI error response for testing error handling.
    """
    return {
        "error": {
            "message": "Rate limit exceeded",
            "type": "rate_limit_error",
            "param": None,
            "code": "rate_limit_exceeded",
        }
    }


def get_streaming_response():
    """
    OpenAI streaming response chunks.

    Returns list of Server-Sent Events (SSE) formatted chunks.
    """
    chunks = [
        {
            "id": "chatcmpl-stream1",
            "object": "chat.completion.chunk",
            "created": 1704067200,
            "model": "gpt-4-0125-preview",
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": ""},
                    "finish_reason": None,
                }
            ],
        },
        {
            "id": "chatcmpl-stream1",
            "object": "chat.completion.chunk",
            "created": 1704067200,
            "model": "gpt-4-0125-preview",
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": "I'll"},
                    "finish_reason": None,
                }
            ],
        },
        {
            "id": "chatcmpl-stream1",
            "object": "chat.completion.chunk",
            "created": 1704067200,
            "model": "gpt-4-0125-preview",
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": " help"},
                    "finish_reason": None,
                }
            ],
        },
        {
            "id": "chatcmpl-stream1",
            "object": "chat.completion.chunk",
            "created": 1704067200,
            "model": "gpt-4-0125-preview",
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop",
                }
            ],
        },
    ]

    # Format as SSE
    sse_chunks = []
    for chunk in chunks:
        sse_chunks.append(f"data: {json.dumps(chunk)}\n\n")
    sse_chunks.append("data: [DONE]\n\n")

    return "".join(sse_chunks)
