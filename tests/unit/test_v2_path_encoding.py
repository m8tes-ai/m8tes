"""A caller's value cannot steer a request off the route its method names.

Resource methods build their URLs with f-strings. Every `{...}` in one of those is a
value the caller supplied, and several are routinely tenant-controlled — an end-user's
`user_id`, an app slug, a filename off a run's artifact list. Interpolated raw, such a
value re-routes the request: `users.get("../account/export")` returned the API key
OWNER's whole account export (200) and `users.delete("../account")` requested deletion
of the account (202), both measured against a live backend.

Percent-encoding alone does NOT fix that, which is the thing this file exists to keep
honest. uvicorn sets `scope["path"]` to the percent-DECODED path and Starlette routes on
it, so `%2F` is a separator to the SERVER even though it is not one to `requests` —
`runs.get("5/messages")` encoded to `/runs/5%2Fmessages` still reaches the messages
route. So `seg` refuses what stays structural after decoding (`/`, `""`, `.`, `..`, and
`None`) and encodes the rest — including a backslash, which is a legal character here
and was measured NOT to act as a separator. There is no exception: the three routes
that declare `{filename:path}` all sanitize the filename to a basename in the handler
they share, so a nested name cannot resolve on any of them either.

Four layers, because each catches what the others cannot:

  * `seg` behaviour — what happens to one value.
  * end-to-end, through the real resource methods and the real `requests` transport, on
    the final prepared URL. `requests` re-quotes and resolves dot segments in what we
    hand it, so the string a method builds is not the string that leaves the process.
  * against a real ASGI app with the production route shapes, asserting which ROUTE was
    reached. The `responses`-based tests above cannot see this by construction, and that
    blind spot is exactly how the `%2F` hole survived the first round of review.
  * an AST guard over every transport call site in the package, so a resource added next
    year cannot reintroduce the hole.

Plus the cross-language corpus (`tests/data/path_encoding_parity.json`), which the
TypeScript client reads too — see `packages/sdk/test/parity.test.ts`.
"""

import ast
import contextlib
import json
from pathlib import Path
import re
from urllib.parse import quote, unquote, urlsplit

import pytest
import requests
import responses

from m8tes import M8tes, ValidationError
from m8tes._http import seg

BASE = "https://api.test/api/v2"
BASE_PATH = urlsplit(BASE).path  # "/api/v2"

PACKAGE_DIR = Path(__file__).resolve().parents[2] / "m8tes"
RESOURCES_DIR = PACKAGE_DIR / "_resources"
CORPUS_PATH = Path(__file__).resolve().parents[1] / "data" / "path_encoding_parity.json"
CORPUS = json.loads(CORPUS_PATH.read_text())

# Every delimiter that would end the segment, start a query, or start a fragment.
STRUCTURAL = "/?#"


def _encode_only(value: str) -> str:
    """What `seg` WOULD have produced if it only encoded — the pre-fix behaviour.

    Used to prove the premise of each refusal, so no test can claim "we refuse X" without
    first demonstrating that sending X lands somewhere else.
    """
    return quote(value, safe="")


def _client() -> M8tes:
    return M8tes(api_key="m8_test", base_url=BASE, timeout=5)


def _catch_all() -> None:
    """Answer any URL, so the test asserts on what the client BUILT, not on a match."""
    for method in (responses.GET, responses.POST, responses.PATCH, responses.DELETE):
        responses.add(method, re.compile(r".*"), body=b"{}", content_type="application/json")


def _send(call) -> str:
    """Drive a real resource method and return the path of the request it sent.

    The stub answers `{}` to every route, so methods that parse a typed response raise a
    KeyError on the way back. That is downstream of the subject here — but ONLY KeyError
    is absorbed: `ValidationError` is what `seg` raises, and swallowing it would let a
    refusal that should have aborted the call read as a successfully-encoded path.
    """
    _catch_all()
    with contextlib.suppress(KeyError):  # the stub body has none of the resource's fields
        call(_client())
    assert len(responses.calls) == 1, f"expected one request, got {len(responses.calls)}"
    return urlsplit(responses.calls[0].request.url).path


# ----------------------------------------------------------------------------- seg


