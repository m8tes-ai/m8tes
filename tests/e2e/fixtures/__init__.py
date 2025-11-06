"""
E2E test fixtures for mocking external APIs.

Provides realistic mock responses for:
- OpenAI API (chat completions, streaming)
- Google Ads API (GAQL queries, campaigns, keywords)
- Meta Ads API (campaigns, ad sets, targeting)
"""

from .google_ads_responses import get_google_ads_mock
from .meta_ads_responses import get_meta_ads_mock
from .openai_responses import get_openai_mock

__all__ = [
    "get_google_ads_mock",
    "get_meta_ads_mock",
    "get_openai_mock",
]
