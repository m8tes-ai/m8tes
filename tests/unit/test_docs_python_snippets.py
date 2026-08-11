"""Guard: the Python the docs tell people to run must actually be Python, and must
actually pass the flag that keeps a failed run from looking like a successful one.

The frontend already pins these snippets, but only as SUBSTRINGS
(`expect(snippet).toContain("raise_on_error=True")`). An independent review pointed out
what that does not catch: the text could be moved into a `#` comment, placed outside the
`stream_text(...)` call, or sit in a snippet that does not parse at all, and every one of
those still passes a `toContain`. The frontend cannot do better — it has no Python parser.
This suite does.

So the assertions here are structural, not textual: parse the snippet with `ast`, find the
call to `runs.stream_text`, and require `raise_on_error=True` to be a real keyword argument
ON that call. `ast.parse` also makes "is this valid Python" a real question rather than an
assumed one — these strings are copy-pasted by a developer as the first code they ever run
against us, so a syntax error here is a first-impression bug.
"""

from __future__ import annotations

import ast
from pathlib import Path
import re

import pytest

# tests/unit/ -> tests/ -> the SDK package root. Same anchor and rationale as
# test_runtime_event_parity.py; see test_path_arithmetic_is_correct there.
_SDK_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = _SDK_ROOT.parents[1]
_SNIPPETS_TS = (
    _REPO_ROOT / "vite-frontend" / "src" / "constants" / "docs" / "shared-quickstart-snippets.ts"
)


def _in_monorepo() -> bool:
    return _SDK_ROOT.name == "py" and _SDK_ROOT.parent.name == "sdk"


requires_frontend = pytest.mark.skipif(
    not _in_monorepo(), reason="standalone SDK repo — vite-frontend does not exist here"
)


def _python_snippets() -> dict[str, str]:
    """Every Python block in the shared snippets module, keyed by a readable name.

    Template interpolations (`${...}`) are stripped to their concrete form so the result
    is parseable: the `user_id` line is conditional in TypeScript, and both branches are
    covered because we render it once with the line and once without.
    """
    text = _SNIPPETS_TS.read_text()
    out: dict[str, str] = {}

    quickstart = re.search(r"export const PYTHON_QUICKSTART_SNIPPET = `(.*?)`;", text, re.DOTALL)
    assert quickstart, "PYTHON_QUICKSTART_SNIPPET not found — did the export get renamed?"
    out["quickstart"] = quickstart.group(1)

    console = re.search(
        r"function pythonFirstRun\([^)]*\)[^{]*\{\s*.*?return `(.*?)`;", text, re.DOTALL
    )
    assert console, "pythonFirstRun's template literal not found"
    body = console.group(1)
    # The conditional `user_id` line is a multi-line `${ ... }` interpolation whose
    # closing brace sits alone on a tab-indented line. Match to THAT brace, not to the
    # first `}` encountered — the first one belongs to the nested `${userId}` and stopping
    # there leaves TypeScript residue in the middle of the Python, which is exactly how
    # the first version of this helper produced a snippet that could not parse.
    _INTERPOLATION = r"\$\{[\s\S]*?^\s*\}"
    out["console_with_user_id"] = re.sub(
        _INTERPOLATION, '\n    user_id="customer_42",', body, flags=re.M
    )
    out["console_no_user_id"] = re.sub(_INTERPOLATION, "", body, flags=re.M)
    for name, src in out.items():
        assert "${" not in src, f"{name} still contains a TypeScript interpolation: {src!r}"
    return out


@requires_frontend
def test_the_guard_can_actually_see_the_snippets():
    """Anti-vacuity: a regex that silently matched nothing would pass everything below."""
    assert _SNIPPETS_TS.is_file(), f"{_SNIPPETS_TS} is missing"
    snippets = _python_snippets()
    assert set(snippets) == {"quickstart", "console_with_user_id", "console_no_user_id"}
    for name, src in snippets.items():
        assert "stream_text" in src, f"{name} does not look like a first-run snippet"


@requires_frontend
@pytest.mark.parametrize("name", ["quickstart", "console_with_user_id", "console_no_user_id"])
def test_every_documented_kwarg_exists_on_the_real_method(name):
    """The docs may not call `stream_text` with an argument the SDK does not accept.

    This is the guard for the incident that produced this test file. #1272 documented
    `raise_on_error=True` and shipped the SDK that supports it — but not a version bump, so
    PyPI kept serving the previous build and a developer copy-pasting the quickstart got
    `TypeError: Runs.stream_text() got an unexpected keyword argument 'raise_on_error'`.

    It checks the SOURCE tree, so it cannot catch the packaging half of that (the publish
    job fixing that is filed in TODOS.md as P1). What it does catch is the simpler and more
    likely half: a snippet drifting to an argument that does not exist at all — a typo, a
    renamed parameter, or copy from a proposal that never shipped.
    """
    import inspect

    from m8tes._resources.runs import Runs

    tree = ast.parse(_python_snippets()[name])
    sig = inspect.signature(Runs.stream_text)
    accepted = set(sig.parameters)
    for call in ast.walk(tree):
        if not (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "stream_text"
        ):
            continue
        # Positional args are their own TypeError, and checking only keywords misses it:
        # every public parameter on `stream_text` is keyword-only, so
        # `stream_text("prompt", raise_on_error=True)` satisfies a keywords-only check and
        # still dies with "takes 1 positional argument but 2 were given".
        assert not call.args, (
            f"{name}: the docs pass {len(call.args)} positional argument(s) to stream_text, "
            "whose public parameters are all keyword-only. Copy-pasting this raises."
        )
        for kw in call.keywords:
            assert kw.arg in accepted, (
                f"{name}: the docs pass `{kw.arg}=` to stream_text, which does not accept "
                f"it. A developer copy-pasting this gets a TypeError. Accepted: "
                f"{sorted(accepted - {'self'})}"
            )


