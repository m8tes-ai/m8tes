"""teammates→agents rename: canonical names with permanent legacy aliases.

client.agents / client.agent_templates are canonical (hitting /v2/agents and
/v2/agent-templates); client.teammates / client.teammate_templates are the same
objects. agent_id= is the canonical kwarg on runs/tasks, mapping to the wire
field teammate_id. m8tes.Agent is the v2 Teammate alias (the legacy v1 class
was deleted with the legacy SDK).
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


# The legacy aliases stay PLAIN INSTANCE ATTRIBUTES, and that is a decision with a scar.
#
# The DX complaint is real: `dir(client)` offers `agents` and `teammates` with identical
# method sets and nothing says which is canonical, so a developer picks one by coin flip
# and repeats it through a whole integration. A 2026-08-11 attempt to fix that turned both
# into properties and filtered them out of `__dir__`. An independent review found three
# separate breakages in one pass, two of them reproduced here before the revert:
#
#   1. `patch.object(client, "teammates", mock)` raised `AttributeError: property
#      'teammates' has no deleter` on TEARDOWN. mock deletes rather than restores when the
#      name is not in the instance `__dict__`, so every test suite stubbing the alias broke.
#      Adding a setter did NOT fix this; it needs a deleter too, and by then the "simple
#      alias" is four dunder-adjacent methods.
#   2. `Mock(spec=client)` stopped exposing `teammates` at all, because `spec` is built
#      from `dir()`. That one is caused by the `__dir__` filter itself and cannot be fixed
#      while still hiding the name — the two requirements are the same mechanism.
#   3. A subclass declaring `__slots__ = ("teammates",)` shadows the property.
#
# Tidier autocomplete is not worth breaking a permanent alias in three ways. If this is
# ever revisited, the answer is documentation and the docs' own examples, not a descriptor.
# See TODOS.md "DX parity with eve.dev".
def test_legacy_aliases_stay_plain_attributes(client):
    """Pins the revert, so the descriptor approach cannot come back without reading why."""
    assert "teammates" in vars(client), "alias must live in the instance __dict__"
    assert "teammate_templates" in vars(client)
    assert not isinstance(type(client).__dict__.get("teammates"), property)


def test_patch_object_round_trips_on_the_alias(client):
    """The exact failure that reverted the descriptor version."""
    from unittest.mock import MagicMock, patch

    with patch.object(client, "teammates", MagicMock()):
        assert isinstance(client.teammates, MagicMock)
    # Teardown is the half that broke: it must restore, not raise.
    assert client.teammates is client.agents


def test_mock_spec_still_exposes_the_alias(client):
    """`Mock(spec=client)` builds from dir(), so filtering dir() silently breaks it."""
    from unittest.mock import MagicMock

    assert hasattr(MagicMock(spec=client), "teammates")


def test_v2_type_alias():
    assert Agent is Teammate


def test_package_level_agent_is_the_v2_alias():
    import m8tes

    assert m8tes.Agent is Teammate


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
