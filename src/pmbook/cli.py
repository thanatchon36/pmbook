"""CLI entry point: ``pmbook backfill | labels | validate | panel | analyze | paper | record``."""

import signal
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

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


backfill_app = typer.Typer(
    help="Backfill Tier 1 on-chain data (identity first, then fills).", no_args_is_help=True
)
app.add_typer(backfill_app, name="backfill")

_START = typer.Option(None, help="First UTC day (YYYY-MM-DD). Default: the crawl's start.")
_END = typer.Option(None, help="Last UTC day (YYYY-MM-DD). Default: yesterday (UTC).")
_RPC = typer.Option(None, "--rpc", help="RPC endpoint(s) to use, in failover order.")
_OUT = typer.Option(None, help="Write the Markdown report here.")
_AUDIT = typer.Option(0, help="Re-check N random transactions per complete day against receipts.")


def _run_crawl(kind: str, start: str | None, end: str | None, rpc_urls: list[str] | None) -> None:
    from pmbook.logging import configure
    from pmbook.onchain import backfill as bf
    from pmbook.onchain.pseudonym import Pseudonymizer, load_or_create_salt
    from pmbook.onchain.rpc import RpcClient

    configure()
    settings = Settings()
    root = settings.data_dir
    stop = {"flag": False}

    def _stop(signum: int, frame: object) -> None:
        stop["flag"] = True

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    exclusions = bf.Exclusions.load(root / "filters" / "excluded.json")
    default_start = bf.IDENTITY_START if kind == "identity" else bf.FILLS_START
    first = date.fromisoformat(start) if start else default_start
    last = date.fromisoformat(end) if end else datetime.now(UTC).date() - timedelta(days=1)
    with RpcClient(rpc_urls or None, settings) as rpc:
        if kind == "identity":
            proc: bf.Processor = bf.IdentityProcessor(exclusions)
            require = None
        else:
            pseudo = Pseudonymizer(load_or_create_salt(settings.salt_path))
            proc = bf.FillsProcessor(exclusions, pseudo.id)
            require = bf.ManifestStore(root, "identity").complete
        crawler = bf.Crawler(rpc, root, proc, should_stop=lambda: stop["flag"])
        crawler.crawl(first, last, require=require)
    s = crawler.stats
    typer.echo(f"{kind}: {s.requests} requests, {s.logs} logs, {s.rows} rows written")


@backfill_app.command("identity")
def backfill_identity(
    start: str | None = _START, end: str | None = _END, rpc: list[str] | None = _RPC
) -> None:
    """Tokens, conditions and question text (with the home-jurisdiction filter)."""
    _run_crawl("identity", start, end, rpc)


@backfill_app.command("fills")
def backfill_fills(
    start: str | None = _START, end: str | None = _END, rpc: list[str] | None = _RPC
) -> None:
    """OrderFilled legs of the venue exchanges, pseudonymised at decode time."""
    _run_crawl("fills", start, end, rpc)


@backfill_app.command("binance")
def backfill_binance(start: str | None = _START, end: str | None = _END) -> None:
    """Binance public 1-minute klines (RQ4 reference), from 2025-10-01 by default."""
    from pmbook.http import PublicClient
    from pmbook.logging import configure
    from pmbook.onchain.backfill import FILLS_START
    from pmbook.reference import binance

    configure()
    settings = Settings()
    first = date.fromisoformat(start) if start else FILLS_START
    last = date.fromisoformat(end) if end else datetime.now(UTC).date() - timedelta(days=1)
    with PublicClient(settings) as client:
        written = binance.backfill(client, settings.data_dir, first, last)
    typer.echo("binance: " + ", ".join(f"{s} {n:,} rows" for s, n in written.items()))


labels_app = typer.Typer(
    help="Classify questions into fee categories and report validation accuracy.",
    no_args_is_help=True,
)
app.add_typer(labels_app, name="labels")


@labels_app.command("build")
def labels_build(
    silver: bool = typer.Option(True, help="Also derive fee-rate silver labels from fills."),
) -> None:
    """Market identity, rule-based categories, silver labels and the fee timeline."""
    from pmbook.labels import build

    counts = build.build(Settings().data_dir, with_silver=silver)
    typer.echo("labels: " + ", ".join(f"{k} {v:,}" for k, v in counts.items()))


@labels_app.command("sample")
def labels_sample(n: int = typer.Option(300, help="Markets to sample.")) -> None:
    """Stratified sample of traded markets for hand labelling."""
    from pmbook.labels import build

    typer.echo(f"sample: {build.sample(Settings().data_dir, n)}")


@labels_app.command("evaluate")
def labels_evaluate(out: Path | None = _OUT) -> None:
    """Accuracy and confusion matrices against silver and hand labels."""
    from pmbook.labels import build

    text = "\n".join(build.evaluate(Settings().data_dir))
    if out is not None:
        out.write_text(text)
    typer.echo(text)


@app.command()
def validate(
    out: Path | None = _OUT, audit_per_day: int = _AUDIT, rpc: list[str] | None = _RPC
) -> None:
    """Coverage and integrity report for the stored on-chain partitions."""
    from pmbook.validate import coverage_report

    settings = Settings()
    root = settings.data_dir
    report = coverage_report(root)
    text, errors = report.markdown, list(report.errors)
    if audit_per_day > 0:
        from pmbook.onchain.audit import audit
        from pmbook.onchain.backfill import Exclusions, ManifestStore
        from pmbook.onchain.pseudonym import Pseudonymizer, load_or_create_salt
        from pmbook.onchain.rpc import RpcClient

        manifests = ManifestStore(root, "fills")
        days = sorted(
            date.fromisoformat(m.stem)
            for m in manifests.dir.glob("*.json")
            if manifests.complete(date.fromisoformat(m.stem))
        )
        pseudo = Pseudonymizer(load_or_create_salt(settings.salt_path))
        excluded = Exclusions.load(root / "filters" / "excluded.json").token_ids
        with RpcClient(rpc or None, settings) as client:
            res = audit(client, root, days, pseudo.id, excluded, audit_per_day)
        text += (
            f"\n## Decoding audit\n\nSampled {res.sampled} transactions over {len(days)} days: "
            f"{res.passed} passed, {len(res.failures)} problems, "
            f"{res.skipped_excluded} skipped (excluded tokens).\n"
        )
        text += "".join(f"- {f}\n" for f in res.failures)
        errors += res.failures
        typer.echo(f"audit: {res.passed}/{res.sampled} transactions passed")
    target = out or root / "reports" / "coverage.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)
    typer.echo(report.summary)
    typer.echo(f"report: {target}")
    if errors:
        raise typer.Exit(code=1)


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
