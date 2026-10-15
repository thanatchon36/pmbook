from typer.testing import CliRunner

from pmbook import __version__
from pmbook.cli import app

runner = CliRunner()

COMMANDS = ["record", "backfill", "validate", "panel", "analyze", "paper"]


def test_help_lists_all_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in COMMANDS:
        assert cmd in result.output


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_stub_commands_exit_nonzero() -> None:
    for cmd in COMMANDS:
        result = runner.invoke(app, [cmd])
        assert result.exit_code == 2, cmd
