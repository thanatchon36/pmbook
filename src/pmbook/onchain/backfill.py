"""Resumable, adaptive ``eth_getLogs`` crawler over UTC days (docs/plans/phase-1.md).

Two crawls share the machinery:

* ``identity``: tokens, conditions and question text, from the exchange deployment onward,
  strictly in time order. The home-jurisdiction filter runs here, at ingestion: excluded
  questions are never stored, and their conditions and tokens are dropped and remembered in
  the local exclusion registry.
* ``fills``: ``OrderFilled`` legs of the venue exchanges. Day D runs only once identity is
  complete through D, and legs on excluded tokens are dropped at decode time.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import structlog

from pmbook.filters import home_jurisdiction
from pmbook.onchain import contracts as c
from pmbook.onchain import decode
from pmbook.onchain.rpc import ResultCapExceeded, RpcClient, RpcError
from pmbook.store import DayState, PartitionStore

log = structlog.get_logger(__name__)

IDENTITY_START = date(2022, 9, 26)  # CTF Exchange V1 deployed at block 33,605,403
FILLS_START = date(2025, 10, 1)  # MISSION §3.3 backfill window
FINALITY_BLOCKS = 300
TARGET_LOGS = 10_000
MAX_CHUNK = 10_000
FLUSH_ROWS = 750_000

Row = dict[str, Any]


def day_start_ts(day: date) -> int:
    return int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp())


def days(start: date, end: date) -> Iterator[date]:
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


class BlockIndex:
    """First block at or after a timestamp, by interpolation search; cached on disk."""

    def __init__(self, rpc: RpcClient, cache: Path) -> None:
        self.rpc = rpc
        self.cache = cache
        self._map: dict[str, int] = json.loads(cache.read_text()) if cache.exists() else {}
        self._ts: dict[int, int] = {}

    def _block_ts(self, n: int) -> int:
        if n not in self._ts:
            self._ts[n] = self.rpc.block_timestamp(n)
        return self._ts[n]

    def first_block_at(self, ts: int, head: int, after: int | None = None) -> int:
        """First block with timestamp >= ``ts``; ``after`` is a known earlier block (a hint)."""
        lo, hi = 1, head
        if self._block_ts(hi) < ts:
            return hi + 1
        if after is not None and self._block_ts(after) < ts:
            lo = after
            # Polygon blocks take >= ~2 s, so a day spans < 50k blocks after a known boundary.
            near = min(head, after + 50_000)
            if self._block_ts(near) >= ts:
                hi = near
        while hi - lo > 16:  # interpolate, then finish with bisection
            t_lo, t_hi = self._block_ts(lo), self._block_ts(hi)
            if t_hi <= t_lo:
                break
            guess = lo + int((ts - t_lo) * (hi - lo) / (t_hi - t_lo))
            guess = min(max(guess, lo + 1), hi - 1)
            # Probe a small bracket around the guess to shrink both ends quickly.
            a, b = max(lo + 1, guess - 4), min(hi - 1, guess + 4)
            if self._block_ts(a) >= ts:
                hi = a
            elif self._block_ts(b) < ts:
                lo = b
            else:
                lo, hi = a, b
        while lo < hi:
            mid = (lo + hi) // 2
            if self._block_ts(mid) < ts:
                lo = mid + 1
            else:
                hi = mid
        return lo

    def _first(self, day: date, head: int) -> int:
        key = day.isoformat()
        if key not in self._map:
            prev = self._map.get((day - timedelta(days=1)).isoformat())
            first = self.first_block_at(day_start_ts(day), head, after=prev)
            if first > head:
                return first  # not reached yet; never cache
            self._map[key] = first
            self._save()
        return self._map[key]

    def day_range(self, day: date, head: int) -> tuple[int, int, bool]:
        """Inclusive block range of a UTC day, and whether the day has ended by ``head``."""
        first = self._first(day, head)
        nxt = self._first(day + timedelta(days=1), head)
        closed = nxt <= head
        return first, (nxt - 1 if closed else head), closed

    def _save(self) -> None:
        self.cache.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.cache.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._map, sort_keys=True))
        os.replace(tmp, self.cache)


@dataclass
class Exclusions:
    """Local-only registry of excluded ids (gitignored; DECISIONS D-030)."""

    path: Path
    question_ids: set[str] = field(default_factory=set)
    market_ids: set[str] = field(default_factory=set)
    condition_ids: set[str] = field(default_factory=set)
    token_ids: set[str] = field(default_factory=set)
    keyword_counts: dict[str, int] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> Exclusions:
        if not path.exists():
            return cls(path)
        raw = json.loads(path.read_text())
        return cls(
            path,
            set(raw["question_ids"]),
            set(raw["market_ids"]),
            set(raw["condition_ids"]),
            set(raw["token_ids"]),
            dict(raw["keyword_counts"]),
        )

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(
                {
                    "question_ids": sorted(self.question_ids),
                    "market_ids": sorted(self.market_ids),
                    "condition_ids": sorted(self.condition_ids),
                    "token_ids": sorted(self.token_ids),
                    "keyword_counts": self.keyword_counts,
                }
            )
        )
        os.replace(tmp, self.path)


class Processor:
    """Turns a chunk of logs into rows per output dataset."""

    name: str
    outputs: tuple[str, ...]
    topics: list[Any]
    addresses: list[str] | None
    initial_chunk: int

    def process(self, logs: list[dict[str, Any]]) -> dict[str, list[Row]]:  # pragma: no cover
        raise NotImplementedError

    def on_flush(self) -> None:
        """Persist processor state before the manifest advances."""


class IdentityProcessor(Processor):
    name = "identity"
    outputs = ("questions_onchain", "conditions_onchain", "tokens_onchain")
    addresses = None
    initial_chunk = 5_000

    def __init__(self, exclusions: Exclusions) -> None:
        self.ex = exclusions
        self.topics = [
            [
                c.TOKEN_REGISTERED,
                c.CONDITION_PREPARATION,
                c.CONDITION_RESOLUTION,
                c.QUESTION_INITIALIZED,
                c.QUESTION_INITIALIZED_LEGACY,
                c.QUESTION_RESOLVED,
                c.QUESTION_PREPARED,
                c.MARKET_PREPARED,
            ]
        ]

    def process(self, logs: list[dict[str, Any]]) -> dict[str, list[Row]]:
        out: dict[str, list[Row]] = {k: [] for k in self.outputs}
        ordered = sorted(logs, key=lambda x: (int(x["blockNumber"], 16), int(x["logIndex"], 16)))
        for lg in ordered:
            if lg.get("removed"):
                continue
            q = decode.decode_question(lg)
            if q is not None:
                if self._question_excluded(q):
                    continue
                out["questions_onchain"].append(q)
                continue
            cond = decode.decode_condition(lg)
            if cond is not None:
                if cond["question_id"] in self.ex.question_ids:
                    self.ex.condition_ids.add(cond["condition_id"])
                    continue
                out["conditions_onchain"].append(cond)
                continue
            tok = decode.decode_token(lg)
            if tok is not None:
                if tok["condition_id"] in self.ex.condition_ids:
                    self.ex.token_ids.update((tok["token0"], tok["token1"]))
                    continue
                out["tokens_onchain"].append(tok)
        return out

    def _question_excluded(self, q: Row) -> bool:
        if q["market_id"] is not None and q["market_id"] in self.ex.market_ids:
            if q["question_id"]:
                self.ex.question_ids.add(q["question_id"])
            return True
        if q["question_id"] is not None and q["question_id"] in self.ex.question_ids:
            return True
        hits = home_jurisdiction.match(q["text"])
        if not hits:
            return False
        for h in hits:
            self.ex.keyword_counts[h] = self.ex.keyword_counts.get(h, 0) + 1
        if q["event"] == "negrisk_market":
            self.ex.market_ids.add(q["market_id"])
        if q["question_id"]:
            self.ex.question_ids.add(q["question_id"])
        return True

    def on_flush(self) -> None:
        self.ex.save()


class FillsProcessor(Processor):
    name = "fills"
    outputs = ("fills_onchain",)
    initial_chunk = 50

    def __init__(self, exclusions: Exclusions, pseudo: Callable[[str], str]) -> None:
        self.ex = exclusions
        self.pseudo = pseudo
        self.topics = [[c.ORDER_FILLED_V1, c.ORDER_FILLED_V2]]
        self.addresses = list(c.EXCHANGES)
        self.dropped_excluded = 0

    def process(self, logs: list[dict[str, Any]]) -> dict[str, list[Row]]:
        rows: list[Row] = []
        for lg in logs:
            if lg.get("removed"):
                continue
            row = decode.decode_fill(lg, self.pseudo)
            if row is None:
                continue
            if row["token_id"] in self.ex.token_ids:
                self.dropped_excluded += 1
                continue
            rows.append(row)
        return {"fills_onchain": rows}


@dataclass
class CrawlStats:
    requests: int = 0
    logs: int = 0
    rows: int = 0
    bytes_hint: int = 0
    started: float = field(default_factory=time.monotonic)


class Crawler:
    def __init__(
        self,
        rpc: RpcClient,
        root: Path,
        processor: Processor,
        flush_rows: int = FLUSH_ROWS,
        should_stop: Callable[[], bool] = lambda: False,
    ) -> None:
        self.rpc = rpc
        self.root = Path(root)
        self.proc = processor
        self.stores = {name: PartitionStore(self.root, name) for name in processor.outputs}
        self.state_store = ManifestStore(self.root, processor.name)
        self.blocks = BlockIndex(rpc, self.root / "_state" / "day_blocks.json")
        self.flush_rows = flush_rows
        self.should_stop = should_stop
        self.chunk = processor.initial_chunk
        self.stats = CrawlStats()

    def crawl(self, start: date, end: date, require: Callable[[date], bool] | None = None) -> None:
        head = self.rpc.block_number() - FINALITY_BLOCKS
        for day in days(start, end):
            if self.should_stop():
                return
            if require is not None and not require(day):
                log.warning("crawl.blocked", crawl=self.proc.name, day=str(day))
                return
            if not self.crawl_day(day, head):
                return  # reached the finality horizon

    def crawl_day(self, day: date, head: int) -> bool:
        """Crawl one UTC day; return True if the day is complete."""
        state = self.state_store.load(day)
        if state is not None and state.complete:
            return True
        first, last, closed = self.blocks.day_range(day, head)
        if state is None:
            state = DayState(first, last, first - 1)
        state.last_block = last
        for store in self.stores.values():
            for p in store.recover(day, state.done_through):
                log.warning("crawl.recovered", removed=str(p))
        buffers: dict[str, list[Row]] = {k: [] for k in self.stores}
        buf_first = state.done_through + 1
        cursor = buf_first
        upto = min(last, head)
        while cursor <= upto:
            if self.should_stop():
                break
            to = min(cursor + self.chunk - 1, upto)
            try:
                logs = self.rpc.get_logs(cursor, to, self.proc.topics, self.proc.addresses)
            except ResultCapExceeded:
                if to == cursor:
                    raise RpcError(f"block {cursor} alone exceeds the provider cap") from None
                self.chunk = max(1, (to - cursor + 1) // 2)
                continue
            self.stats.requests += 1
            self.stats.logs += len(logs)
            for name, rows in self.proc.process(logs).items():
                buffers[name].extend(rows)
            cursor = to + 1
            self._adapt(len(logs))
            if sum(map(len, buffers.values())) >= self.flush_rows:
                self._flush(day, state, buffers, buf_first, to)
                buf_first = to + 1
        if cursor - 1 >= buf_first:
            self._flush(day, state, buffers, buf_first, cursor - 1)
        state.complete = closed and state.done_through >= last
        self.state_store.save(day, state)
        log.info(
            "crawl.day",
            crawl=self.proc.name,
            day=str(day),
            complete=state.complete,
            requests=self.stats.requests,
            logs=self.stats.logs,
            elapsed_s=round(time.monotonic() - self.stats.started, 1),
        )
        return state.complete

    def _adapt(self, n_logs: int) -> None:
        """Aim the next chunk at ``TARGET_LOGS`` logs, growing at most 2x (4x when empty)."""
        if n_logs == 0:
            self.chunk = min(self.chunk * 4, MAX_CHUNK)
            return
        scaled = int(self.chunk * TARGET_LOGS / n_logs)
        self.chunk = max(1, min(scaled, self.chunk * 2, MAX_CHUNK))

    def _flush(
        self, day: date, state: DayState, buffers: dict[str, list[Row]], first: int, last: int
    ) -> None:
        for name, rows in buffers.items():
            if rows:
                self.stores[name].write_part(day, first, last, rows)
                self.stats.rows += len(rows)
            rows.clear()
        self.proc.on_flush()
        state.done_through = last
        self.state_store.save(day, state)


class ManifestStore:
    """Per-crawl day manifests at ``<root>/_state/<crawl>/<date>.json``."""

    def __init__(self, root: Path, crawl: str) -> None:
        self.dir = Path(root) / "_state" / crawl

    def load(self, day: date) -> DayState | None:
        path = self.dir / f"{day.isoformat()}.json"
        return DayState(**json.loads(path.read_text())) if path.exists() else None

    def save(self, day: date, state: DayState) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        path = self.dir / f"{day.isoformat()}.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state.__dict__))
        os.replace(tmp, path)

    def complete(self, day: date) -> bool:
        state = self.load(day)
        return state is not None and state.complete
