"""`m8tes --help` is the CLI's front door, so its shape is pinned here.

The help text was the first thing a developer saw and it opened with argparse's raw
choice dump — 15 tokens for 6 commands, aliases inline with the names they alias:

    {auth,a,apps,app,google,g,agent,mate,teammate,m,agents,task,tasks,run,r}

then repeated them per row as `agent (mate, teammate, m, agents)`. Nothing in that tells
a reader which token is the real command, and the four names for "agent" are the same
canonical-vs-legacy confusion the SDK client had (see tests/unit/test_agents_alias.py).

The aliases themselves are fine — they are muscle memory for existing users and cost
nothing to keep. They just must not be advertised. So: primary names in the help,
every alias still resolving.
"""

from __future__ import annotations

import pytest

from m8tes.cli.main import build_parser


@pytest.fixture
def parser():
    return build_parser()


@pytest.fixture
def help_text(parser):
    return parser.format_help()


def test_help_lists_the_primary_commands(help_text):
    for name in ("auth", "apps", "agent", "task", "run"):
        assert name in help_text, f"{name} missing from `m8tes --help`"


def test_help_does_not_dump_aliases_beside_the_names_they_alias(help_text):
    # The exact regression: argparse rendering `agent (mate, teammate, m, agents)`.
    # Checked as a substring of the rendered help rather than by inspecting argparse
    # internals, because what shipped wrong was the rendered text.
    assert "(mate, teammate, m, agents)" not in help_text
    assert "(tasks)" not in help_text
    assert "{auth,a,apps" not in help_text


def test_help_is_not_wider_than_the_commands_it_describes(help_text):
    # A cheap proxy for "the choice dump is gone": that one line was ~70 chars of
    # comma-separated tokens. Any line that long in the command list means it came back.
    offenders = [
        line
        for line in help_text.splitlines()
        if line.count(",") >= 4 and "{" in line and "}" in line
    ]
    assert offenders == [], f"argparse choice dump is back: {offenders}"


@pytest.mark.parametrize(
    ("alias", "primary"),
    [
        ("m", "agent"),
        ("mate", "agent"),
        ("teammate", "agent"),
        ("agents", "agent"),
        ("tasks", "task"),
        ("a", "auth"),
        ("app", "apps"),
        ("r", "run"),
        ("g", "google"),
    ],
)
def test_every_alias_still_resolves(parser, alias, primary):
    """Hiding an alias must not retire it.

    Asserted through the parser rather than the registry: the registry always knew these
    names, and the thing that could break when they stop being passed to `add_parser` is
    argparse's own name→parser map. Parsing `m8tes <alias>` is what a user actually does.
    """
    args = parser.parse_args([alias])
    assert args.command == alias
    # And the same parser object backs both names, so the alias cannot drift into
    # accepting a different set of flags than the command it points at. Read through the
    # public `choices` mapping, which is the same dict the subparsers action registers
    # names in.
    subparsers = parser._subparsers._group_actions[0]  # type: ignore[union-attr]
    assert subparsers.choices[alias] is subparsers.choices[primary]


def test_discovery_does_not_skip_because_something_else_registered_first():
    """Idempotency must key on the PACKAGE scanned, not on "the registry is non-empty".

    The first version returned early whenever any command existed. Registering one command
    of your own before building the parser then made discovery a silent no-op and every
    built-in vanished — measured: the registry came back as exactly `["custom"]`, with no
    error raised anywhere. Silent and total, which is the worst combination.
    """
    from m8tes.cli.base import CommandGroup
    from m8tes.cli.registry import CommandRegistry

    class Custom(CommandGroup):
        name = "custom"
        description = "a host-registered command"

        def add_arguments(self, parser):  # pragma: no cover - never parsed here
            pass

        def execute(self, args, client):  # pragma: no cover - never executed here
            return 0

    r = CommandRegistry()
    r.register_command(Custom())
    r.auto_discover_commands()

    assert "custom" in r.get_all_commands()
    for builtin in ("auth", "apps", "agent", "task", "run"):
        assert builtin in r.get_all_commands(), f"discovery skipped the built-ins ({builtin})"


def test_discovery_is_still_idempotent_for_the_same_package():
    """The reason the early-return exists at all: a second call must not raise."""
    from m8tes.cli.registry import CommandRegistry

    r = CommandRegistry()
    r.auto_discover_commands()
    before = sorted(r.get_all_commands())
    r.auto_discover_commands()  # must not raise "already registered"
    assert sorted(r.get_all_commands()) == before


def test_clear_lets_discovery_run_again():
    """`clear()` must reset the discovered-packages set too.

    Otherwise it leaves a registry that is empty of commands but believes everything has
    been scanned, so nothing can ever repopulate it.
    """
    from m8tes.cli.registry import CommandRegistry

    r = CommandRegistry()
    r.auto_discover_commands()
    r.clear()
    r.auto_discover_commands()
    assert "auth" in r.get_all_commands()


def test_unknown_command_still_suggests_a_close_match(parser, capsys):
    # `choices` for a subparsers action IS the name→parser map, so wiring aliases in by
    # hand has to keep the suggester working. A CLI that hides aliases AND stops
    # suggesting corrections is worse than the noisy one it replaced.
    with pytest.raises(SystemExit):
        parser.parse_args(["agnt"])
    err = capsys.readouterr().err
    assert "agent" in err, f"no suggestion for a near-miss command: {err!r}"


# --- Subgroup help (m8tes agent --help, m8tes run --help) -----------------------
# Same rule one level down (live DX audit 2026-08-16): the top-level help got the
# metavar treatment, but subgroups still opened with the raw choice dump
# ({create,c,list,ls,...}) and advertised aliases per row. And the newest surface
# still shipped the pre-rename vocabulary: `run list-mate`, a `mate_id` positional.


def _subgroup_help(parser, name: str) -> str:
    import argparse

    action = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    return action.choices[name].format_help()


def test_subgroup_help_has_no_choice_dump(parser):
    for group in ("agent", "run", "task", "auth", "apps"):
        text = _subgroup_help(parser, group)
        assert "{create,c," not in text, f"raw choice dump in `m8tes {group} --help`"
        assert "{list," not in text, f"raw choice dump in `m8tes {group} --help`"


def test_run_group_speaks_agent_not_mate(parser):
    text = _subgroup_help(parser, "run")
    assert "list-agent" in text
    assert "list-mate" not in text  # alias stays functional, is not advertised
    assert "mate_id" not in text


def test_agent_group_positionals_say_agent_id(parser):
    import argparse

    action = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    agent = action.choices["agent"]
    sub = next(a for a in agent._actions if isinstance(a, argparse._SubParsersAction))
    get_help = sub.choices["get"].format_help()
    assert "agent_id" in get_help
    assert "mate_id" not in get_help
    task_help = sub.choices["task"].format_help()
    assert "mate_id" not in task_help


def test_legacy_subcommand_aliases_still_resolve(parser):
    import argparse

    action = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    run_sub = next(
        a for a in action.choices["run"]._actions if isinstance(a, argparse._SubParsersAction)
    )
    for legacy in ("list-mate", "lm"):
        assert legacy in run_sub.choices, f"`m8tes run {legacy}` must keep working"
    assert "list-agent" in run_sub.choices
