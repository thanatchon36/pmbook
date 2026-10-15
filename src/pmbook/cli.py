"""Command-line entry point: ``pmbook record | backfill | validate | panel | analyze | paper``."""

import typer

from pmbook import __version__

app = typer.Typer(
    help="Read-only Polymarket order-book research toolkit. Research only: never places orders.",
    no_args_is_help=True,
    add_completion=False,
)


def _not_yet(phase: int) -> None:
    typer.echo(f"Not implemented yet (planned for Phase {phase}; see MISSION.md §8).", err=True)
    raise typer.Exit(code=2)


def _version(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version, is_eager=True, help="Show version and exit."
    ),
) -> None:
    """pmbook command group."""


@app.command()
def record() -> None:
    """Run the long-lived recorder (Gamma metadata, CLOB books, WS deltas)."""
    _not_yet(1)


@app.command()
def backfill() -> None:
    """Backfill on-chain fills, price history and reference data."""
    _not_yet(2)


@app.command()
def validate() -> None:
    """Integrity and coverage reports for recorded partitions."""
    _not_yet(1)


@app.command()
def panel() -> None:
    """Build the market-day / market-hour panel."""
    _not_yet(3)


@app.command()
def analyze() -> None:
    """Run the pre-registered analysis (event studies, DiD, robustness)."""
    _not_yet(3)


@app.command()
def paper() -> None:
    """Build the paper from analysis outputs."""
    _not_yet(4)
