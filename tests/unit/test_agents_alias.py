"""teammates→agents rename: canonical names with permanent legacy aliases.

client.agents / client.agent_templates are canonical (hitting /v2/agents and
/v2/agent-templates); client.teammates / client.teammate_templates are the same
objects. agent_id= is the canonical kwarg on runs/tasks, mapping to the wire
field teammate_id. The legacy v1 class m8tes.Agent (m8tes/agent.py) is NOT
shadowed by the v2 alias.
"""

import pytest
import responses

from m8tes import M8tes
from m8tes._resources._utils import _resolve_agent_id
from m8tes._types import Agent, Teammate

BASE = "https://api.test/v2"


@pytest.fixture
def client():
    return M8tes(api_key="m8_test", base_url="https://api.test/v2")


def test_client_aliases_are_the_same_objects(client):
    assert client.teammates is client.agents
    assert client.teammate_templates is client.agent_templates


def test_v2_type_alias():
    assert Agent is Teammate


def test_legacy_v1_agent_class_not_shadowed():
    import m8tes
    import m8tes.agent

    assert m8tes.Agent is m8tes.agent.Agent


def test_resolve_agent_id():
    assert _resolve_agent_id(None, 5) == 5
    assert _resolve_agent_id(5, None) == 5
    assert _resolve_agent_id(5, 5) == 5
    assert _resolve_agent_id(None, None) is None
    with pytest.raises(ValueError):
        _resolve_agent_id(1, 2)


@responses.activate
def test_runs_create_accepts_agent_id(client):
    responses.add(responses.POST, f"{BASE}/runs/", json={"id": 1, "status": "running"}, status=200)
    client.runs.create(message="hi", agent_id=7, stream=False)
    import json

    assert json.loads(responses.calls[0].request.body)["teammate_id"] == 7


@responses.activate
def test_tasks_create_accepts_agent_id(client):
    responses.add(
        responses.POST,
        f"{BASE}/tasks/",
        json={"id": 1, "teammate_id": 7, "instructions": "x", "name": "t"},
        status=201,
    )
    task = client.tasks.create(agent_id=7, instructions="x")
    assert task.agent_id == 7  # canonical property mirrors wire field teammate_id


def test_tasks_create_requires_an_agent(client):
    with pytest.raises(ValueError):
        client.tasks.create(instructions="x")
