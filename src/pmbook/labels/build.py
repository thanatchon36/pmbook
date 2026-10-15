"""Derived label datasets and their validation (``pmbook labels build|sample|evaluate``).

Outputs (all under ``<data>/derived/``, rebuilt deterministically, never released; D-019):

* ``markets.parquet``: market identity (labels.markets);
* ``category_labels.parquet``: rule-based category per condition (labels.categories);
* ``silver_labels.parquet``: fee-rate group per condition (labels.feerates);
* ``fee_timeline.parquet``: treatment timeline (reference.fee_timeline).

Validation (METHODS §1.4): rule labels are compared with (a) fee-rate silver labels at the
rate-group level and (b) a stratified hand-labelled sample at the category level. The hand
labels live in ``<data>/labels/hand_labels.csv``; who labelled them is recorded in the file
and reported with the metrics (D-042).
"""

from __future__ import annotations

import csv
import random
from collections import Counter
from datetime import UTC, datetime, time
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from pmbook.labels.categories import CATEGORIES, RATE_GROUP, classify
from pmbook.labels.feerates import silver_labels
from pmbook.labels.markets import build_markets
from pmbook.onchain.backfill import FILLS_START
from pmbook.reference import fee_timeline

HAND_FIELDS = ("condition_id", "title", "event_title", "predicted", "label", "annotator", "note")


def derived_dir(root: Path) -> Path:
    d = root / "derived"
    d.mkdir(parents=True, exist_ok=True)
    return d


def label_table(markets: pa.Table) -> pa.Table:
    cols = [markets[c].to_pylist() for c in ("title", "description", "event_title", "text_source")]
    labs = [classify(*x) for x in zip(*cols, strict=True)]
    return pa.table(
        {
            "venue": markets["venue"],
            "condition_id": markets["condition_id"],
            "category": [lab.category for lab in labs],
            "rate_group": [RATE_GROUP[lab.category] for lab in labs],
            "rule": [lab.rule for lab in labs],
            "short_crypto": [lab.short_crypto for lab in labs],
        }
    )


def build(root: Path, with_silver: bool = True) -> dict[str, int]:
    out = derived_dir(root)
    markets = build_markets(root)
    pq.write_table(markets, out / "markets.parquet", compression="zstd")
    pq.write_table(label_table(markets), out / "category_labels.parquet", compression="zstd")
    pq.write_table(fee_timeline.table(), out / "fee_timeline.parquet")
    counts = {"markets": markets.num_rows}
    if with_silver and (root / "dataset=fills_onchain").exists():
        silver = silver_labels(root, markets)
        pq.write_table(silver, out / "silver_labels.parquet", compression="zstd")
        counts["silver"] = silver.num_rows
    return counts


def sample(root: Path, n: int = 300, seed: int = 20261015, floor: int = 15) -> Path:
    """Stratified sample of text-bearing markets created in the backfill window.

    Drawn before the fills crawl completes, so the frame is markets *created* since
    ``FILLS_START`` (nearly all of which trade); ``evaluate`` reports on the traded subset.
    """
    out = derived_dir(root)
    m = pq.read_table(
        out / "markets.parquet", columns=["condition_id", "title", "event_title", "created_ts"]
    )
    since = datetime.combine(FILLS_START, time(), tzinfo=UTC)
    lab = pq.read_table(out / "category_labels.parquet", columns=["condition_id", "category"])
    pred = dict(zip(lab["condition_id"].to_pylist(), lab["category"].to_pylist(), strict=True))
    pool: dict[str, list[dict[str, str]]] = {}
    for cid, title, ev, ts in zip(*(m[c].to_pylist() for c in m.column_names), strict=True):
        if ts is not None and ts >= since and title:
            pool.setdefault(pred[cid], []).append(
                {"condition_id": cid, "title": title, "event_title": ev or ""}
            )
    total = sum(len(v) for v in pool.values())
    alloc = {c: min(len(v), max(floor, round(n * len(v) / total))) for c, v in pool.items()}
    while sum(alloc.values()) > n:  # trim the largest strata back to n
        big = max(alloc, key=lambda c: alloc[c])
        alloc[big] -= 1
    rng = random.Random(seed)
    rows: list[dict[str, str]] = []
    for c in sorted(pool):
        for r in rng.sample(sorted(pool[c], key=lambda x: x["condition_id"]), alloc[c]):
            rows.append(r | {"predicted": c, "label": "", "annotator": "", "note": ""})
    rng.shuffle(rows)
    path = root / "labels" / "hand_sample.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=HAND_FIELDS)
        w.writeheader()
        w.writerows(rows)
    return path


def _confusion(pairs: list[tuple[str, str]], classes: tuple[str, ...]) -> list[str]:
    cm = Counter(pairs)
    head = "| truth \\ predicted | " + " | ".join(classes) + " |"
    lines = [head, "|" + "---|" * (len(classes) + 1)]
    for t in classes:
        lines.append(f"| {t} | " + " | ".join(str(cm[(t, p)]) for p in classes) + " |")
    return lines


def _scores(pairs: list[tuple[str, str]], classes: tuple[str, ...]) -> list[str]:
    n = len(pairs)
    acc = sum(t == p for t, p in pairs) / n if n else float("nan")
    lines = [f"Accuracy: {acc:.3f} (n = {n:,}).", "", "| class | precision | recall | support |"]
    lines.append("|---|---|---|---|")
    for c in classes:
        tp = sum(t == p == c for t, p in pairs)
        pp = sum(p == c for _, p in pairs)
        sup = sum(t == c for t, _ in pairs)
        prec = f"{tp / pp:.3f}" if pp else "-"
        rec = f"{tp / sup:.3f}" if sup else "-"
        lines.append(f"| {c} | {prec} | {rec} | {sup:,} |")
    return lines


def evaluate(root: Path) -> list[str]:
    out = derived_dir(root)
    lab = pq.read_table(out / "category_labels.parquet").to_pylist()
    by_cid = {r["condition_id"]: r for r in lab}
    lines = ["# Category label validation", ""]
    sp = out / "silver_labels.parquet"
    if sp.exists():
        silver = [r for r in pq.read_table(sp).to_pylist() if r["silver_group"]]
        groups = ("r00", "r03", "r04", "r05", "r07")
        pairs = [
            (r["silver_group"], by_cid[r["condition_id"]]["rate_group"])
            for r in silver
            if r["condition_id"] in by_cid
        ]
        lines += ["## Against fee-rate silver labels (rate groups)", ""]
        lines += [*_scores(pairs, groups), "", *_confusion(pairs, groups), ""]
    hp = root / "labels" / "hand_labels.csv"
    if hp.exists():
        with hp.open() as fh:
            hand = [r for r in csv.DictReader(fh) if r["label"]]
        annotators = sorted({r["annotator"] for r in hand})
        pairs = [(r["label"], by_cid[r["condition_id"]]["category"]) for r in hand]
        lines += ["## Against the hand-labelled sample (categories)", ""]
        lines += [f"Annotator(s): {', '.join(annotators)}.", ""]
        lines += [*_scores(pairs, CATEGORIES), "", *_confusion(pairs, CATEGORIES), ""]
    return lines
