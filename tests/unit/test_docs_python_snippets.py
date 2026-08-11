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