@pytest.mark.parametrize(
    ("value", "encoded"),
    [
        ("x?y", "x%3Fy"),
        ("x#y", "x%23y"),
        ("%2F", "%252F"),  # a pre-encoded slash is encoded again, never passed through
        ("a b", "a%20b"),
        ("a&b=c", "a%26b%3Dc"),
        ("a:b", "a%3Ab"),
        ("a\nb", "a%0Ab"),  # control chars escaped here, not left to the transport
        ("bjørk", "bj%C3%B8rk"),
        ("a-Z_9.~", "a-Z_9.~"),  # unreserved: untouched
        ("..foo...", "..foo..."),  # dots that are not a whole dot segment are fine
        ("a\\b", "a%5Cb"),  # a backslash is a legal character, not a separator here
        (42, "42"),  # ints (every id route) pass through unchanged
    ],
)
def test_seg_encodes_what_it_accepts(value, encoded):
    assert seg(value) == encoded


@pytest.mark.parametrize("value", ["a/b", "../account", "5/messages", "", ".", "..", None])
def test_seg_refuses_what_encoding_cannot_contain(value):
    with pytest.raises(ValidationError):
        seg(value)


def test_a_backslash_is_encoded_rather_than_refused_or_translated(routed):
    """It is a legal character in an id and it does NOT act as a separator on this
    stack — measured, not assumed. Refusing it would break a call that works, and
    translating it to `/` (an earlier draft did) would silently address a different
    resource. So it is encoded, which is what the SDK sent before any of this."""
    for value in ("a\\b", "..\\account"):
        landed = requests.get(f"{routed}/users/{seg(value)}", timeout=5).json()
        assert landed == {"route": "GET USER", "user_id": value}  # stayed inside /users/


def test_seg_refusal_is_catchable_as_an_sdk_error():
    """`except m8tes.M8tesError` is the documented catch-all. A bare `ValueError` would
    escape it, so a caller who handled every SDK error would get an uncaught crash."""
    import m8tes

    with pytest.raises(m8tes.M8tesError):
        seg("../account")


def test_a_refusal_names_the_offending_value_and_says_why():
    """The message is the whole remedy the caller gets — it has to be actionable."""
    with pytest.raises(ValidationError) as exc:
        seg("5/messages")
    assert "5/messages" in str(exc.value)
    assert "path separator" in str(exc.value)
    assert exc.value.status_code is None  # nothing was sent, so there is no HTTP status


def test_seg_output_can_never_contain_a_delimiter():
    for value in ("?", "#", "%2f%3f%23", "a?b#c", " ", "ø"):
        assert not (set(seg(value)) & set(STRUCTURAL)), value


def test_seg_is_lossless():
    """Encoding is reversible — hardening a segment must not change which row it names."""
    for value in ("a b", "bjørk", "a&b=c", "%2F", "!*'()", "..foo..."):
        assert unquote(seg(value)) == value


# ------------------------------------------------------------------- end-to-end


@responses.activate
def test_a_slash_in_user_id_is_refused_before_anything_is_sent():
    """The bug this file exists for. `../account/export` is a DIFFERENT v2 resource,
    owned by the API key holder rather than the end-user the call names."""
    _catch_all()

    with pytest.raises(ValidationError, match="path separator"):
        _client().users.get("../account/export")

    assert len(responses.calls) == 0


@responses.activate
@pytest.mark.parametrize(
    "hostile",
    ["../account", "../../account", "a/b/c", "5/messages", "", ".", "..", "./", None],
)
def test_no_hostile_user_id_reaches_the_network(hostile):
    _catch_all()
    client = _client()  # constructed OUTSIDE raises(): if __init__ ever raised
    # ValidationError, the call under test would never run and this would pass vacuously.

    with pytest.raises(ValidationError):
        client.users.get(hostile)

    assert len(responses.calls) == 0


