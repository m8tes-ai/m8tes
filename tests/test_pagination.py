"""SyncPage semantics."""

from m8tes._types import SyncPage


def test_page_is_iterable_over_current_items():
    """Docs iterate the page directly (`for policy in client.permissions.list():`)
    — 2026-08-16 executable-docs gate found this raising TypeError. Page-local
    iteration only; crossing pages stays explicit via auto_paging_iter()."""
    page = SyncPage(
        data=[1, 2, 3],
        has_more=True,
        _fetch_next=lambda **kw: SyncPage(data=[4], has_more=False),
    )
    assert list(page) == [1, 2, 3]  # does NOT auto-fetch page 2


def test_auto_paging_iter_still_crosses_pages():
    from types import SimpleNamespace as N

    one, two, three = N(id=1), N(id=2), N(id=3)
    page = SyncPage(
        data=[one, two],
        has_more=True,
        _fetch_next=lambda **kw: SyncPage(data=[three], has_more=False),
    )
    assert list(page.auto_paging_iter()) == [one, two, three]


def test_list_continuation_preserves_caller_limit():
    """auto_paging_iter must keep the caller's page size on EVERY page. The
    continuation closure previously dropped `limit`, so page 2+ silently fell
    back to the server default of 20 (Greptile P1, 2026-08-17)."""
    from m8tes import M8tes

    sent = []

    class _FakeResp:
        def __init__(self, data, has_more):
            self._b = {"data": data, "has_more": has_more}

        def json(self):
            return self._b

    class _FakeHTTP:
        def request(self, method, path, params=None, **kw):
            p = dict(params or {})
            sent.append(p)
            if "starting_after" not in p:  # page 1
                return _FakeResp([{"id": 1}, {"id": 2}], True)
            return _FakeResp([{"id": 3}], False)  # page 2, done

    client = M8tes(api_key="m8_test", base_url="http://x/api/v2")
    client.runs._http = _FakeHTTP()
    list(client.runs.list(limit=7).auto_paging_iter())
    assert sent[0].get("limit") == 7
    assert len(sent) >= 2, "continuation request never fired"
    assert sent[1].get("limit") == 7, f"continuation dropped limit: {sent[1]}"


def test_every_paginated_list_forwards_limit():
    """Drift guard (class-proof): every paginated list-style method that accepts
    a `limit` must forward it in its `_fetch_next` continuation closure, or
    page 2+ silently resets to the server default. AST, not text. apps.list is
    exempt — GET /apps is not paginated and documents ignoring limit."""
    import ast
    from pathlib import Path

    res_dir = Path(__file__).resolve().parent.parent / "m8tes" / "_resources"
    offenders = []
    for f in sorted(res_dir.glob("*.py")):
        if f.name == "apps.py":
            continue
        tree = ast.parse(f.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name not in ("list", "receipts", "usage", "list_deliveries"):
                continue
            if not any(a.arg == "limit" for a in node.args.kwonlyargs + node.args.args):
                continue
            fwd = any(
                isinstance(c, ast.keyword) and c.arg == "limit"
                for inner in ast.walk(node)
                if isinstance(inner, ast.FunctionDef) and inner.name == "_fetch_next"
                for c in ast.walk(inner)
            )
            if not fwd:
                offenders.append(f"{f.name}::{node.name}")
    assert not offenders, f"list methods drop limit on continuation: {offenders}"
