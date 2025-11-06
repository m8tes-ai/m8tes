"""
Meta Ads API mock responses for E2E tests.

Provides realistic Meta Ads API responses for testing without
hitting real Meta Ads API or requiring test accounts.
"""

import re


def get_meta_ads_mock(rsps):
    """
    Add Meta Ads API mocks to responses object.

    Args:
        rsps: responses.RequestsMock instance
    """
    # Mock campaigns endpoint
    rsps.add(
        rsps.GET,
        re.compile(r"https://graph\.facebook\.com/v\d+\.\d+/act_\d+/campaigns"),
        json=get_campaigns_response(),
        status=200,
    )

    # Mock ad sets endpoint
    rsps.add(
        rsps.GET,
        re.compile(r"https://graph\.facebook\.com/v\d+\.\d+/act_\d+/adsets"),
        json=get_adsets_response(),
        status=200,
    )

    # Mock OAuth token endpoint
    rsps.add(
        rsps.GET,
        "https://graph.facebook.com/v18.0/oauth/access_token",
        json={
            "access_token": "EAAtest_long_lived_token",
            "token_type": "bearer",
            "expires_in": 5184000,  # 60 days
        },
        status=200,
    )

    # Mock user accounts endpoint
    rsps.add(
        rsps.GET,
        re.compile(r"https://graph\.facebook\.com/v\d+\.\d+/me/adaccounts"),
        json={
            "data": [
                {
                    "account_id": "1234567890",
                    "id": "act_1234567890",
                    "name": "Acme Corp Ad Account",
                },
                {
                    "account_id": "9876543210",
                    "id": "act_9876543210",
                    "name": "Acme Corp - Brand",
                },
            ],
            "paging": {
                "cursors": {
                    "before": "test_before",
                    "after": "test_after",
                }
            },
        },
        status=200,
    )


def get_campaigns_response():
    """
    Realistic Meta Ads response for campaigns listing.
    """
    return {
        "data": [
            {
                "id": "120210000000001",
                "name": "Summer Sale Campaign",
                "status": "ACTIVE",
                "objective": "OUTCOME_SALES",
                "daily_budget": "5000",  # cents
                "insights": {
                    "data": [
                        {
                            "impressions": "25000",
                            "clicks": "350",
                            "spend": "125.50",
                            "ctr": "1.4",
                            "cpc": "0.36",
                        }
                    ]
                },
            },
            {
                "id": "120210000000002",
                "name": "Brand Awareness Campaign",
                "status": "ACTIVE",
                "objective": "OUTCOME_AWARENESS",
                "daily_budget": "3000",  # cents
                "insights": {
                    "data": [
                        {
                            "impressions": "75000",
                            "clicks": "150",
                            "spend": "85.25",
                            "ctr": "0.2",
                            "cpc": "0.57",
                        }
                    ]
                },
            },
        ],
        "paging": {
            "cursors": {
                "before": "test_before_cursor",
                "after": "test_after_cursor",
            }
        },
    }


def get_adsets_response():
    """
    Realistic Meta Ads response for ad sets listing.
    """
    return {
        "data": [
            {
                "id": "120210000000101",
                "name": "US - 18-35 - Interests",
                "campaign_id": "120210000000001",
                "status": "ACTIVE",
                "daily_budget": "2500",
                "targeting": {
                    "geo_locations": {
                        "countries": ["US"],
                    },
                    "age_min": 18,
                    "age_max": 35,
                },
                "insights": {
                    "data": [
                        {
                            "impressions": "15000",
                            "clicks": "210",
                            "spend": "75.30",
                        }
                    ]
                },
            },
            {
                "id": "120210000000102",
                "name": "Canada - 25-45 - Lookalike",
                "campaign_id": "120210000000001",
                "status": "ACTIVE",
                "daily_budget": "2500",
                "targeting": {
                    "geo_locations": {
                        "countries": ["CA"],
                    },
                    "age_min": 25,
                    "age_max": 45,
                },
                "insights": {
                    "data": [
                        {
                            "impressions": "10000",
                            "clicks": "140",
                            "spend": "50.20",
                        }
                    ]
                },
            },
        ],
        "paging": {
            "cursors": {
                "before": "test_before_cursor_adsets",
                "after": "test_after_cursor_adsets",
            }
        },
    }


def get_error_response(error_code=190, message="Invalid OAuth access token"):
    """
    Meta Ads error response for testing error handling.

    Args:
        error_code: Error code from Meta API
        message: Error message

    Returns:
        Error response dict
    """
    return {
        "error": {
            "message": message,
            "type": "OAuthException",
            "code": error_code,
            "fbtrace_id": "test_trace_id_12345",
        }
    }


def get_empty_results_response():
    """
    Empty results response (no campaigns found).
    """
    return {
        "data": [],
        "paging": {
            "cursors": {
                "before": "test_empty_before",
                "after": "test_empty_after",
            }
        },
    }
