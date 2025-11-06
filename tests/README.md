# m8tes Python SDK Test Suite

A comprehensive test suite following 2025 best practices for the m8tes Python SDK.

## Overview

This test suite provides:

- **Modern pytest 8.x configuration** with strict validation and fast feedback
- **Clean SDK-specific test structure** ready to scale with SDK development
- **Rich test utilities** for assertions, mocking, and test data
- **Working examples** demonstrating SDK testing patterns

## Directory Structure

```
tests/
├── conftest.py           # Root fixtures and SDK test setup
├── utils/                # Test utilities
│   ├── assertions.py     # SDK-specific assertion helpers
│   ├── factories.py      # Test data factories for SDK objects
│   └── mocks.py         # HTTP mocking and SDK mock helpers
└── unit/                # Unit tests
    ├── __init__.py      # Unit test package
    ├── test_client.py   # M8tes client tests
    ├── test_agent.py    # Agent class tests
    └── test_auth.py     # Authentication tests
```

## Installation

```bash
# Install with development dependencies
pip install -e ".[dev]"
```

## Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=m8tes

# Run specific markers
pytest -m unit           # Only unit tests
pytest -m integration    # Only integration tests
pytest -m "not slow"     # Exclude slow tests

# Run specific test file
pytest tests/unit/test_client.py -v
```

## Test Configuration

The pytest configuration in `pyproject.toml` includes:

```toml
[tool.pytest.ini_options]
minversion = "8.0"
addopts = [
    "-ra",              # show all test results
    "--strict-markers", # strict marker validation
    "--maxfail=1",     # fail fast for quick feedback
    "--tb=short",      # concise traceback format
    "--showlocals",    # show local vars in failures
    "--durations=10"   # show 10 slowest tests
]
markers = [
    "unit: Unit tests with mocked dependencies",
    "integration: Integration tests requiring external services",
    "slow: Tests that take more than a few seconds to run",
    "api: API endpoint tests",
    "auth: Authentication and authorization tests",
    "streaming: Tests for streaming functionality",
    "google_ads: Google Ads API integration tests"
]
```

## Writing Tests

### Basic Unit Test

```python
# tests/unit/test_client.py
import pytest
from m8tes import M8tes, AuthenticationError
from tests.utils.assertions import assert_valid_agent_id


@pytest.mark.unit
class TestM8tesClient:
    def test_initialization_with_api_key(self, api_key, base_url):
        client = M8tes(api_key=api_key, base_url=base_url)
        assert client.api_key == api_key
        assert client.base_url == base_url

    def test_initialization_without_api_key_raises_error(self):
        with pytest.raises(AuthenticationError, match="No API key provided"):
            M8tes()

    @pytest.mark.slow
    def test_create_agent_with_mock_response(self, authenticated_client, mock_agent_data):
        # Test agent creation with mocked HTTP response
        # Implementation would use responses library
        pass
```

### Using Test Utilities

```python
from tests.utils.assertions import (
    assert_dict_contains_keys,
    assert_valid_agent_id,
    assert_valid_tools_list,
)
from tests.utils.factories import SDKDataFactory, HTTPResponseFactory
from tests.utils.mocks import ResponsesMock, mock_environment_variables


def test_with_factories_and_assertions():
    # Create test data
    agent_data = SDKDataFactory.create_agent_data(
        name="Test Agent",
        tools=["google_ads_search"],
    )

    # Use assertions
    assert_dict_contains_keys(agent_data, ["id", "name", "tools"])
    assert_valid_agent_id(agent_data["id"])
    assert_valid_tools_list(agent_data["tools"])


def test_with_http_mocking():
    with ResponsesMock() as rsps:
        rsps.add_agent_creation(
            base_url="https://api.test.m8tes.ai/api/v1",
            agent_data={"id": "agent_123", "name": "Test Agent"}
        )

        # Your test code using the mocked HTTP client
        client = M8tes(api_key="test-key")
        agent = client.create_agent(tools=["google_ads_search"], instructions="test")
        # Assertions...


@mock_environment_variables(M8TES_API_KEY="test-key")
def test_with_env_vars():
    # Test with mocked environment variables
    client = M8tes()  # Should pick up API key from env
    assert client.api_key == "test-key"