@responses.activate
@pytest.mark.parametrize(
    ("call", "expected"),
    [
        (lambda c: c.users.get("a?b"), "/users/a%3Fb"),
        (lambda c: c.users.update("a?b", name="x"), "/users/a%3Fb"),
        (lambda c: c.users.delete("a?b"), "/users/a%3Fb"),
        (lambda c: c.apps.connect_api_key("a?b", api_key="sk"), "/apps/a%3Fb/connect/api-key"),
        (lambda c: c.apps.connect_oauth("a?b", redirect_uri="https://x/cb"), "/apps/a%3Fb/connect"),
        (
            lambda c: c.apps.connect_complete("a?b", connection_id="c1"),
            "/apps/a%3Fb/connect/complete",
        ),
        (lambda c: c.apps.provision("a?b"), "/apps/a%3Fb/provision"),
        (lambda c: c.apps.list_triggers("a?b"), "/apps/a%3Fb/triggers"),
        (lambda c: c.apps.list_tools("a?b"), "/apps/a%3Fb/tools"),
        (lambda c: c.apps.disconnect("a?b"), "/apps/a%3Fb/connections"),
        (
            lambda c: c.runs.download_file(42, "q3 final.pdf"),
            "/runs/42/files/q3%20final.pdf/download",
        ),
        (lambda c: c.teammates.get_document(7, "a?b"), "/agents/7/documents/a%3Fb"),
        (lambda c: c.tasks.delete_lesson(1, "a?b"), "/tasks/1/lessons/a%3Fb"),
    ],
)
def test_every_string_valued_segment_is_encoded(call, expected):
    """The routes whose segment is a string by design — the ones a developer is most
    likely to fill from tenant input. One case per route, driven through the real method."""
    assert _send(call) == BASE_PATH + expected


@responses.activate
def test_an_int_route_hardens_without_changing_its_url():
    """`run_id: int` is a type hint, not enforcement — but hardening it must not alter
    the URL of the 99.9% of calls that do pass an int."""
    assert _send(lambda c: c.runs.get(12345)) == f"{BASE_PATH}/runs/12345"


@responses.activate
def test_a_string_smuggled_into_an_int_route_is_refused():
    with pytest.raises(ValidationError):
        _client().runs.cancel("42/../../account")  # type: ignore[arg-type]


def test_the_transport_really_does_resolve_dot_segments():
    """The measurement the refusal rests on. If a future requests/urllib3 stops doing
    this, the refusal is over-strict and this test says so — rather than the reason for
    it living only in a comment."""
    prepared = requests.Request("GET", f"{BASE}/users/..").prepare()
    assert urlsplit(prepared.url).path == f"{BASE_PATH}/"  # NOT /users/..

    # And the escaped form is decoded back to a raw dot segment on the wire, so encoding
    # was never an alternative to refusing.
    escaped = requests.Request("GET", f"{BASE}/users/%2E%2E").prepare()
    assert urlsplit(escaped.url).path == f"{BASE_PATH}/users/.."


# -------------------------------------------------- against a real ASGI router


@pytest.fixture(scope="module")
def routed():
    """A real ASGI server with the production route SHAPES.

    `responses` asserts on the URL the client built. It cannot tell you which route that
    URL reaches, and the gap between those two is where the `%2F` hole lived: the built
    string looked contained while the server decoded it back into a separator. These
    cases assert the ROUTE, which is the property users actually care about.

    Imported directly rather than via `importorskip`: `starlette` and `uvicorn` are
    declared dev dependencies precisely so this cannot silently skip. A skipped security
    test is the failure mode this whole file exists to avoid.
    """
    import socket
    import threading
    import time

    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route
    import uvicorn

    def route(name):
        def handler(request):
            return JSONResponse({"route": name, **dict(request.path_params)})

        return handler

    app = Starlette(
        routes=[
            Route("/api/v2/users/", route("LIST USERS")),
            Route("/api/v2/users/{user_id}", route("GET USER")),
            Route("/api/v2/runs/{run_id}", route("GET RUN")),
            Route("/api/v2/runs/{run_id}/messages", route("GET MESSAGES")),
            Route("/api/v2/runs/{run_id}/files/{filename:path}/download", route("DOWNLOAD")),
        ]
    )

    # Hand uvicorn the ALREADY-BOUND socket rather than a port number we looked up and
    # released — under parallel CI something else can take the port in between.
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen()
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
    threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True).start()
    deadline = time.time() + 20
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    assert server.started, "uvicorn did not start"
    yield f"http://127.0.0.1:{port}/api/v2"
    server.should_exit = True


