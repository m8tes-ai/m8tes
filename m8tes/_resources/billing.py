"""Billing resource — usage, plan catalog, and opt-in overage controls.

Lets developers self-meter spend: read current usage (including accrued overage),
fetch the public plan catalog, and toggle usage overage with a monthly cap.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._types import Plan, Usage

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
