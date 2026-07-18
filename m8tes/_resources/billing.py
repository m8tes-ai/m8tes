"""Billing resource — usage, plan catalog, opt-in overage controls, and prepaid token balance.

Lets developers self-meter spend: read current usage (including accrued overage),
fetch the public plan catalog, and toggle usage overage with a monthly cap. For
prepaid-billed accounts, also read the prepaid token balance and add credit via a
Stripe Checkout top-up.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._types import Balance, Plan, Receipt, SyncPage, Usage, UsageTimeseries
from ._utils import _build_params, _resolve_agent_id

if TYPE_CHECKING:
    from .._http import HTTPClient


class Billing:
    """client.billing — usage, plans, and opt-in overage settings."""

    def __init__(self, http: HTTPClient):
        self._http = http

    def usage(self) -> Usage:
        """Get current billing usage, run counts, costs, and overage state."""
        resp = self._http.request("GET", "/usage/")
        return Usage.from_dict(resp.json())

    def usage_timeseries(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        user_id: str | None = None,
        teammate_id: int | None = None,
        agent_id: int | None = None,
        group_by: str | None = None,
    ) -> UsageTimeseries:
        """Daily token + USD usage buckets, zero-filled over the window (UTC days).

        Defaults to the last 30 days ending today. Dates are ISO strings
        (`"2026-07-01"`). Pass `user_id` to scope to one end-user, `agent_id`
        to scope to one agent. With `group_by="model"`, each bucket carries
        per-model slices in `.models` (history predating model attribution folds
        into "unknown"). Cost mirrors `usage().cost_used` semantics, so the
        series always reconciles with period totals and prepaid debits.
        """
        params = _build_params(
            start_date=start_date,
            end_date=end_date,
            user_id=user_id,
            teammate_id=_resolve_agent_id(teammate_id, agent_id),
            group_by=group_by,
        )
        resp = self._http.request("GET", "/usage/timeseries", params=params)
        return UsageTimeseries.from_dict(resp.json())

    def receipts(self, *, limit: int = 20, starting_after: int | None = None) -> SyncPage[Receipt]:
        """Prepaid top-up payment history with Stripe-hosted receipt links, newest first.

        Each row is one paid top-up; `receipt_url` opens the Stripe receipt (may be
        None when the underlying session is no longer retrievable).
        """
        params = _build_params(limit=limit, starting_after=starting_after)
        resp = self._http.request("GET", "/billing/receipts", params=params)
        body = resp.json()

        def _fetch_next(**kw: object) -> SyncPage[Receipt]:
            return self.receipts(**kw)  # type: ignore[arg-type]

        return SyncPage(
            data=[Receipt.from_dict(d) for d in body["data"]],
            has_more=body["has_more"],
            _fetch_next=_fetch_next,
        )

    def plans(self) -> list[Plan]:
        """List public (paid) plans from the canonical catalog."""
        resp = self._http.request("GET", "/billing/plans")
        return [Plan.from_dict(d) for d in resp.json()]

    def set_overage(self, *, enabled: bool, monthly_cap_cents: int) -> Usage:
        """Opt in/out of usage overage and set the monthly spend cap (cents).

        Off by default. Once enabled, runs beyond your plan's included allotment
        bill at the per-run overage rate until the cap is hit. Returns the refreshed
        usage so you can confirm the new state in one call.
        """
        resp = self._http.request(
            "PATCH",
            "/billing/overage",
            json={"enabled": enabled, "monthly_cap_cents": monthly_cap_cents},
        )
        return Usage.from_dict(resp.json())

    def balance(self) -> Balance:
        """Get your prepaid token balance + recent ledger (for prepaid-billed accounts).

        Balance is micro-USD; `balance_usd` is a rounded display string. Runs debit this
        balance at official provider prices.
        """
        resp = self._http.request("GET", "/billing/balance")
        return Balance.from_dict(resp.json())

    def topup(self, *, amount_cents: int) -> str:
        """Start a Stripe Checkout to add token credit. Returns a URL to send the buyer to;
        the balance is credited once payment completes ($5 min, $1M max)."""
        resp = self._http.request("POST", "/billing/topup", json={"amount_cents": amount_cents})
        return str(resp.json()["checkout_url"])

    def set_auto_reload(
        self,
        *,
        enabled: bool,
        threshold_cents: int | None = None,
        amount_cents: int | None = None,
    ) -> Balance:
        """Enable/disable auto-reload: when the balance falls below `threshold_cents`,
        `amount_cents` is charged to your saved card off-session and credited.

        Enabling requires a saved payment method — any completed top-up Checkout saves
        the card; without one this raises `BillingError` with
        `.code == "NO_SAVED_PAYMENT_METHOD"`. Disabling needs only `enabled=False`.

        `amount_cents` runs from $5 to $10,000 per charge (deliberately lower than the
        manual top-up ceiling — these charges happen off-session). At most one reload
        fires per 6-hour window, and Stripe emails a receipt for each charge. Returns
        the refreshed balance with the new settings.
        """
        body: dict = {"enabled": enabled}
        if threshold_cents is not None:
            body["threshold_cents"] = threshold_cents
        if amount_cents is not None:
            body["amount_cents"] = amount_cents
        resp = self._http.request("PATCH", "/billing/auto-reload", json=body)
        return Balance.from_dict(resp.json())

    def set_alert_threshold(self, *, low_balance_threshold_cents: int) -> Balance:
        """Set the balance at which the low-balance warning fires (cents; the critical tier is
        20% of it). Warnings are delivered by email AND as `balance.low`/`balance.critical`/
        `balance.depleted` webhook events. 0 warns only on depletion. Returns the refreshed
        balance with the new thresholds.
        """
        resp = self._http.request(
            "PATCH",
            "/billing/alert-settings",
            json={"low_balance_threshold_cents": low_balance_threshold_cents},
        )
        return Balance.from_dict(resp.json())