def test_the_router_fixture_can_distinguish_routes(routed):
    """Without this, every assertion below could pass against a server that answers
    the same thing to everything."""
    assert requests.get(f"{routed}/runs/5", timeout=5).json()["route"] == "GET RUN"
    assert requests.get(f"{routed}/runs/5/messages", timeout=5).json()["route"] == "GET MESSAGES"
    assert requests.get(f"{routed}/users/", timeout=5).json()["route"] == "LIST USERS"


def test_an_encoded_slash_would_reach_a_sibling_route_which_is_why_it_is_refused(routed):
    """The measurement behind `seg`'s refusal of `/`. Encoding is demonstrably not
    enough: the server decodes before routing, so `%2F` selects a different endpoint."""
    leaked = requests.get(f"{routed}/runs/{_encode_only('5/messages')}", timeout=5)
    assert leaked.json()["route"] == "GET MESSAGES", "premise dead: server stopped decoding %2F"

    # Which is why the SDK never builds that URL in the first place.
    with pytest.raises(ValidationError):
        M8tes(api_key="m8_test", base_url=routed).runs.get("5/messages")  # type: ignore[arg-type]


def test_an_empty_segment_would_reach_the_collection_which_is_why_it_is_refused(routed):
    leaked = requests.get(f"{routed}/users/{_encode_only('')}", timeout=5)
    assert leaked.json()["route"] == "LIST USERS", "premise dead: empty segment stopped collapsing"

    with pytest.raises(ValidationError):
        M8tes(api_key="m8_test", base_url=routed).users.get("")


def test_an_accepted_hostile_value_still_lands_on_its_own_route(routed):
    """The positive half of the ASGI layer, and the one a double-decoding proxy would
    break: a caller id that is ALREADY percent-encoded gets encoded again, and must
    arrive as the literal text rather than as a separator."""
    got = requests.get(f"{routed}/users/{seg('%2F')}", timeout=5).json()
    assert got == {"route": "GET USER", "user_id": "%2F"}, "one decode too many"

    for hostile in ("a?b", "a#b", "a%2E%2E", "..foo.."):
        landed = requests.get(f"{routed}/users/{seg(hostile)}", timeout=5).json()
        assert landed == {"route": "GET USER", "user_id": hostile}, hostile


def test_a_legal_value_still_reaches_its_own_route(routed):
    """The other half: hardening must not break the calls that were always fine, and the
    encoded form must arrive DECODED to the value the caller passed."""
    got = requests.get(f"{routed}/users/{seg('ann bjørk')}", timeout=5).json()
    assert got == {"route": "GET USER", "user_id": "ann bjørk"}

    flat = requests.get(f"{routed}/runs/42/files/{seg('q3 final.pdf')}/download", timeout=5).json()
    assert flat == {"route": "DOWNLOAD", "run_id": "42", "filename": "q3 final.pdf"}


# ------------------------------------------------------------------------ parity


@pytest.mark.parametrize("case", CORPUS["cases"], ids=[c["name"] for c in CORPUS["cases"]])
@responses.activate
def test_matches_the_cross_language_corpus(case):
    """The Python half of the corpus the TypeScript client also reads. A change to either
    encoder that the other does not make fails on one side."""
    spec = case["python"]
    args = [case["value"] if a == "$VALUE" else a for a in spec["args"]]

    path = _send(
        lambda c: getattr(getattr(c, spec["resource"]), spec["method"])(
            *args, **spec.get("kwargs", {})
        )
    )

    assert path == BASE_PATH + case["expected_path"]