```

### Using Fixtures

```python
def test_with_sdk_fixtures(authenticated_client, mock_agent_data, mock_run_events):
    # authenticated_client: Pre-configured M8tes client
    # mock_agent_data: Sample agent data
    # mock_run_events: Sample streaming events

    from m8tes.agent import Agent
    agent = Agent(client=authenticated_client, data=mock_agent_data)

    assert agent.id == mock_agent_data["id"]
    assert agent.name == mock_agent_data["name"]
```

## Test Categories

### Unit Tests (`@pytest.mark.unit`)

- Test individual classes and methods in isolation
- Mock all external dependencies (HTTP, environment, etc.)
- Should run in <1 second each
- No network calls or external services

### Integration Tests (`@pytest.mark.integration`)

- Test SDK integration with mock or test API endpoints
- May involve multiple SDK components
- Can take longer but should stay under reasonable limits
- Mock external services, but test SDK integration logic

### Authentication Tests (`@pytest.mark.auth`)

- Test OAuth flows, API key validation, credential handling
- Mock external OAuth providers
- Test error scenarios (expired tokens, invalid keys, etc.)

### Streaming Tests (`@pytest.mark.streaming`)

- Test SSE streaming functionality
- Mock streaming responses
- Test event parsing, connection handling, etc.

## Development Workflow

### Adding New Tests

1. **Create test file** in appropriate directory (`tests/unit/`, etc.)
2. **Use appropriate markers** (`@pytest.mark.unit`, etc.)
3. **Leverage test utilities** from `tests/utils/`
4. **Follow naming conventions** (`test_*` functions, `Test*` classes)

### Test Data Management

```python
# Use factories for consistent test data
agent_data = SDKDataFactory.create_agent_data(
    name="Custom Agent",
    tools=["google_ads_search"]
)

# Use fixtures for common test scenarios
def test_agent_creation(authenticated_client, mock_agent_data):
    # Test implementation
    pass
```

### Mocking HTTP Requests

```python
# For simple mocking
@responses.activate
def test_api_call():
    responses.add(
        responses.POST,
        "https://api.test.m8tes.ai/api/v1/agents",
        json={"id": "agent_123"},
        status=201,
    )
    # Test code

# For complex scenarios
def test_complex_flow():
    with ResponsesMock() as rsps:
        # base_url should include API version and prefix for convenience in this helper
        base_url = "https://api.test.m8tes.ai/api/v1"
        rsps.add_agent_creation(base_url, agent_data)
        rsps.add_agent_run(base_url, "agent_123", mock_events)
        # Test code
```

## Commands Reference

```bash
# Basic test runs
pytest                                    # All tests
pytest -v                                # Verbose output
pytest -x                                # Stop on first failure
pytest --lf                              # Last failed tests only

# Coverage
pytest --cov=m8tes                       # SDK coverage
pytest --cov=m8tes --cov-report=html     # HTML coverage report

# Markers
pytest -m unit                           # Only unit tests
pytest -m "unit and not slow"           # Unit tests, exclude slow
pytest -m integration                    # Only integration tests
pytest -m auth                          # Only auth tests

# Performance
pytest --durations=10                    # Show 10 slowest tests
pytest --maxfail=3                       # Stop after 3 failures

# Specific tests
pytest tests/unit/test_client.py         # Specific file
pytest tests/unit/test_client.py::TestM8tesClient::test_init  # Specific test
pytest -k "test_agent"                   # Tests matching pattern
```

## Extending the Test Suite

As the SDK grows, you can easily add:

1. **More test categories**: Add new markers and test directories
2. **API integration tests**: Test against real API endpoints (staging)
3. **Performance tests**: Measure SDK performance characteristics
4. **End-to-end tests**: Test complete user workflows
5. **Mock service**: Create local mock server for complex integration tests

## Best Practices

1. **Test behavior, not implementation**: Focus on what the SDK should do
2. **Use descriptive test names**: `test_create_agent_with_invalid_tools_raises_validation_error`
3. **One assertion per test**: Keep tests focused and easy to debug
4. **Mock external dependencies**: Keep unit tests isolated and fast
5. **Test error conditions**: Don't just test the happy path
6. **Use factories**: Consistent, maintainable test data
7. **Clean up after tests**: Use fixtures that handle setup/teardown

This test suite provides a solid foundation for developing and maintaining the m8tes Python SDK with confidence!
