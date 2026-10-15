import pytest
from typer.testing import CliRunner

from pmbook import __version__
from pmbook.cli import app

runner = CliRunner()

COMMANDS = ["labels", "panel", "analyze", "paper"]


def test_help_lists_all_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in [*COMMANDS, "backfill", "validate", "record"]:
        assert cmd in result.output


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_stub_commands_exit_nonzero() -> None:
    for cmd in COMMANDS:
        result = runner.invoke(app, [cmd])
        assert result.exit_code == 2, cmd


def test_record_refuses_without_tier2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PMBOOK_TIER2", raising=False)
    result = runner.invoke(app, ["record"])
    assert result.exit_code == 3
    assert "Checkpoint R" in result.output