@pytest.mark.parametrize("case", CORPUS["refused"], ids=[c["name"] for c in CORPUS["refused"]])
@responses.activate
def test_the_corpus_refusals_are_refused(case):
    """Both clients refuse these before anything is sent — this is the Python half;
    `parity.test.ts` asserts the TypeScript half throws on the same corpus entries."""
    _catch_all()
    spec = case["python"]
    args = [case["value"] if a == "$VALUE" else a for a in spec["args"]]
    method = getattr(getattr(_client(), spec["resource"]), spec["method"])  # outside raises()

    with pytest.raises(ValidationError):
        method(*args, **spec.get("kwargs", {}))

    assert len(responses.calls) == 0

    # The corpus convention: `typescript_path` on a refused entry pinned the URL the
    # TypeScript client STILL BUILT for a value Python refused. Since the TS client
    # refuses the same set, the field goes away — one creeping back in would claim a
    # TS regression as documented behavior, so its absence is asserted, not assumed.
    assert "typescript_path" not in case, (
        f"{case['name']}: refused entries carry no typescript_path — both clients "
        f"refuse this value; if the TypeScript client started building a URL for it "
        f"again, that is a regression to fix, not to record"
    )


def test_the_corpus_covers_the_routes_that_take_a_string_segment():
    """A corpus that quietly shrank to one easy route would still pass every case."""
    routes = {(c["python"]["resource"], c["python"]["method"]) for c in CORPUS["cases"]}
    routes |= {(c["python"]["resource"], c["python"]["method"]) for c in CORPUS["refused"]}
    assert {("users", "get"), ("apps", "connect_api_key"), ("runs", "download_file")} <= routes
    assert len(CORPUS["cases"]) >= 8 and len(CORPUS["refused"]) >= 7


def test_a_documented_divergence_is_only_ever_cosmetic():
    """`typescript_path` is an escape hatch on the one file pinning the TS encoder. Left
    to a free-text reason it would let a real TS regression be documented into green.

    The predicate has to be ROUTE-aware, not decode-aware: comparing `unquote(ts) ==
    unquote(expected)` alone accepts `/users/a%2Fb` against `/users/a/b`, which is two
    different endpoints and is precisely the vulnerability this branch closes. So the
    RAW separator count must match — the number of path components is what selects the
    route. There is no exception: the three routes declaring `{filename:path}` all
    sanitize their value to a basename in the handler, so a divergence there would not
    be free either.
    """
    divergent = [c for c in CORPUS["cases"] if c.get("typescript_path")]
    assert divergent, "no divergent case left — this guard would pass over nothing"
    for case in divergent:
        ts = case["typescript_path"]
        assert case.get("why_divergent"), case["name"]
        expected = case["expected_path"]
        assert unquote(ts) == unquote(expected), case["name"]
        assert ts.count("/") == expected.count("/"), (
            f"{case['name']}: the two clients build a different NUMBER of path "
            f"components, so they select different routes — not cosmetic"
        )


# ------------------------------------------------------------------- drift guard


_HTTP_VERBS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"})

# The v1 session transport's own generic wrappers, which forward their `path` parameter
# straight through. They are the transport, not a call site that builds a path from a
# caller's value. An EXPLICIT list, not a heuristic: an earlier version exempted any bare
# Name that happened to match a parameter name, which also waived
# `path = f"/users/{uid}"; self._http.request("GET", path)` — a shape no site uses
# today, and one this guard must keep unusable.
# Adding a line here is a deliberate act that shows up in review.
_FORWARDING_WRAPPERS = frozenset(
    {("auth/http.py", 397), ("auth/http.py", 406), ("auth/http.py", 415), ("auth/http.py", 423)}
)


def _collect_path_arguments() -> list[tuple[str, int, ast.expr]]:
    """Every path expression handed to a `.request(...)` / `.stream(...)` transport call.

    Matched on the CALL, not on the receiver's spelling: an earlier version required the
    receiver to be literally `self._http`, and hoisting it to a local (`http = self._http`)
    hid the site completely while the guard stayed green. Over-matching here costs a false
    positive; under-matching costs the vulnerability — so the only narrowing is the
    `(METHOD, PATH, ...)` shape, keyed on an uppercase string literal first argument.

    Scans the whole package, not just `_resources/`: a nested subpackage was invisible to
    the earlier non-recursive glob.
    """
    found: list[tuple[str, int, ast.expr]] = []
    for file in sorted(PACKAGE_DIR.rglob("*.py")):
        rel = str(file.relative_to(PACKAGE_DIR))
        tree = ast.parse(file.read_text(), filename=str(file))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in ("request", "stream"):
                continue
            # The path is the second positional arg, or a `path=` keyword. Reading only
            # positionals let `request("GET", path=f"/users/{uid}")` through.
            path: ast.expr | None = node.args[1] if len(node.args) >= 2 else None
            for kw in node.keywords:
                if kw.arg == "path":
                    path = kw.value
            if path is None:
                continue
            method = node.args[0] if node.args else None
            if not (isinstance(method, ast.Constant) and isinstance(method.value, str)):
                continue
            # `.upper()`, not `.isupper()`: `requests` uppercases the verb, so a
            # lowercase literal is a real call site and was previously skipped.
            if method.value.upper() not in _HTTP_VERBS:
                continue
            if (rel, node.lineno) in _FORWARDING_WRAPPERS:
                continue
            found.append((rel, node.lineno, path))
    return found


