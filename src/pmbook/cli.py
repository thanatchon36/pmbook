"""CLI entry point: ``pmbook backfill | labels | validate | panel | analyze | paper | record``."""

import typer

from pmbook import __version__
from pmbook.config import Settings

app = typer.Typer(
    help="Prediction-market microstructure research toolkit. Research only: reads public data, "
    "never places orders.",
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
def backfill() -> None:
    """Backfill on-chain fills, conditions and questions (Tier 1) and reference data."""
    _not_yet(1)


@app.command()
def labels() -> None:
    """Classify questions into fee categories and report validation accuracy."""
    _not_yet(2)


@app.command()
def validate() -> None:
    """Integrity and coverage reports for stored partitions."""
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


@app.command()
def record() -> None:
    """Tier 2 L2 recorder (venue-hosted endpoints; requires PMBOOK_TIER2=1 after Checkpoint R)."""
    if not Settings().tier2:
        typer.echo(
            "record is Tier 2: set PMBOOK_TIER2=1 only after Checkpoint R (MISSION §9).", err=True
        )
        raise typer.Exit(code=3)
    _not_yet(5)
