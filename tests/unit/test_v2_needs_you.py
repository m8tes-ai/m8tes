"""`runs.needs_you()` — the compact "waiting on a human" list.

The endpoint feeds the iOS companion's Lock Screen widgets, so its contract is
narrower than a run list on purpose: a capped `items`, a full `count`, and titles
the server has already made public-safe. These tests pin the parts a caller can
get wrong quietly — the scope param actually reaching the wire, and `count` being
independent of `len(items)`.
"""

import pytest
import responses

from m8tes import M8tes, NeedsYou, NeedsYouItem
from m8tes._exceptions import AuthenticationError

BASE = "https://api.test/v2"

_ITEM = {"run_id": 7, "title": "Ads Mate needs you", "mate_name": "Ads Mate"}


@responses.activate
def test_needs_you_returns_typed_items_and_sends_the_end_user_scope():
    responses.get(f"{BASE}/runs/needs-you", json={"count": 1, "items": [_ITEM]})
    with M8tes(api_key="m8_test", base_url=BASE) as client:
        result = client.runs.needs_you(user_id="alice")

    assert isinstance(result, NeedsYou)
    assert isinstance(result.items[0], NeedsYouItem)
    assert (result.count, result.items[0].run_id) == (1, 7)
    assert result.items[0].title == "Ads Mate needs you"
    assert result.items[0].mate_name == "Ads Mate"
    # The param has to reach the query string, not merely be accepted as a kwarg:
    # a scoped call that silently reads the account scope is a cross-tenant read.
    assert responses.calls[0].request.params == {"user_id": "alice"}
    assert len(responses.calls) == 1


@responses.activate
def test_account_scope_sends_no_user_id():
    responses.get(f"{BASE}/runs/needs-you", json={"count": 0, "items": []})
    with M8tes(api_key="m8_test", base_url=BASE) as client:
        assert client.runs.needs_you().count == 0
    assert responses.calls[0].request.params == {}


@responses.activate
def test_count_is_the_whole_set_not_the_capped_items():
    """`items` is a top-N for a widget. Treating `len(items)` as the total
    under-reports the moment more than a few runs are waiting, which is exactly
    when a caller most wants the number."""
    responses.get(f"{BASE}/runs/needs-you", json={"count": 12, "items": [_ITEM] * 3})
    with M8tes(api_key="m8_test", base_url=BASE) as client:
        result = client.runs.needs_you()
    assert result.count == 12
    assert len(result.items) == 3


@responses.activate
def test_a_missing_items_key_is_an_empty_list_not_a_crash():
    responses.get(f"{BASE}/runs/needs-you", json={"count": 0})
    with M8tes(api_key="m8_test", base_url=BASE) as client:
        assert client.runs.needs_you().items == []


@responses.activate
def test_needs_you_propagates_authentication_errors():
    responses.get(f"{BASE}/runs/needs-you", status=401, json={"error": {"message": "Invalid key"}})
    with M8tes(api_key="m8_test", base_url=BASE) as client, pytest.raises(AuthenticationError):
        client.runs.needs_you()
