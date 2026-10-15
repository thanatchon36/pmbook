"""Binance public spot klines (Tier 1 reference data; no key; MISSION §3.1).

Uses the market-data-only mirror ``data-api.binance.vision``. One partition per UTC day per
symbol; a day is written once complete (1,440 rows) and never refetched.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from pmbook.config import BINANCE_URL
from pmbook.http import PublicClient
from pmbook.store import PartitionStore

SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT")
MINUTES_PER_DAY = 1_440
_MS_DAY = 86_400_000


def _row(symbol: str, k: list[Any]) -> dict[str, Any]:
    return {
        "venue": "binance",
        "symbol": symbol,
        "open_time": int(k[0]),
        "open": float(k[1]),
        "high": float(k[2]),
        "low": float(k[3]),
        "close": float(k[4]),
        "volume": float(k[5]),
        "quote_volume": float(k[7]),
        "trades": int(k[8]),
        "taker_buy_base": float(k[9]),
        "taker_buy_quote": float(k[10]),
    }


def fetch_day(client: PublicClient, symbol: str, day: date) -> list[dict[str, Any]]:
    start = int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp() * 1000)
    end = start + _MS_DAY - 1
    rows: list[dict[str, Any]] = []
    cursor = start
    while cursor <= end:
        batch = client.get_json(
            f"{BINANCE_URL}/api/v3/klines",
            {
                "symbol": symbol,
                "interval": "1m",
                "startTime": cursor,
                "endTime": end,
                "limit": 1000,
            },
        )
        if not batch:
            break
        rows += [_row(symbol, k) for k in batch]
        cursor = int(batch[-1][0]) + 60_000
    return rows


def _days(start: date, end: date) -> Iterator[date]:
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def backfill(
    client: PublicClient, root: Path, start: date, end: date, symbols: tuple[str, ...] = SYMBOLS
) -> dict[str, int]:
    """Fetch missing complete days; return rows written per symbol."""
    store = PartitionStore(root, "reference_binance")
    written = dict.fromkeys(symbols, 0)
    for day in _days(start, end):
        existing = {p.stem.split("-", 1)[1] for p in store.parts(day)}
        for sym in symbols:
            if sym in existing:
                continue
            rows = fetch_day(client, sym, day)
            if len(rows) != MINUTES_PER_DAY:
                continue  # incomplete day (today, or an exchange outage): retry later
            store.write_named(day, f"part-{sym}", rows)
            written[sym] += len(rows)
    return written
