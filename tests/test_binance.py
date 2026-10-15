from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
import pyarrow.parquet as pq

from pmbook.config import Settings
from pmbook.http import PublicClient
from pmbook.reference import binance

DAY = date(2025, 10, 1)
START = int(datetime(2025, 10, 1, tzinfo=UTC).timestamp() * 1000)


def kline(t: int) -> list[Any]:
    return [t, "1", "2", "0.5", "1.5", "10", t + 59_999, "15", 7, "4", "6", "0"]


def handler_factory(minutes: int, calls: list[dict[str, Any]]) -> Any:
    def handler(req: httpx.Request) -> httpx.Response:
        q = dict(req.url.params)
        calls.append(q)
        assert req.url.host == "data-api.binance.vision"
        start = int(q["startTime"])
        first = (start - START) // 60_000
        n = max(0, min(int(q["limit"]), minutes - first))
        return httpx.Response(200, json=[kline(start + 60_000 * i) for i in range(n)])

    return handler


def client(minutes: int, calls: list[dict[str, Any]]) -> PublicClient:
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    return PublicClient(s, transport=httpx.MockTransport(handler_factory(minutes, calls)))


def test_fetch_day_pages(tmp_path: Path) -> None:
    calls: list[dict[str, Any]] = []
    rows = binance.fetch_day(client(1_440, calls), "BTCUSDT", DAY)
    assert len(rows) == 1_440 and len(calls) == 2
    assert rows[0]["close"] == 1.5 and rows[0]["trades"] == 7 and rows[0]["venue"] == "binance"


def test_backfill_writes_complete_days_once(tmp_path: Path) -> None:
    calls: list[dict[str, Any]] = []
    out = binance.backfill(client(1_440, calls), tmp_path, DAY, DAY, ("BTCUSDT",))
    assert out == {"BTCUSDT": 1_440}
    path = tmp_path / "dataset=reference_binance" / "date=2025-10-01" / "part-BTCUSDT.parquet"
    t = pq.read_table(path)
    assert t.num_rows == 1_440 and set(t.column("venue").to_pylist()) == {"binance"}
    n = len(calls)
    assert binance.backfill(client(1_440, calls), tmp_path, DAY, DAY, ("BTCUSDT",)) == {
        "BTCUSDT": 0
    }
    assert len(calls) == n


def test_incomplete_day_not_written(tmp_path: Path) -> None:
    out = binance.backfill(client(900, []), tmp_path, DAY, DAY, ("ETHUSDT",))
    assert out == {"ETHUSDT": 0}
    assert not (tmp_path / "dataset=reference_binance").exists()