#: Every checked-in file that declares an `m8tes>=` install floor. `llms-full.txt` is a
#: GENERATED but COMMITTED corpus, and it is in this list on purpose: it is what coding
#: agents read, it shipped contradicting the hand-written docs, and "the build regenerates
#: it" does not help a guard that runs before the build.
_FLOOR_FILES = (
    "vite-frontend/src/constants/docs/quickstart.ts",
    "vite-frontend/src/constants/docs/cli.ts",
    "sdk/py/README.md",
    "vite-frontend/public/llms-full.txt",
)


def _declared_floor() -> tuple[int, ...]:
    floors = set()
    for rel in _FLOOR_FILES:
        text = (_REPO_ROOT / rel).read_text()
        found = re.findall(r"m8tes>=([0-9]+\.[0-9]+(?:\.[0-9]+)?)", text)
        assert found, f"no `m8tes>=` install floor found in {rel}"
        floors.update(found)
    assert len(floors) == 1, f"install floors disagree across the docs: {sorted(floors)}"
    return tuple(int(p) for p in floors.pop().split("."))


#: The lowest m8tes version that can RUN the documented quickstart. Currently 3.2, the
#: release in which `stream_text` gained `raise_on_error`.
#:
#: A plain constant, deliberately. The first attempt asserted only `floor <= current
#: version`, which codex showed was worthless for the bug it was written for: reverting
#: every declared floor to 2.7 passed, because 2.7 <= 3.2. It checked the direction that
#: could not hurt anyone and skipped the one that already had.
#:
#: The second attempt tried to DERIVE this from the changelog — the oldest section
#: mentioning each documented kwarg — and was also wrong, in a way only mutation caught:
#: it returned **1.21.0** for `raise_on_error`, because that parameter has existed on
#: `create`/`create_and_wait` since then and is merely NEW ON `stream_text` in 3.2. A
#: changelog search cannot tell "this token appeared" from "this method gained it", so the
#: derivation silently under-reported the floor and the guard passed on the regression
#: again.
#:
#: So: one visible number that someone bumps when the docs start using a newer API. The
#: cost is a manual step; the benefit is a guard that actually fails. `test_…_kwarg_exists`
#: above covers the related and more likely error (documenting an argument that does not
#: exist at all), which is what this constant cannot see.
_REQUIRED_FLOOR = (3, 2)


@requires_frontend
def test_the_documented_install_floor_supports_the_documented_api():
    """The floor must be high enough to RUN the snippet, not merely not-in-the-future."""
    floor = _declared_floor()
    fl, rq = ".".join(map(str, floor)), ".".join(map(str, _REQUIRED_FLOOR))
    assert floor == _REQUIRED_FLOOR, (
        f"the docs tell people to install m8tes>={fl}, but the quickstart needs >={rq} — "
        f"`stream_text(raise_on_error=…)` does not exist below it. Anyone copying that "
        f"constraint into a requirements file resolves to a version the docs' own code "
        f"will not run on. Files that declare it: {', '.join(_FLOOR_FILES)}. If the docs "
        f"now use something newer, raise _REQUIRED_FLOOR too."
    )


@requires_frontend
def test_the_documented_install_floor_is_not_ahead_of_this_repo():
    """The other direction: never advertise a version that does not exist yet."""
    floor = _declared_floor()
    version = re.search(
        r'^version\s*=\s*"([^"]+)"', (_SDK_ROOT / "pyproject.toml").read_text(), re.M
    )
    assert version, "could not read version from pyproject.toml"
    current = tuple(int(p) for p in version.group(1).split(".")[: len(floor)])
    assert floor <= current, (
        f"the docs tell people to install m8tes>={'.'.join(map(str, floor))}, which is "
        f"newer than this repo's {version.group(1)} — that version does not exist yet."
    )


@requires_frontend
@pytest.mark.parametrize("name", ["quickstart", "console_with_user_id", "console_no_user_id"])
def test_snippet_is_valid_python(name):
    src = _python_snippets()[name]
    try:
        ast.parse(src)
    except SyntaxError as exc:  # pragma: no cover - only on a real regression
        pytest.fail(f"{name} is not valid Python ({exc}):\n{src}")


@requires_frontend
@pytest.mark.parametrize("name", ["quickstart", "console_with_user_id", "console_no_user_id"])
def test_raise_on_error_is_a_real_kwarg_on_the_stream_text_call(name):
    """Structural, so moving the text into a comment or outside the call fails.

    Without `raise_on_error=True`, `stream_text` yields only text deltas and a failed run
    produces zero chunks with no exception — a failure that reads as a successful empty
    answer. This is the first call a developer makes, so it is the worst place for it.
    """
    tree = ast.parse(_python_snippets()[name])
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "stream_text"
    ]
    assert len(calls) == 1, f"{name}: expected exactly one stream_text call, found {len(calls)}"
    kwargs = {kw.arg: kw.value for kw in calls[0].keywords}
    assert "raise_on_error" in kwargs, (
        f"{name}: stream_text is called without raise_on_error. A failed run would print "
        "nothing and exit normally."
    )
    value = kwargs["raise_on_error"]
    assert isinstance(value, ast.Constant) and value.value is True, (
        f"{name}: raise_on_error must be literally True, got {ast.dump(value)}"
    )
