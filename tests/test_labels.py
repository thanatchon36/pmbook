import csv
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import pytest

from pmbook.labels import build
from pmbook.labels.categories import CATEGORIES, RATE_GROUP, classify
from pmbook.reference import fee_timeline
from pmbook.store import PartitionStore

UMA = "0x65070be91477460d8a7aeeb94ef92fe056c2f2a7"
SHORT = "0x58e1745bedda7312c4cddb72618923da1b90efde"
EX = "0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e"


@pytest.mark.parametrize(
    ("title", "category"),
    [
        ("Texas Tech Red Raiders vs. Alabama Crimson Tide: O/U 165.5", "sports"),
        ("UNLV Runnin' Rebels vs. Tulsa Golden Hurricane", "sports"),
        ("Spread: Arizona Wildcats (-11.5)", "sports"),
        ("Dota 2: Aurora vs Silk - Game 1 Winner", "sports"),
        ("Will Bitcoin reach $77,000 on March 24?", "crypto"),
        ("Highest temperature in Miami on April 10?", "weather"),
        ("Will the Fed cut rates in June?", "economics"),
        ("Russia x Ukraine ceasefire by June 30?", "geopolitics"),
        ("Mamdani vs. Cuomo: who wins the NYC mayoral election?", "politics"),
        ('Will Leavitt say "Kristi" or "Noem" during the next press briefing?', "mentions"),
        ("Will Gemini 3 be the top AI model on May 1?", "tech"),
        ("Will NVIDIA close above $200 on Friday?", "finance"),
        ("Will Taylor Swift's album debut at #1 on the Billboard 200?", "culture"),
        ("Will it happen?", "other"),
    ],
)
def test_classify_examples(title: str, category: str) -> None:
    assert classify(title).category == category


def test_short_crypto_flags() -> None:
    assert classify(None, text_source="short_crypto_resolver").short_crypto
    lab = classify("Bitcoin Up or Down - January 10, 6AM ET")
    assert lab.category == "crypto" and lab.short_crypto
    assert not classify("Bitcoin Up or Down in 2026?").short_crypto


def test_rate_groups_cover_all_categories() -> None:
    assert set(RATE_GROUP) == set(CATEGORIES)


def test_fee_timeline_rows_have_sources() -> None:
    t = fee_timeline.table()
    assert t.num_rows >= 10
    assert all(t["sources"].to_pylist())
    v2 = [r for r in t.to_pylist() if r["note"] == "Fee Structure V2."]
    assert {r["scope"] for r in v2} == set(CATEGORIES)


def _log(day: date, i: int) -> dict[str, Any]:
    return {
        "block_number": 1000 + i,
        "block_ts": datetime(day.year, day.month, day.day, 12, tzinfo=UTC),
        "tx_hash": f"0x{i:064x}",
        "log_index": i,
    }


def _fixture(root: Path) -> None:
    d0, d1 = date(2026, 3, 1), date(2026, 4, 10)
    cid_a, cid_b, cid_c = ("0x" + ch * 64 for ch in "abc")
    qid_a, qid_b, qid_c = ("0x" + ch * 64 for ch in "def")
    PartitionStore(root, "questions_onchain").write_named(
        d0,
        "p",
        [
            _log(d0, 1)
            | {
                "emitter": UMA,
                "event": "uma_initialized",
                "question_id": qid_a,
                "text": "q: title: Will the Fed cut rates in June?, description: Fed decision."
                " market_id: 7 res_data: p1: 0, p2: 1,initializer:abc",
            },
            _log(d0, 2)
            | {
                "emitter": UMA,
                "event": "uma_initialized",
                "question_id": qid_b,
                "text": '{"q": {"title": "Russia x Ukraine ceasefire?", "description": "War."}}',
            },
        ],
    )
    PartitionStore(root, "conditions_onchain").write_named(
        d0,
        "p",
        [
            _log(d0, 3 + i)
            | {
                "event": "preparation",
                "condition_id": cid,
                "oracle": oracle,
                "question_id": qid,
                "outcome_slot_count": 2,
                "payouts": None,
            }
            for i, (cid, oracle, qid) in enumerate(
                [(cid_a, UMA, qid_a), (cid_b, UMA, qid_b), (cid_c, SHORT, qid_c)]
            )
        ],
    )
    PartitionStore(root, "tokens_onchain").write_named(
        d0,
        "p",
        [
            _log(d0, 10 + i)
            | {"emitter": EX, "token0": f"{i}1", "token1": f"{i}2", "condition_id": cid}
            for i, cid in enumerate([cid_a, cid_b, cid_c])
        ],
    )
    fills = []
    # Economics market at rate 0.05 (V2 formula), geopolitics at zero fee: 6 legs each.
    for k in range(6):
        for tok, fee in (("01", 0.05 * 100 * 0.4 * 0.6), ("11", 0.0)):
            fills.append(
                _log(d1, 100 + len(fills))
                | {
                    "exchange": "ctf_v2",
                    "exchange_version": 2,
                    "neg_risk": False,
                    "order_hash": f"0x{k:064x}",
                    "maker_id": "m",
                    "taker_id": "t",
                    "is_taker_leg": True,
                    "side": "BUY",
                    "token_id": tok,
                    "collateral_amount": 40_000_000,
                    "share_amount": 100_000_000,
                    "fee": round(fee * 1_000_000),
                    "fee_asset": "collateral",
                    "price": 0.4,
                }
            )
    PartitionStore(root, "fills_onchain").write_named(d1, "p", fills)


def test_build_and_evaluate(tmp_path: Path) -> None:
    _fixture(tmp_path)
    counts = build.build(tmp_path)
    assert counts == {"markets": 3, "silver": 2}
    m = {
        r["condition_id"][:4]: r
        for r in pq.read_table(tmp_path / "derived/markets.parquet").to_pylist()
    }
    assert m["0xaa"]["title"] == "Will the Fed cut rates in June?"
    assert m["0xaa"]["description"] == "Fed decision."  # payout map and initializer dropped
    assert m["0xbb"]["title"] == "Russia x Ukraine ceasefire?"  # JSON ancillary data
    assert m["0xcc"]["text_source"] == "short_crypto_resolver"
    silver = {
        r["condition_id"][:4]: r["silver_group"]
        for r in pq.read_table(tmp_path / "derived/silver_labels.parquet").to_pylist()
    }
    assert silver == {"0xaa": "r05", "0xbb": "r00"}

    path = build.sample(tmp_path, n=2, floor=1)
    with path.open() as fh:
        rows = list(csv.DictReader(fh))
    assert {r["predicted"] for r in rows} == {"economics", "geopolitics"}
    for r in rows:
        r |= {"label": r["predicted"], "annotator": "test"}
    with (tmp_path / "labels/hand_labels.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=build.HAND_FIELDS)
        w.writeheader()
        w.writerows(rows)
    text = "\n".join(build.evaluate(tmp_path))
    assert text.count("Accuracy: 1.000") == 2
    assert "Annotator(s): test." in text