# Parsed once — two tests read it, and the earlier version re-parsed the whole package
# for each of them.
PATH_ARGUMENTS = _collect_path_arguments()


def test_the_guard_can_see_the_call_sites_it_guards():
    """A matcher that found nothing would pass every assertion below. Pinned near the
    real number rather than at a slack floor: at `>= 80` (with 135 actual) more than a
    third of the package could drop out of the scan before this fired."""
    sites = PATH_ARGUMENTS
    assert len(sites) >= 130, f"only {len(sites)} call sites found — the AST matcher broke"
    files = {f for f, _, _ in sites}
    expected = {
        str(p.relative_to(PACKAGE_DIR))
        for p in PACKAGE_DIR.rglob("*.py")
        if "_http.request(" in p.read_text() or "_http.stream(" in p.read_text()
    }
    assert expected - files == set(), f"modules the matcher cannot see: {expected - files}"


def test_every_dynamic_path_segment_goes_through_seg():
    offenders = []
    for filename, lineno, node in PATH_ARGUMENTS:
        if isinstance(node, ast.Constant):
            continue  # a static path has no caller value in it
        if not isinstance(node, ast.JoinedStr):
            offenders.append(f"{filename}:{lineno} — path is not a literal f-string")
            continue
        for part in node.values:
            if not isinstance(part, ast.FormattedValue):
                continue
            call = part.value
            encoder = getattr(call.func, "id", None) if isinstance(call, ast.Call) else None
            if encoder != "seg":
                offenders.append(
                    f"{filename}:{lineno} — {ast.unparse(part.value)} is interpolated raw; "
                    f"wrap it in seg()"
                )
    assert offenders == []


def test_nothing_can_hide_a_call_site_or_substitute_a_different_encoder():
    """Evasions the call-site guard cannot see on its own, each one measured against an
    earlier version of this guard rather than imagined:

      * aliasing the transport to a local, which hid the call site entirely;
      * binding the NAME `seg` to something that does not encode — `def seg`, but also
        `seg = lambda v: v` and `from urllib.parse import quote as seg`. The call-site
        guard only checks the name, so any of these defeats the whole module at one line.

    `_http.py` is the one module allowed to define them.
    """
    offenders = []
    encoders = {"seg"}
    for file in sorted(PACKAGE_DIR.rglob("*.py")):
        tree = ast.parse(file.read_text(), filename=str(file))
        rel = str(file.relative_to(PACKAGE_DIR))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Attribute)
                and node.value.attr == "_http"
            ):
                offenders.append(f"{rel}:{node.lineno} — aliases self._http to a local")
            if rel == "_http.py":
                continue
            bound: list[str] = []
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                bound = [node.name]
            elif isinstance(node, ast.Assign):
                bound = [t.id for t in node.targets if isinstance(t, ast.Name)]
            elif isinstance(node, ast.ImportFrom):
                # `from .._http import seg` is the ONLY legitimate binding.
                bound = [
                    a.asname or a.name
                    for a in node.names
                    if (a.asname or a.name) in encoders and a.name not in encoders
                ]
            for name in bound:
                if name in encoders:
                    offenders.append(
                        f"{rel}:{node.lineno} — binds {name!r} to something other than "
                        f"the encoder in _http.py"
                    )
    assert offenders == []
