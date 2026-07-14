"""Tests for client.billing usage_timeseries + receipts, and Run.usage parsing."""

import pytest
import responses

from m8tes._http import HTTPClient
from m8tes._resources.billing import Billing
from m8tes._types import Receipt, Run, RunUsage, UsageTimeseries

BASE = "https://api.test/v2"

BUCKET = {
    "date": "2026-07-13",
    "input_tokens": 1000,
    "output_tokens": 200,
    "cache_read_tokens": 500,
    "cache_creation_tokens": 50,
    "total_tokens": 1750,
    "cost_usd": "0.42",
}
TOTALS = {k: v for k, v in BUCKET.items() if k != "date"}


@pytest.fixture
def billing():
    return Billing(HTTPClient(api_key="m8_test", base_url=BASE, timeout=5))


class TestUsageTimeseries:
    @responses.activate
    def test_parses_buckets_and_totals(self, billing):
        responses.add(
            responses.GET,
            f"{BASE}/usage/timeseries",
            json={
                "start_date": "2026-06-14",
                "end_date": "2026-07-13",
                "buckets": [BUCKET],
                "totals": TOTALS,
            },
        )
        series = billing.usage_timeseries()
        assert isinstance(series, UsageTimeseries)
        assert series.start_date == "2026-06-14"
        assert series.buckets[0].date == "2026-07-13"
        assert series.buckets[0].total_tokens == 1750
        assert series.buckets[0].cost_usd == "0.42"
        assert series.totals.input_tokens == 1000
        assert series.totals.cost_usd == "0.42"

    @responses.activate
    def test_sends_filters_as_params(self, billing):
        responses.add(
            responses.GET,
            f"{BASE}/usage/timeseries",
            json={
                "start_date": "2026-07-01",
                "end_date": "2026-07-02",
                "buckets": [],
                "totals": TOTALS,
            },
        )
        billing.usage_timeseries(
            start_date="2026-07-01",
            end_date="2026-07-02",
            user_id="alice",
            teammate_id=7,
        )
        params = responses.calls[0].request.params
        assert params["start_date"] == "2026-07-01"
        assert params["end_date"] == "2026-07-02"
        assert params["user_id"] == "alice"
        assert params["teammate_id"] == "7"

    @responses.activate
    def test_group_by_model_parses_slices(self, billing):
        responses.add(
            responses.GET,
            f"{BASE}/usage/timeseries",
            json={
                "start_date": "2026-07-13",
                "end_date": "2026-07-13",
                "buckets": [
                    {
                        **BUCKET,
                        "models": [
                            {**TOTALS, "model": "claude-opus-4-8"},
                            {**TOTALS, "model": "unknown"},
                        ],
                    }
                ],
                "totals": TOTALS,
            },
        )
        series = billing.usage_timeseries(group_by="model")
        assert responses.calls[0].request.params["group_by"] == "model"
        slices = series.buckets[0].models
        assert slices is not None and len(slices) == 2
        assert slices[0].model == "claude-opus-4-8"
        assert slices[0].cost_usd == "0.42"

    @responses.activate
    def test_models_none_without_group_by(self, billing):
        responses.add(
            responses.GET,
            f"{BASE}/usage/timeseries",
            json={
                "start_date": "2026-07-13",
                "end_date": "2026-07-13",
                "buckets": [{**BUCKET, "models": None}],
                "totals": TOTALS,
            },
        )
        series = billing.usage_timeseries()
        assert series.buckets[0].models is None

    @responses.activate
    def test_omits_unset_params(self, billing):
        responses.add(
            responses.GET,
            f"{BASE}/usage/timeseries",
            json={
                "start_date": "2026-06-14",
                "end_date": "2026-07-13",
                "buckets": [],
                "totals": TOTALS,
            },
        )
        billing.usage_timeseries()
        assert responses.calls[0].request.params == {}


class TestReceipts:
    @responses.activate
    def test_lists_receipts(self, billing):
        responses.add(
            responses.GET,
            f"{BASE}/billing/receipts",
            json={
                "data": [
                    {
                        "id": 7,
                        "amount_cents": 5000,
                        "currency": "usd",
                        "description": "API token top-up",
                        "receipt_url": "https://pay.stripe.test/r/1",
                        "created_at": "2026-07-01T12:00:00Z",
                    },
                    {
                        "id": 6,
                        "amount_cents": 1000,
                        "currency": "usd",
                        "description": None,
                        "receipt_url": None,
                        "created_at": "2026-06-01T12:00:00Z",
                    },
                ],
                "has_more": False,
            },
        )
        page = billing.receipts()
        assert isinstance(page.data[0], Receipt)
        assert page.data[0].amount_cents == 5000
        assert page.data[0].receipt_url == "https://pay.stripe.test/r/1"
        assert page.data[1].receipt_url is None
        assert page.has_more is False

    @responses.activate
    def test_pagination_params(self, billing):
        responses.add(
            responses.GET,
            f"{BASE}/billing/receipts",
            json={"data": [], "has_more": False},
        )
        billing.receipts(limit=50, starting_after=6)
        params = responses.calls[0].request.params
        assert params["limit"] == "50"
        assert params["starting_after"] == "6"


class TestRunUsage:
    def test_run_parses_usage(self):
        run = Run.from_dict(
            {
                "id": 1,
                "status": "completed",
                "created_at": "2026-07-13T00:00:00Z",
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 20,
                    "cache_read_tokens": 5,
                    "cache_creation_tokens": 1,
                    "total_tokens": 126,
                    "cost_usd": "1.25",
                },
            }
        )
        assert isinstance(run.usage, RunUsage)
        assert run.usage.total_tokens == 126
        assert run.usage.cost_usd == "1.25"

    def test_run_usage_defaults_none(self):
        run = Run.from_dict({"id": 1, "status": "completed", "created_at": ""})
        assert run.usage is None


class TestAutoReload:
    @responses.activate
    def test_enable_sends_settings_and_parses_balance(self, billing):
        responses.add(
            responses.PATCH,
            f"{BASE}/billing/auto-reload",
            json={
                "balance_micros": 1_000_000,
                "balance_usd": "1.0000",
                "currency": "usd",
                "transactions": [],
                "auto_reload_enabled": True,
                "auto_reload_threshold_cents": 500,
                "auto_reload_amount_cents": 2000,
            },
        )
        bal = billing.set_auto_reload(enabled=True, threshold_cents=500, amount_cents=2000)
        import json

        sent = json.loads(responses.calls[0].request.body)
        assert sent == {"enabled": True, "threshold_cents": 500, "amount_cents": 2000}
        assert bal.auto_reload_enabled is True
        assert bal.auto_reload_amount_cents == 2000

    @responses.activate
    def test_disable_omits_amounts(self, billing):
        responses.add(
            responses.PATCH,
            f"{BASE}/billing/auto-reload",
            json={
                "balance_micros": 0,
                "balance_usd": "0.0000",
                "currency": "usd",
                "transactions": [],
                "auto_reload_enabled": False,
            },
        )
        bal = billing.set_auto_reload(enabled=False)
        import json

        assert json.loads(responses.calls[0].request.body) == {"enabled": False}
        assert bal.auto_reload_enabled is False
        assert bal.auto_reload_threshold_cents is None
