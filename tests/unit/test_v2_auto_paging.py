"""Tests for SyncPage.auto_paging_iter() and M8tes context manager."""

from m8tes._client import M8tes
from m8tes._types import SyncPage, Teammate

BASE = "https://api.test/v2"


class TestAutoPagingIter:
    def test_single_page(self):
        """auto_paging_iter yields all items from a single page (has_more=False)."""
        page = SyncPage(
            data=[
                Teammate(
                    id=1,
                    name="A",
                    instructions=None,
                    tools=[],
                    role=None,
                    goals=None,
                    user_id=None,
                    metadata=None,
                    allowed_senders=None,
                    status="enabled",
                    created_at="",
                ),
                Teammate(
                    id=2,
                    name="B",
                    instructions=None,
                    tools=[],
                    role=None,
                    goals=None,
                    user_id=None,
                    metadata=None,
                    allowed_senders=None,
                    status="enabled",
                    created_at="",
                ),
            ],
            has_more=False,
        )
        items = list(page.auto_paging_iter())
        assert len(items) == 2
        assert items[0].id == 1
        assert items[1].id == 2

    def test_multi_page(self):
        """auto_paging_iter walks through multiple pages via _fetch_next."""
        page2 = SyncPage(
            data=[
                Teammate(
                    id=3,
                    name="C",
                    instructions=None,
                    tools=[],
                    role=None,
                    goals=None,
                    user_id=None,
                    metadata=None,
                    allowed_senders=None,
                    status="enabled",
                    created_at="",
                ),
            ],
            has_more=False,
        )

        def fetch_next(**kw):
            assert kw.get("starting_after") == 2
            return page2

        page1 = SyncPage(
            data=[
                Teammate(
                    id=1,
                    name="A",
                    instructions=None,
                    tools=[],
                    role=None,
                    goals=None,
                    user_id=None,
                    metadata=None,
                    allowed_senders=None,
                    status="enabled",
                    created_at="",
                ),
                Teammate(
                    id=2,
                    name="B",
                    instructions=None,
                    tools=[],
                    role=None,
                    goals=None,
                    user_id=None,
                    metadata=None,
                    allowed_senders=None,
                    status="enabled",
                    created_at="",
                ),
            ],
            has_more=True,
            _fetch_next=fetch_next,
        )
        items = list(page1.auto_paging_iter())
        assert len(items) == 3
        assert [i.id for i in items] == [1, 2, 3]

    def test_empty_page(self):
        """auto_paging_iter on empty page yields nothing."""
        page = SyncPage(data=[], has_more=False)
        items = list(page.auto_paging_iter())
        assert items == []

    def test_no_fetch_next(self):
        """auto_paging_iter stops if _fetch_next is None even if has_more=True."""
        page = SyncPage(
            data=[
                Teammate(
                    id=1,
                    name="A",
                    instructions=None,
                    tools=[],
                    role=None,
                    goals=None,
                    user_id=None,
                    metadata=None,
                    allowed_senders=None,
                    status="enabled",
                    created_at="",
                ),
            ],
            has_more=True,
            _fetch_next=None,
        )
        items = list(page.auto_paging_iter())
        assert len(items) == 1


class TestContextManager:
    def test_enter_returns_self(self):
        """__enter__ returns the client instance."""
        client = M8tes(api_key="m8_test", base_url="http://localhost")
        ctx = client.__enter__()
        assert ctx is client
        client.__exit__()

    def test_with_statement(self):
        """M8tes works with `with` statement."""
        with M8tes(api_key="m8_test", base_url="http://localhost") as client:
            assert client._http is not None
        # Session closed — no crash

    def test_close_idempotent(self):
        """Calling close() multiple times doesn't raise."""
        client = M8tes(api_key="m8_test", base_url="http://localhost")
        client.close()
        client.close()  # second close should not raise
