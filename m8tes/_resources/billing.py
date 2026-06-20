"""Billing resource — usage, plan catalog, opt-in overage controls, and prepaid token balance.

Lets developers self-meter spend: read current usage (including accrued overage),
fetch the public plan catalog, and toggle usage overage with a monthly cap. For
prepaid-billed accounts, also read the prepaid token balance and add credit via a
Stripe Checkout top-up.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._types import Balance, Plan, Usage

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
