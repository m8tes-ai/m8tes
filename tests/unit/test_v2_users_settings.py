"""Tests for v2 SDK Users and Settings resources."""

import responses

from m8tes._http import HTTPClient
from m8tes._resources.settings import Settings
from m8tes._resources.users import Users
from m8tes._types import AccountSettings, EndUser, SyncPage

BASE = "https://api.test/v2"


# ── Users ────────────────────────────────────────────────────────────


class TestUsers:
    @responses.activate
    def test_create(self):
        http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
        responses.add(
            responses.POST,
            f"{BASE}/users",
            json={
                "id": 1,
                "user_id": "cust_001",
                "name": "Alice",
                "email": "alice@example.com",
                "company": "Acme",
                "metadata": {"plan": "pro"},
                "created_at": "2026-01-01T00:00:00Z",
            },
        )
        user = Users(http).create(
            user_id="cust_001",
            name="Alice",
            email="alice@example.com",
            company="Acme",
            metadata={"plan": "pro"},
        )
        assert isinstance(user, EndUser)
        assert user.user_id == "cust_001"
        assert user.name == "Alice"
        assert user.email == "alice@example.com"
        assert user.company == "Acme"
        assert user.metadata == {"plan": "pro"}

        body = responses.calls[0].request.body
        assert b'"user_id": "cust_001"' in body or b'"user_id":"cust_001"' in body

    @responses.activate
    def test_create_minimal(self):
        http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
        responses.add(
            responses.POST,
            f"{BASE}/users",
            json={"id": 2, "user_id": "cust_002", "created_at": "2026-01-01T00:00:00Z"},
        )
        user = Users(http).create(user_id="cust_002")
        assert user.user_id == "cust_002"
        assert user.name is None
        assert user.metadata is None

    @responses.activate
    def test_list(self):
        http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
        responses.add(
            responses.GET,
            f"{BASE}/users",
            json={
                "data": [
                    {"id": 1, "user_id": "cust_001", "created_at": "2026-01-01T00:00:00Z"},
                    {"id": 2, "user_id": "cust_002", "created_at": "2026-01-01T00:00:00Z"},
                ],
                "has_more": False,
            },
        )
        page = Users(http).list()
        assert isinstance(page, SyncPage)
        assert len(page.data) == 2
        assert page.data[0].user_id == "cust_001"
        assert not page.has_more

    @responses.activate
    def test_list_auto_paging(self):
        """Verify _fetch_next is wired correctly for auto-pagination."""
        http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
        # Page 1
        responses.add(
            responses.GET,
            f"{BASE}/users",
            json={
                "data": [{"id": 1, "user_id": "cust_001", "created_at": "2026-01-01T00:00:00Z"}],
                "has_more": True,
            },
        )
        # Page 2
        responses.add(
            responses.GET,
            f"{BASE}/users",
            json={
                "data": [{"id": 2, "user_id": "cust_002", "created_at": "2026-01-01T00:00:00Z"}],
                "has_more": False,
            },
        )
        page = Users(http).list()
        all_users = list(page.auto_paging_iter())
        assert len(all_users) == 2
        assert all_users[1].user_id == "cust_002"

    @responses.activate
    def test_get(self):
        http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
        responses.add(
            responses.GET,
            f"{BASE}/users/cust_001",
            json={
                "id": 1,
                "user_id": "cust_001",
                "name": "Alice",
                "created_at": "2026-01-01T00:00:00Z",
            },
        )
        user = Users(http).get("cust_001")
        assert user.user_id == "cust_001"
        assert user.name == "Alice"

    @responses.activate
    def test_update(self):
        http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
        responses.add(
            responses.PATCH,
            f"{BASE}/users/cust_001",
            json={
                "id": 1,
                "user_id": "cust_001",
                "name": "Bob",
                "created_at": "2026-01-01T00:00:00Z",
            },
        )
        user = Users(http).update("cust_001", name="Bob")
        assert user.name == "Bob"

    @responses.activate
    def test_update_omits_none_fields(self):
        """Only non-None fields are sent in the PATCH body."""
        http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
        responses.add(
            responses.PATCH,
            f"{BASE}/users/cust_001",
            json={
                "id": 1,
                "user_id": "cust_001",
                "email": "new@test.com",
                "created_at": "2026-01-01T00:00:00Z",
            },
        )
        Users(http).update("cust_001", email="new@test.com")
        body = responses.calls[0].request.body
        # name/company/metadata should NOT be in the body
        assert b"name" not in body
        assert b"company" not in body
        assert b"metadata" not in body

    @responses.activate
    def test_delete(self):
        http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
        responses.add(responses.DELETE, f"{BASE}/users/cust_001", status=204)
        Users(http).delete("cust_001")
        assert responses.calls[0].request.method == "DELETE"


# ── Settings ─────────────────────────────────────────────────────────


class TestSettings:
    @responses.activate
    def test_get(self):
        http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
        responses.add(
            responses.GET,
            f"{BASE}/settings",
            json={"company_research": True},
        )
        settings = Settings(http).get()
        assert isinstance(settings, AccountSettings)
        assert settings.company_research is True

    @responses.activate
    def test_update(self):
        http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
        responses.add(
            responses.PATCH,
            f"{BASE}/settings",
            json={"company_research": False},
        )
        settings = Settings(http).update(company_research=False)
        assert settings.company_research is False

        body = responses.calls[0].request.body
        assert b"company_research" in body

    @responses.activate
    def test_update_omits_none(self):
        """Calling update() with no args sends empty body."""
        http = HTTPClient(api_key="m8_test", base_url=BASE, timeout=5)
        responses.add(
            responses.PATCH,
            f"{BASE}/settings",
            json={"company_research": True},
        )
        Settings(http).update()
        body = responses.calls[0].request.body
        assert body == b"{}"
