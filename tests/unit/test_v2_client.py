"""Tests for v2 M8tes client entry point."""

import pytest

from m8tes._client import M8tes
from m8tes._exceptions import AuthenticationError
from m8tes._resources import Apps, Runs, Tasks, Teammates


class TestClientInit:
    def test_explicit_api_key(self):
        client = M8tes(api_key="m8_test", base_url="http://localhost")
        assert client._http._session.headers["Authorization"] == "Bearer m8_test"

    def test_env_var_api_key(self, monkeypatch):
        monkeypatch.setenv("M8TES_API_KEY", "m8_from_env")
        client = M8tes(base_url="http://localhost")
        assert client._http._session.headers["Authorization"] == "Bearer m8_from_env"

    def test_no_key_raises(self, monkeypatch):
        monkeypatch.delenv("M8TES_API_KEY", raising=False)
        with pytest.raises(AuthenticationError, match="No API key"):
            M8tes()

    def test_resource_namespaces(self):
        client = M8tes(api_key="m8_test", base_url="http://localhost")
        assert isinstance(client.teammates, Teammates)
        assert isinstance(client.runs, Runs)
        assert isinstance(client.tasks, Tasks)
        assert isinstance(client.apps, Apps)

    def test_default_base_url(self):
        client = M8tes(api_key="m8_test")
        assert client._http._base_url == "https://m8tes.ai/api/v2"
