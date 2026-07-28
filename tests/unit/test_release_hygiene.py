"""Release-hygiene guards.

Two invariants the 2026-07-21 live DX audit found violated:
1. SDK 2.7.0 shipped to PyPI with no CHANGELOG entry — devs couldn't tell what
   changed. Every version in pyproject.toml must have a matching CHANGELOG
   heading BEFORE it can pass CI (and therefore before publish).
2. CLI help mixed three terms for one entity (mate/teammate/agent). Developer
   surfaces canonically say "agent" (the rename shipped 2026-07-17 with
   permanent teammate aliases); user-visible CLI copy must not reintroduce
   "teammate". Identifiers, API field names, and aliases are untouched.
"""

from pathlib import Path
import re

SDK_ROOT = Path(__file__).resolve().parents[2]


def test_changelog_has_entry_for_current_version():
    """pyproject version bump requires a matching `## [X.Y.Z]` CHANGELOG heading."""
    pyproject = (SDK_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"', pyproject, re.MULTILINE)
    assert match, "version not found in pyproject.toml"
    version = match.group(1)
    changelog = (SDK_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [{version}]" in changelog, (
        f"CHANGELOG.md has no `## [{version}]` entry. Every release needs a changelog "
        f"entry — add one describing what changed (see sdk/py/CLAUDE.md 'After Every "
        f"SDK Change')."
    )


# Calls whose string arguments are shown to a human running the CLI.
_DISPLAY_CALLS = {"print", "prompt", "confirm_prompt"}
# argparse (and friends) keywords whose values render in --help.
_DISPLAY_KWARGS = {"description", "help", "epilog", "metavar"}


def _display_strings(tree):
    """Yield (lineno, text) for every string literal the CLI shows a human.

    AST-based on purpose: the first version of this guard was a line regex over
    `description=|help=|print(`, which silently missed prompt()/confirm_prompt()
    and every continuation line of a multi-line print() — nine "teammate"
    strings sailed past it in the very diff it was written to police. Walking
    Call nodes catches multi-line calls and every display helper by name.
    """
    import ast

    def literals(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.lineno, node.value
        elif isinstance(node, ast.JoinedStr):  # f-string: check its literal parts
            for part in node.values:
                if isinstance(part, ast.Constant) and isinstance(part.value, str):
                    yield node.lineno, part.value

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = getattr(func, "id", None) or getattr(func, "attr", None)
        if name in _DISPLAY_CALLS:
            for arg in node.args:
                yield from literals(arg)
        for kw in node.keywords:
            if kw.arg in _DISPLAY_KWARGS:
                yield from literals(kw.value)


def test_cli_help_copy_says_agents_not_teammates():
    """User-visible CLI copy says "agent", never "teammate". Internal identifiers
    (teammate_id, class names, API fields, aliases) are exempt — this scans
    display strings only. Also catches "a agent", the grammar error a naive
    teammate→agent sweep introduces."""
    import ast

    offenders = []
    for path in (SDK_ROOT / "m8tes" / "cli").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for lineno, text in _display_strings(tree):
            if re.search(r"teammate|\ba agent\b", text, re.IGNORECASE):
                offenders.append(f"{path.relative_to(SDK_ROOT)}:{lineno}: {text[:70]!r}")
    assert not offenders, (
        "CLI display strings must say 'agent' (and 'an agent'), not 'teammate':\n"
        + "\n".join(offenders)
    )


# Identifiers that must never appear anywhere in this tree: four real ad-account
# customer IDs that shipped in test fixtures until 2026-07-27 (found in a
# pre-publication sweep; sync-sdk.yml scrubs them from the public repo's history —
# this guard keeps them out of its future), plus the personal identity the sync's
# fail-closed check aborts on (catching it here fails CI fast instead of breaking
# the publish). Built from fragments so this file never contains them itself:
# this entire directory publishes to the public m8tes-ai/m8tes repo on every push.
_BANNED_LITERALS = tuple(
    "".join(parts)
    for parts in (
        ("974-", "100-", "3352"),
        ("9741", "0033", "52"),
        ("6179", "7307", "54"),
        ("5284", "1514", "31"),
        ("6197", "4682", "92"),
        ("el", "mar"),
    )
)


def _tracked_files():
    """Exactly the set of files sync-sdk.yml publishes: git-tracked, this dir."""
    import subprocess

    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=SDK_ROOT,
        capture_output=True,
        check=True,
    ).stdout
    return [SDK_ROOT / name.decode() for name in out.split(b"\0") if name]


def test_no_leaked_identifiers_anywhere_in_tree():
    """No banned identifier may exist in any tracked file (content, either common
    encoding, or the path itself) — the tracked tree is public via sync-sdk.yml."""
    banned_bytes = [b.encode() for b in _BANNED_LITERALS]
    banned_utf16 = [b.encode(enc) for b in _BANNED_LITERALS for enc in ("utf-16-le", "utf-16-be")]
    offenders = []
    for path in _tracked_files():
        rel = str(path.relative_to(SDK_ROOT))
        if any(b in rel.lower() for b in _BANNED_LITERALS):
            offenders.append(f"{rel}: path contains a banned identifier")
        # A tracked file the guard cannot read is a guard hole, not a skip.
        raw = path.read_bytes().lower()
        if any(b in raw for b in banned_bytes) or any(b in raw for b in banned_utf16):
            offenders.append(f"{rel}: contains a banned identifier")
    assert not offenders, (
        "Banned identifiers found in sdk/py (this tree is PUBLIC via sync-sdk.yml):\n"
        + "\n".join(offenders)
    )
