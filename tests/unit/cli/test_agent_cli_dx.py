"""
CLI DX: primary command is ``agent`` (mate remains an alias) and invalid
choices get a "Did you mean?" suggestion.
"""

from __future__ import annotations

from argparse import Namespace
from io import StringIO
from unittest.mock import patch

import pytest

from m8tes.cli.commands.mate import MateCommandGroup
from m8tes.cli.registry import CommandRegistry
from m8tes.cli.util import (
    SuggestingArgumentParser,
    enhance_argparse_error,
    suggest_commands,
)


class TestAgentCommandNaming:
    def test_primary_name_is_agent(self) -> None:
        group = MateCommandGroup()
        assert group.name == "agent"
        assert "mate" in group.aliases
        assert "teammate" in group.aliases
        assert "m" in group.aliases
        assert "agents" in group.aliases

    def test_registry_resolves_agent_and_mate(self) -> None:
        registry = CommandRegistry()
        registry.auto_discover_commands()
        agent = registry.get_command("agent")
        mate = registry.get_command("mate")
        assert agent is mate
        assert agent.name == "agent"
        # Primary list surfaces agent, not mate
        primaries = {c.name for c in registry.get_primary_commands()}
        assert "agent" in primaries
        assert "mate" not in primaries


class TestSuggestCommands:
    def test_show_suggests_get(self) -> None:
        choices = ["create", "c", "list", "ls", "get", "g", "task", "t"]
        matches = suggest_commands("show", choices)
        assert "get" in matches

    def test_enhance_argparse_invalid_choice(self) -> None:
        msg = (
            "argument agent_command: invalid choice: 'show' (choose from 'create', 'c', 'get', 'g')"
        )
        enhanced = enhance_argparse_error(msg)
        assert "Did you mean" in enhanced
        assert "get" in enhanced

    def test_enhance_leaves_other_errors(self) -> None:
        msg = "the following arguments are required: command_args"
        assert enhance_argparse_error(msg) == msg


class TestSuggestingParser:
    def test_invalid_choice_exits_with_suggestion(self) -> None:
        parser = SuggestingArgumentParser(prog="m8tes")
        sub = parser.add_subparsers(dest="cmd")
        sub.add_parser("get", aliases=["g"])
        sub.add_parser("list", aliases=["ls"])

        with (
            patch("sys.stderr", new_callable=StringIO) as err,
            pytest.raises(SystemExit) as exc,
        ):
            parser.parse_args(["show"])
        assert exc.value.code == 2
        out = err.getvalue()
        assert "invalid choice" in out
        assert "Did you mean" in out
        assert "get" in out


class TestAgentGroupMissingSubcommand:
    def test_missing_subcommand_prints_example(self) -> None:
        group = MateCommandGroup()
        args = Namespace(agent_command=None)
        with patch("builtins.print") as mock_print:
            code = group.execute(args, client=None)
        assert code == 1
        printed = " ".join(str(c.args[0]) for c in mock_print.call_args_list if c.args)
        assert "No subcommand" in printed
        assert 'm8tes agent task "say hello"' in printed


class TestMainHelpSurfacesAgent:
    def test_help_lists_agent(self) -> None:
        registry = CommandRegistry()
        registry.auto_discover_commands()
        parser = SuggestingArgumentParser(prog="m8tes")
        subparsers = parser.add_subparsers(dest="command")
        for command in registry.get_primary_commands():
            subparsers.add_parser(command.name, aliases=command.aliases, help=command.description)
        text = parser.format_help()
        assert "agent" in text
        # Alias still discoverable in help
        assert "mate" in text
