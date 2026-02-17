"""Tests for v2 SDK Webhooks resource."""

import json

import responses

from m8tes._http import HTTPClient
from m8tes._resources.webhooks import Webhooks
from m8tes._types import SyncPage, Webhook, WebhookDelivery

BASE = "https://api.test/v2"


@responses.activate
def test_create_webhook():
    responses.add(
        responses.POST,
        f"{BASE}/webhooks",
        json={
            "id": 1,
            "url": "https://example.com/hook",
            "events": ["run.completed"],
            "secret": "whsec_abc",
            "active": True,
            "created_at": "",
        },
        status=201,
    )
    http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
    w = Webhooks(http).create(url="https://example.com/hook", events=["run.completed"])
    assert isinstance(w, Webhook)
    assert w.id == 1
    assert w.url == "https://example.com/hook"
    assert w.secret == "whsec_abc"
    body = json.loads(responses.calls[0].request.body)
    assert body == {"url": "https://example.com/hook", "events": ["run.completed"]}


@responses.activate
def test_create_webhook_minimal():
    responses.add(
        responses.POST,
        f"{BASE}/webhooks",
        json={"id": 2, "url": "https://example.com/hook", "active": True, "created_at": ""},
        status=201,
    )
    http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
    w = Webhooks(http).create(url="https://example.com/hook")
    assert w.id == 2
    body = json.loads(responses.calls[0].request.body)
    assert body == {"url": "https://example.com/hook"}


@responses.activate
def test_get_webhook():
    responses.add(
        responses.GET,
        f"{BASE}/webhooks/1",
        json={
            "id": 1,
            "url": "https://example.com/hook",
            "events": ["run.completed"],
            "secret": "a1b2...",
            "active": True,
            "delivery_status": "active",
            "created_at": "",
        },
    )
    http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
    w = Webhooks(http).get(1)
    assert isinstance(w, Webhook)
    assert w.id == 1
    assert w.secret == "a1b2..."


@responses.activate
def test_list_webhooks():
    responses.add(
        responses.GET,
        f"{BASE}/webhooks",
        json={
            "data": [
                {"id": 1, "url": "https://a.com/hook", "active": True, "created_at": ""},
                {"id": 2, "url": "https://b.com/hook", "active": False, "created_at": ""},
            ],
            "has_more": False,
        },
    )
    http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
    result = Webhooks(http).list()
    assert isinstance(result, SyncPage)
    assert len(result.data) == 2
    assert all(isinstance(w, Webhook) for w in result.data)
    assert result.has_more is False


@responses.activate
def test_delete_webhook():
    responses.add(responses.DELETE, f"{BASE}/webhooks/1", status=204)
    http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
    Webhooks(http).delete(1)
    assert responses.calls[0].request.method == "DELETE"


@responses.activate
def test_update_webhook():
    responses.add(
        responses.PATCH,
        f"{BASE}/webhooks/1",
        json={
            "id": 1,
            "url": "https://new.com/hook",
            "events": ["run.completed"],
            "active": True,
            "delivery_status": "active",
            "created_at": "",
        },
    )
    http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
    w = Webhooks(http).update(1, url="https://new.com/hook")
    assert isinstance(w, Webhook)
    assert w.url == "https://new.com/hook"
    body = json.loads(responses.calls[0].request.body)
    assert body == {"url": "https://new.com/hook"}


@responses.activate
def test_update_webhook_rotate_secret():
    """rotate_secret=True sends rotate_secret in body."""
    responses.add(
        responses.PATCH,
        f"{BASE}/webhooks/1",
        json={
            "id": 1,
            "url": "https://example.com/hook",
            "events": ["run.completed"],
            "secret": "newsecretnewsecretnewsecretnewsecret",
            "active": True,
            "delivery_status": "active",
            "created_at": "",
        },
    )
    http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
    w = Webhooks(http).update(1, rotate_secret=True)
    assert w.secret == "newsecretnewsecretnewsecretnewsecret"
    body = json.loads(responses.calls[0].request.body)
    assert body == {"rotate_secret": True}


@responses.activate
def test_update_webhook_partial():
    """Only provided fields are sent in request body."""
    responses.add(
        responses.PATCH,
        f"{BASE}/webhooks/1",
        json={
            "id": 1,
            "url": "https://example.com/hook",
            "events": ["run.started"],
            "active": False,
            "delivery_status": "active",
            "created_at": "",
        },
    )
    http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
    Webhooks(http).update(1, events=["run.started"], active=False)
    body = json.loads(responses.calls[0].request.body)
    assert body == {"events": ["run.started"], "active": False}
    assert "url" not in body


@responses.activate
def test_list_deliveries():
    responses.add(
        responses.GET,
        f"{BASE}/webhooks/1/deliveries",
        json={
            "data": [
                {
                    "id": 10,
                    "webhook_endpoint_id": 1,
                    "event_type": "run.completed",
                    "event_id": "evt_abc",
                    "run_id": 42,
                    "status": "success",
                    "response_status_code": 200,
                    "attempts": 1,
                    "created_at": "",
                },
            ],
            "has_more": False,
        },
    )
    http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
    result = Webhooks(http).list_deliveries(1)
    assert isinstance(result, SyncPage)
    assert len(result.data) == 1
    d = result.data[0]
    assert isinstance(d, WebhookDelivery)
    assert d.status == "success"
    assert d.run_id == 42
    assert d.event_type == "run.completed"


@responses.activate
def test_list_deliveries_empty():
    responses.add(
        responses.GET,
        f"{BASE}/webhooks/1/deliveries",
        json={"data": [], "has_more": False},
    )
    http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
    result = Webhooks(http).list_deliveries(1)
    assert result.data == []
    assert result.has_more is False
