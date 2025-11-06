"""
Google Ads API mock responses for E2E tests.

Provides realistic Google Ads API responses for testing without
hitting real Google Ads API or requiring test accounts.
"""

import re


def get_google_ads_mock(rsps):
    """
    Add Google Ads API mocks to responses object.

    Args:
        rsps: responses.RequestsMock instance
    """
    # Mock GAQL search endpoint
    rsps.add(
        rsps.POST,
        re.compile(r"https://googleads\.googleapis\.com/v\d+/customers/\d+/googleAds:search"),
        json=get_campaign_list_response(),
        status=200,
    )

    # Mock search stream endpoint
    rsps.add(
        rsps.POST,
        re.compile(r"https://googleads\.googleapis\.com/v\d+/customers/\d+/googleAds:searchStream"),
        json=get_campaign_list_response(),
        status=200,
    )

    # Mock OAuth token endpoint
    rsps.add(
        rsps.POST,
        "https://oauth2.googleapis.com/token",
        json={
            "access_token": "ya29.test_access_token",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "https://www.googleapis.com/auth/adwords",
        },
        status=200,
    )

    # Mock customer list endpoint
    rsps.add(
        rsps.GET,
        re.compile(r"https://googleads\.googleapis\.com/v\d+/customers:listAccessibleCustomers"),
        json={
            "resourceNames": [
                "customers/1234567890",
                "customers/9876543210",
            ]
        },
        status=200,
    )


def get_campaign_list_response():
    """
    Realistic Google Ads response for campaign listing query.
    """
    return {
        "results": [
            {
                "campaign": {
                    "resourceName": "customers/1234567890/campaigns/111111",
                    "id": "111111",
                    "name": "Summer Sale 2024",
                    "status": "ENABLED",
                    "advertisingChannelType": "SEARCH",
                },
                "metrics": {
                    "impressions": "15000",
                    "clicks": "450",
                    "costMicros": "25000000",  # $25
                    "conversions": "12.5",
                    "ctr": 0.03,
                },
            },
            {
                "campaign": {
                    "resourceName": "customers/1234567890/campaigns/222222",
                    "id": "222222",
                    "name": "Brand Awareness Campaign",
                    "status": "ENABLED",
                    "advertisingChannelType": "DISPLAY",
                },
                "metrics": {
                    "impressions": "50000",
                    "clicks": "200",
                    "costMicros": "10000000",  # $10
                    "conversions": "5.0",
                    "ctr": 0.004,
                },
            },
        ],
        "fieldMask": "campaign.id,campaign.name,campaign.status,metrics.impressions,metrics.clicks,metrics.cost_micros",  # noqa: E501
        "requestId": "test-request-123",
    }


def get_keyword_list_response():
    """
    Realistic response for keyword query.
    """
    return {
        "results": [
            {
                "adGroupCriterion": {
                    "resourceName": "customers/1234567890/adGroupCriteria/111111~333333",
                    "criterion_id": "333333",
                    "keyword": {
                        "text": "buy running shoes",
                        "matchType": "PHRASE",
                    },
                    "status": "ENABLED",
                },
                "metrics": {
                    "impressions": "1000",
                    "clicks": "50",
                    "costMicros": "5000000",  # $5
                    "conversions": "2.0",
                },
            },
            {
                "adGroupCriterion": {
                    "resourceName": "customers/1234567890/adGroupCriteria/111111~444444",
                    "criterion_id": "444444",
                    "keyword": {
                        "text": "best running shoes",
                        "matchType": "EXACT",
                    },
                    "status": "ENABLED",
                },
                "metrics": {
                    "impressions": "500",
                    "clicks": "30",
                    "costMicros": "3000000",  # $3
                    "conversions": "1.5",
                },
            },
        ],
        "fieldMask": "adGroupCriterion.criterion_id,adGroupCriterion.keyword.text,metrics.impressions",  # noqa: E501
        "requestId": "test-request-456",
    }


def get_search_terms_response():
    """
    Realistic response for search terms query (for negative keyword analysis).
    """
    return {
        "results": [
            {
                "searchTermView": {
                    "resourceName": "customers/1234567890/searchTermViews/111111~222222~running%20shoes",  # noqa: E501
                    "searchTerm": "running shoes",
                    "status": "ADDED",
                },
                "metrics": {
                    "impressions": "100",
                    "clicks": "5",
                    "conversions": "1.0",
                },
            },
            {
                "searchTermView": {
                    "resourceName": "customers/1234567890/searchTermViews/111111~222222~cheap%20running%20shoes",  # noqa: E501
                    "searchTerm": "cheap running shoes",
                    "status": "NONE",
                },
                "metrics": {
                    "impressions": "50",
                    "clicks": "10",
                    "conversions": "0.0",
                },
            },
            {
                "searchTermView": {
                    "resourceName": "customers/1234567890/searchTermViews/111111~222222~free%20running%20shoes",  # noqa: E501
                    "searchTerm": "free running shoes",
                    "status": "NONE",
                },
                "metrics": {
                    "impressions": "30",
                    "clicks": "8",
                    "conversions": "0.0",
                },
            },
        ],
        "requestId": "test-request-789",
    }


def get_accessible_customers_response():
    """
    Realistic response for accessible customers query.
    """
    return {
        "resourceNames": [
            "customers/1234567890",
            "customers/9876543210",
            "customers/5555555555",
        ]
    }


def get_customer_details_response(customer_id="1234567890"):
    """
    Realistic response for customer details.

    Args:
        customer_id: Customer ID to return details for
    """
    return {
        "results": [
            {
                "customer": {
                    "resourceName": f"customers/{customer_id}",
                    "id": customer_id,
                    "descriptiveName": "Acme Corp - Main Account",
                    "currencyCode": "USD",
                    "timeZone": "America/New_York",
                    "manager": False,
                },
            }
        ],
        "requestId": f"test-request-customer-{customer_id}",
    }


def get_error_response(error_code="AUTHENTICATION_ERROR", message="Invalid credentials"):
    """
    Google Ads error response for testing error handling.

    Args:
        error_code: Error code from Google Ads API
        message: Error message

    Returns:
        Error response dict
    """
    return {
        "error": {
            "code": 401 if error_code == "AUTHENTICATION_ERROR" else 400,
            "message": message,
            "status": error_code,
            "details": [
                {
                    "@type": "type.googleapis.com/google.ads.googleads.v15.errors.GoogleAdsFailure",
                    "errors": [
                        {
                            "errorCode": {
                                "authenticationError": error_code,
                            },
                            "message": message,
                        }
                    ],
                }
            ],
        }
    }


def get_empty_results_response():
    """
    Empty results response (no campaigns/keywords found).
    """
    return {
        "results": [],
        "fieldMask": "",
        "requestId": "test-request-empty",
    }
