"""Append-only Parquet partitions with per-day crawl manifests (MISSION §3.3).

Layout: ``<root>/dataset=<name>/date=YYYY-MM-DD/part-<first>-<last>.parquet`` (zstd).
Files are written to ``*.tmp`` and renamed, so a crash never leaves a half-written part.
A crawl's day manifest (``onchain.backfill``) records the last block whose logs are on disk.
Parts are written before the manifest advances, so on resume any part starting after
``done_through`` is an orphan of an interrupted flush and :meth:`PartitionStore.recover`
removes it.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from pmbook.schema import VENUE, schema_for

INT64_MAX = 2**63 - 1


@dataclass
class DayState:
    first_block: int
    last_block: int
    done_through: int  # first_block - 1 when nothing is done
    complete: bool = False


class PartitionStore:
    def __init__(self, root: Path, dataset: str) -> None:
        self.root = Path(root)
        self.dataset = dataset
        self.schema = schema_for(dataset)

    def day_dir(self, day: date) -> Path:
        return self.root / f"dataset={self.dataset}" / f"date={day.isoformat()}"

    def recover(self, day: date, done_through: int) -> list[Path]:
        """Delete ``*.tmp`` files and parts beyond ``done_through``; return what was removed."""
        removed: list[Path] = []
        d = self.day_dir(day)
        if not d.exists():
            return removed
        for p in sorted(d.iterdir()):
            orphan = p.suffix == ".tmp"
            if p.name.startswith("part-") and p.suffix == ".parquet":
                orphan = int(p.stem.split("-")[1]) > done_through
            if orphan:
                p.unlink()
                removed.append(p)
        return removed

    def write_part(
        self, day: date, first: int, last: int, rows: Iterable[Mapping[str, Any]]
    ) -> Path:
        return self.write_named(day, f"part-{first}-{last}", rows)

    def write_named(self, day: date, stem: str, rows: Iterable[Mapping[str, Any]]) -> Path:
        table = rows_to_table(rows, self.schema)
        d = self.day_dir(day)
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{stem}.parquet"
        tmp = path.with_suffix(".parquet.tmp")
        pq.write_table(table, tmp, compression="zstd")
        with open(tmp, "rb") as fh:
            os.fsync(fh.fileno())
        os.replace(tmp, path)
        return path

    def parts(self, day: date) -> list[Path]:
        d = self.day_dir(day)
        return sorted(d.glob("part-*.parquet")) if d.exists() else []


def rows_to_table(rows: Iterable[Mapping[str, Any]], schema: pa.Schema) -> pa.Table:
    """Build a table in schema column order. Integer amounts above int64 become null."""
    cols: dict[str, list[Any]] = {f.name: [] for f in schema}
    int_cols = {f.name for f in schema if pa.types.is_integer(f.type) and f.nullable}
    for row in rows:
        for name, values in cols.items():
            if name == "venue":
                values.append(row.get("venue", VENUE))
                continue
            v = row.get(name)
            if name in int_cols and v is not None and v > INT64_MAX:
                v = None
            values.append(v)
    return pa.Table.from_pydict(cols, schema=schema)
