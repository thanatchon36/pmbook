"""Crawler tests against an in-memory chain (no network)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import pytest

from pmbook.onchain import contracts as c
from pmbook.onchain.backfill import (
    BlockIndex,
    Crawler,
    Exclusions,
    FillsProcessor,
    IdentityProcessor,
    days,
)
from pmbook.onchain.rpc import ResultCapExceeded, RpcError

T0 = int(datetime(2026, 3, 30, 23, 0, tzinfo=UTC).timestamp())
CTF_V2 = "0xe111180000d2663c0091e4f400237545b87b996b"


def w(n: int) -> str:
    return f"{n:064x}"


def addr_topic(a: str) -> str:
    return "0x" + "0" * 24 + a[2:]


def dyn(text: str, n_static_after: int) -> str:
    b = text.encode()
    head = w(32 * (1 + n_static_after)) + "".join(w(0) for _ in range(n_static_after))
    pad = b + b"\0" * (-len(b) % 32)
    return head + w(len(b)) + pad.hex()


class FakeChain:
    """Blocks every 2 s from T0; logs placed on chosen blocks; provider cap on results."""

    def __init__(self, n_blocks: int, cap: int = 1_000) -> None:
        self.n = n_blocks
        self.cap = cap
        self.logs: list[dict[str, Any]] = []
        self.calls = 0

    def ts(self, b: int) -> int:
        return T0 + 2 * b

    def add(self, block: int, address: str, topics: list[str], data: str) -> None:
        self.logs.append(
            {
                "address": address,
                "topics": topics,
                "data": "0x" + data,
                "blockNumber": hex(block),
                "blockTimestamp": hex(self.ts(block)),
                "transactionHash": "0x" + w(block),
                "logIndex": hex(len(self.logs)),
                "removed": False,
            }
        )

    # RpcClient surface used by the crawler
    def block_number(self) -> int:
        return self.n

    def block_timestamp(self, n: int) -> int:
        return self.ts(n)

    def get_logs(self, a: int, b: int, topics: list[Any], address: Any = None) -> list[Any]:
        self.calls += 1
        want = set(topics[0])
        out = [
            lg
            for lg in self.logs
            if a <= int(lg["blockNumber"], 16) <= b
            and lg["topics"][0] in want
            and (address is None or lg["address"] in address)
        ]
        if len(out) > self.cap:
            raise ResultCapExceeded("more than cap")
        return out


def fill(chain: FakeChain, block: int, token: int, taker_leg: bool = False) -> None:
    taker = CTF_V2 if taker_leg else "0x" + "22" * 20
    chain.add(
        block,
        CTF_V2,
        [c.ORDER_FILLED_V2, "0x" + w(block), addr_topic("0x" + "11" * 20), addr_topic(taker)],
        w(0) + w(token) + w(40_000_000) + w(100_000_000) + w(0) + w(0) + w(0),
    )


def identity(chain: FakeChain, block: int, qid: int, cond: int, tok: int, text: str) -> None:
    chain.add(
        block,
        "0x" + "65" * 20,
        [c.QUESTION_INITIALIZED, "0x" + w(qid), "0x" + w(1), addr_topic("0x" + "33" * 20)],
        dyn(text, 3),
    )
    chain.add(
        block,
        c.CONDITIONAL_TOKENS,
        [c.CONDITION_PREPARATION, "0x" + w(cond), addr_topic("0x" + "65" * 20), "0x" + w(qid)],
        w(2),
    )
    chain.add(
        block + 1,
        "0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e",
        [c.TOKEN_REGISTERED, "0x" + w(tok), "0x" + w(tok + 1), "0x" + w(cond)],
        "",
    )


def read(root: Path, dataset: str) -> list[dict[str, Any]]:
    files = sorted((root / f"dataset={dataset}").rglob("*.parquet"))
    return [r for f in files for r in pq.read_table(f).to_pylist()]


@pytest.fixture
def chain() -> FakeChain:
    # 1800 blocks before midnight (T0 = 23:00) and 1800 after.
    ch = FakeChain(7_000)
    identity(ch, 100, qid=1, cond=11, tok=101, text="q: title: Will Bitcoin hit 100k?")
    identity(ch, 200, qid=2, cond=22, tok=201, text="q: title: Will Thailand hold an election?")
    for b in range(1_000, 2_600, 2):
        fill(ch, b, 101, taker_leg=b % 4 == 0)
        fill(ch, b, 201)
    return ch


def test_block_index_day_range(chain: FakeChain, tmp_path: Path) -> None:
    idx = BlockIndex(chain, tmp_path / "blocks.json")  # type: ignore[arg-type]
    first, last, closed = idx.day_range(date(2026, 3, 31), chain.n)
    assert chain.ts(first) == T0 + 3600 and chain.ts(first - 1) < T0 + 3600
    assert not closed and last == chain.n
    _first0, last0, closed0 = idx.day_range(date(2026, 3, 30), chain.n)
    assert closed0 and last0 == first - 1
    # cached boundaries survive a restart
    assert BlockIndex(chain, tmp_path / "blocks.json")._map  # type: ignore[arg-type]


def test_identity_then_fills_with_exclusion(chain: FakeChain, tmp_path: Path) -> None:
    ex = Exclusions.load(tmp_path / "filters" / "excluded.json")
    crawler = Crawler(chain, tmp_path, IdentityProcessor(ex), flush_rows=50)  # type: ignore[arg-type]
    crawler.crawl(date(2026, 3, 30), date(2026, 3, 31))
    questions = read(tmp_path, "questions_onchain")
    assert [q["question_id"][-1] for q in questions] == ["1"]
    assert all("thailand" not in (q["text"] or "").lower() for q in questions)
    assert len(read(tmp_path, "conditions_onchain")) == 1
    assert {t["token0"] for t in read(tmp_path, "tokens_onchain")} == {"101"}
    ex2 = Exclusions.load(tmp_path / "filters" / "excluded.json")
    assert ex2.token_ids == {"201", "202"} and ex2.keyword_counts == {"thailand": 1}

    ident = crawler.state_store
    fills = Crawler(chain, tmp_path, FillsProcessor(ex2, lambda a: "h" + a[-4:]), flush_rows=300)  # type: ignore[arg-type]
    fills.crawl(date(2026, 3, 30), date(2026, 3, 31), require=ident.complete)
    rows = read(tmp_path, "fills_onchain")
    # 31 Mar is blocked: identity is not complete for it yet (the day is still open).
    assert len(rows) == 400 and {r["token_id"] for r in rows} == {"101"}
    assert fills.proc.dropped_excluded == 400  # type: ignore[attr-defined]
    assert sum(r["is_taker_leg"] for r in rows) == 200
    assert {r["venue"] for r in rows} == {"polymarket"}
    # day 1 is complete; day 2 is still open at the head
    assert fills.state_store.complete(date(2026, 3, 30))
    assert not fills.state_store.complete(date(2026, 3, 31))
    # partitions follow block timestamps
    d30 = {
        r["block_ts"].date()
        for r in pq.read_table(fills.stores["fills_onchain"].day_dir(date(2026, 3, 30))).to_pylist()
    }
    assert d30 == {date(2026, 3, 30)}


def test_cap_halving_and_resume(chain: FakeChain, tmp_path: Path) -> None:
    chain.cap = 120
    ex = Exclusions(tmp_path / "x.json")
    stops = iter([False] * 6 + [True] * 1000)
    crawler = Crawler(
        chain, tmp_path, FillsProcessor(ex, str), flush_rows=100, should_stop=lambda: next(stops)
    )  # type: ignore[arg-type]
    crawler.crawl(date(2026, 3, 30), date(2026, 3, 30))
    partial = crawler.state_store.load(date(2026, 3, 30))
    assert partial is not None and not partial.complete
    # simulate an interrupted flush: an orphan part beyond done_through and a tmp file
    d = crawler.stores["fills_onchain"].day_dir(date(2026, 3, 30))
    (d / f"part-{partial.done_through + 1}-999999.parquet").write_bytes(b"junk")
    (d / "x.parquet.tmp").write_bytes(b"junk")
    resumed = Crawler(chain, tmp_path, FillsProcessor(ex, str), flush_rows=100)  # type: ignore[arg-type]
    resumed.crawl(date(2026, 3, 30), date(2026, 3, 30))
    rows = read(tmp_path, "fills_onchain")
    keys = [(r["tx_hash"], r["log_index"]) for r in rows]
    assert len(keys) == len(set(keys))
    expected = [
        lg
        for lg in chain.logs
        if lg["topics"][0] == c.ORDER_FILLED_V2 and chain.ts(int(lg["blockNumber"], 16)) < T0 + 3600
    ]
    assert len(rows) == len(expected)
    assert resumed.state_store.complete(date(2026, 3, 30))


def test_single_block_over_cap_fails(tmp_path: Path) -> None:
    ch = FakeChain(3_000, cap=1)
    fill(ch, 10, 5)
    fill(ch, 10, 6)
    crawler = Crawler(ch, tmp_path, FillsProcessor(Exclusions(tmp_path / "x"), str))  # type: ignore[arg-type]
    with pytest.raises(RpcError, match="alone exceeds"):
        crawler.crawl(date(2026, 3, 30), date(2026, 3, 30))


def test_blocked_until_identity_done(chain: FakeChain, tmp_path: Path) -> None:
    crawler = Crawler(chain, tmp_path, FillsProcessor(Exclusions(tmp_path / "x"), str))  # type: ignore[arg-type]
    crawler.crawl(date(2026, 3, 30), date(2026, 3, 30), require=lambda d: False)
    assert chain.calls == 0


def test_days_inclusive() -> None:
    assert len(list(days(date(2026, 1, 30), date(2026, 2, 2)))) == 4


def test_validate_report(chain: FakeChain, tmp_path: Path) -> None:
    from pmbook.validate import check_fills_day, coverage_report

    assert "no data" in coverage_report(tmp_path).summary
    ex = Exclusions(tmp_path / "x.json")
    Crawler(chain, tmp_path, IdentityProcessor(ex)).crawl(date(2026, 3, 30), date(2026, 3, 30))  # type: ignore[arg-type]
    Crawler(chain, tmp_path, FillsProcessor(ex, str)).crawl(date(2026, 3, 30), date(2026, 3, 30))  # type: ignore[arg-type]
    report = coverage_report(tmp_path)
    assert "fills: 1/1 days complete" in report.summary
    assert "| 2026-03-30 |" in report.markdown
    # The synthetic chain puts V2 fills in March and a taker leg only on every other tx;
    # both must be caught.
    assert any("200 transactions without a taker leg" in e for e in report.errors)
    assert any("V2 fills before the migration" in e for e in report.errors)
    day_dir = tmp_path / "dataset=fills_onchain" / "date=2026-03-30"
    assert not any("V2" in e for e in check_fills_day(day_dir, date(2026, 5, 1)))


def test_block_index_uses_previous_day_hint(chain: FakeChain, tmp_path: Path) -> None:
    calls: list[int] = []
    real = chain.block_timestamp

    def counting(n: int) -> int:
        calls.append(n)
        return real(n)

    chain.block_timestamp = counting  # type: ignore[method-assign]
    idx = BlockIndex(chain, tmp_path / "b.json")  # type: ignore[arg-type]
    idx._map["2026-03-30"] = 1  # known boundary one day earlier
    first = idx.first_block_at(T0 + 3600, chain.n, after=1)
    assert chain.ts(first) >= T0 + 3600 > chain.ts(first - 1)
    assert len(calls) <= 12


def test_identity_join_coverage(chain: FakeChain, tmp_path: Path) -> None:
    from pmbook.validate import identity_join

    assert identity_join(tmp_path) == {}
    Crawler(chain, tmp_path, IdentityProcessor(Exclusions(tmp_path / "x.json"))).crawl(  # type: ignore[arg-type]
        date(2026, 3, 30), date(2026, 3, 30)
    )
    assert identity_join(tmp_path) == {"conditions": 1, "with_preparation": 1, "with_text": 1}
