"""Tests for the v2 teammate-templates catalog resource."""

import responses

from m8tes._http import HTTPClient
from m8tes._resources.teammate_templates import TeammateTemplates
from m8tes._types import TeammateTemplate

BASE = "https://api.test/v2"


def _http() -> HTTPClient:
    return HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)


@responses.activate
def test_list_templates_parses_and_hits_trailing_slash():
    responses.add(
        responses.GET,
        f"{BASE}/agent-templates/",
        json={
            "data": [
                {
                    "slug": "ppc-manager",
                    "name": "PPC Manager",
                    "description": "Runs Google Ads.",
                    "logo_ref": "google-ads",
                    "required_integrations": ["google_ads"],
                    "role": "Paid search operator",
                    "goals": "Reduce wasted spend.",
                    "default_tasks": [{"slug": "weekly-search-term-review"}],
                }
            ]
        },
        status=200,
    )

    tpls = TeammateTemplates(_http()).list()

    assert len(tpls) == 1
    t = tpls[0]
    assert isinstance(t, TeammateTemplate)
    assert t.slug == "ppc-manager"
    assert t.required_integrations == ["google_ads"]
    assert t.default_tasks[0]["slug"] == "weekly-search-term-review"
    # Trailing slash means no 307 redirect.
    assert responses.calls[0].request.url == f"{BASE}/agent-templates/"
    assert not responses.calls[0].response.history
