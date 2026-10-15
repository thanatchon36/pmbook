"""Coverage and integrity reports for on-chain partitions (``pmbook validate``).

Coverage comes from the crawl manifests (blocks covered per UTC day). Integrity checks read
the fill partitions: unique (tx_hash, log_index), at least one taker leg per transaction,
exchange generation consistent with the 2026-04-28 migration, prices in (0, 1], fees >= 0.
The report holds counts only: no ids, addresses or question text.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

CRAWLS = {
    "identity": ("questions_onchain", "conditions_onchain", "tokens_onchain"),
    "fills": ("fills_onchain",),
}
V2_FROM = date(2026, 4, 28)  # exchange migration day: both generations may appear


@dataclass
class Report:
    markdown: str
    summary: str
    errors: list[str] = field(default_factory=list)


def _rows(root: Path, dataset: str, day: str) -> int:
    d = root / f"dataset={dataset}" / f"date={day}"
    return sum(pq.ParquetFile(p).metadata.num_rows for p in d.glob("part-*.parquet"))


def check_fills_day(day_dir: Path, day: date) -> list[str]:
    """Integrity problems in one day of ``fills_onchain`` (empty list if none)."""
    parts = sorted(day_dir.glob("part-*.parquet"))
    if not parts:
        return []
    cols = ["tx_hash", "log_index", "is_taker_leg", "exchange_version", "price", "fee"]
    t = pa.concat_tables(pq.read_table(p, columns=cols) for p in parts)
    problems: list[str] = []
    keys = t.group_by(["tx_hash", "log_index"]).aggregate([([], "count_all")])
    if keys.num_rows != t.num_rows:
        problems.append(f"{day}: {t.num_rows - keys.num_rows} duplicate (tx, log_index)")
    per_tx = t.group_by("tx_hash").aggregate([("is_taker_leg", "max")])
    missing = per_tx.num_rows - pc.sum(per_tx["is_taker_leg_max"].cast(pa.int64())).as_py()
    if missing:
        problems.append(f"{day}: {missing} transactions without a taker leg")
    versions = set(pc.unique(t["exchange_version"]).to_pylist())
    if day < V2_FROM and 2 in versions:
        problems.append(f"{day}: V2 fills before the migration")
    if day > V2_FROM and 1 in versions:
        problems.append(f"{day}: V1 fills after the migration")
    price = t["price"]
    bad_price = pc.sum(pc.or_(pc.less_equal(price, 0), pc.greater(price, 1))).as_py() or 0
    if bad_price:
        problems.append(f"{day}: {bad_price} prices outside (0, 1]")
    if (pc.sum(pc.less(t["fee"], 0)).as_py() or 0) > 0:
        problems.append(f"{day}: negative fees")
    return problems


def coverage_report(root: Path, check_integrity: bool = True) -> Report:
    root = Path(root)
    lines = ["# Coverage report", ""]
    summary: list[str] = []
    errors: list[str] = []
    for crawl, datasets in CRAWLS.items():
        state_dir = root / "_state" / crawl
        manifests = sorted(state_dir.glob("*.json")) if state_dir.exists() else []
        lines += [f"## {crawl}", ""]
        if not manifests:
            lines += ["_no data_", ""]
            summary.append(f"{crawl}: no data")
            continue
        header = "| date | blocks | covered | complete | " + " | ".join(datasets) + " |"
        lines += [header, "|" + "---|" * (4 + len(datasets))]
        n_complete = blocks = covered = 0
        totals = dict.fromkeys(datasets, 0)
        days = [m.stem for m in manifests]
        for m in manifests:
            st = json.loads(m.read_text())
            n_blocks = st["last_block"] - st["first_block"] + 1
            n_cov = max(0, st["done_through"] - st["first_block"] + 1)
            blocks += n_blocks
            covered += n_cov
            n_complete += bool(st["complete"])
            counts = {ds: _rows(root, ds, m.stem) for ds in datasets}
            for ds, n in counts.items():
                totals[ds] += n
            lines.append(
                f"| {m.stem} | {n_blocks} | {n_cov} | {'yes' if st['complete'] else 'no'} | "
                + " | ".join(str(counts[ds]) for ds in datasets)
                + " |"
            )
            if crawl == "fills" and check_integrity:
                errors += check_fills_day(
                    root / "dataset=fills_onchain" / f"date={m.stem}", date.fromisoformat(m.stem)
                )
        gaps = _missing_days(days)
        lines += [
            "",
            f"Days: {len(manifests)} ({n_complete} complete), {days[0]} → {days[-1]}; "
            f"missing days inside the range: {len(gaps)}.",
            f"Blocks covered: {covered:,} / {blocks:,} ({covered / blocks:.4%}).",
            "Rows: " + ", ".join(f"{ds} {n:,}" for ds, n in totals.items()) + ".",
            "",
        ]
        if gaps:
            lines += ["Missing days: " + ", ".join(gaps[:50]), ""]
        summary.append(
            f"{crawl}: {n_complete}/{len(manifests)} days complete, "
            f"{covered / blocks:.4%} of blocks, "
            + ", ".join(f"{n:,} {ds}" for ds, n in totals.items())
        )
    lines += identity_join_lines(root)
    lines += ["## Integrity", ""]
    lines += [f"- {e}" for e in errors] if errors else ["No integrity problems found.", ""]
    return Report("\n".join(lines) + "\n", "\n".join(summary), errors)


def _missing_days(days: list[str]) -> list[str]:
    if not days:
        return []
    have = set(days)
    d0, d1 = date.fromisoformat(days[0]), date.fromisoformat(days[-1])
    out = []
    d = d0
    while d <= d1:
        if d.isoformat() not in have:
            out.append(d.isoformat())
        d = date.fromordinal(d.toordinal() + 1)
    return out


def identity_join(root: Path) -> dict[str, int]:
    """How many registered tokens' conditions resolve to a preparation and to question text."""
    paths = {
        ds: (root / f"dataset={ds}").as_posix() + "/*/*.parquet"
        for ds in ("tokens_onchain", "conditions_onchain", "questions_onchain")
    }
    if not all((root / f"dataset={ds}").exists() for ds in paths):
        return {}
    con = duckdb.connect()
    row = con.sql(
        f"""
        with t as (select distinct condition_id from read_parquet('{paths["tokens_onchain"]}')),
        c as (select condition_id, any_value(question_id) as question_id
              from read_parquet('{paths["conditions_onchain"]}')
              where event = 'preparation' group by 1),
        q as (select distinct question_id from read_parquet('{paths["questions_onchain"]}')
              where text is not null)
        select count(*), count(c.condition_id), count(q.question_id)
        from t left join c using (condition_id) left join q on q.question_id = c.question_id
        """
    ).fetchone()
    assert row is not None
    return {"conditions": row[0], "with_preparation": row[1], "with_text": row[2]}


def identity_join_lines(root: Path) -> list[str]:
    j = identity_join(root)
    if not j:
        return []
    n = max(j["conditions"], 1)
    return [
        "## Identity join",
        "",
        f"Registered conditions: {j['conditions']:,}; with on-chain preparation: "
        f"{j['with_preparation']:,} ({j['with_preparation'] / n:.2%}); with question text: "
        f"{j['with_text']:,} ({j['with_text'] / n:.2%}).",
        "",
    ]
