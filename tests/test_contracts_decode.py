import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from pmbook.onchain import contracts as c
from pmbook.onchain import decode

FIX: dict[str, Any] = json.loads((Path(__file__).parent / "fixtures_logs.json").read_text())


def pseudo(addr: str) -> str:
    return "id:" + addr


@pytest.mark.parametrize(
    ("topic", "prefix", "suffix"),
    [
        (c.ORDER_FILLED_V1, "0xd0a08e8c", "c0f6"),
        (c.ORDERS_MATCHED_V1, "0x63bf4d16", "956c"),
        (c.ORDER_FILLED_V2, "0xd543adfd", "d8ee"),
        (c.ORDERS_MATCHED_V2, "0x174b3811", "ab7c"),
        (c.FEE_CHARGED, "0x55bb3cad", "0ab1"),
        (c.TOKEN_REGISTERED, "0xbc9a2432", "af0d"),
    ],
)
def test_topics_match_verified_hashes(topic: str, prefix: str, suffix: str) -> None:
    assert topic.startswith(prefix) and topic.endswith(suffix)


@pytest.mark.parametrize("key", ["v1_match", "v2_match"])
def test_match_has_exactly_one_taker_leg(key: str) -> None:
    rows = [r for lg in FIX[key] if (r := decode.decode_fill(lg, pseudo)) is not None]
    assert len(rows) >= 3
    takers = [r for r in rows if r["is_taker_leg"]]
    assert len(takers) == 1
    matched = [
        lg for lg in FIX[key] if lg["topics"][0] in (c.ORDERS_MATCHED_V1, c.ORDERS_MATCHED_V2)
    ]
    # OrdersMatched.takerOrderMaker is the taker leg's maker (METHODS §2.2).
    assert takers[0]["maker_id"] == pseudo(decode._addr(matched[0]["topics"][2]))
    for r in rows:
        assert 0 < r["price"] < 1
        assert r["maker_id"].startswith("id:0x")
        assert len(r["tx_hash"]) == 66


def test_v2_taker_fee_equals_fee_charged() -> None:
    rows = [r for lg in FIX["v2_match"] if (r := decode.decode_fill(lg, pseudo)) is not None]
    fee_charged = [lg for lg in FIX["v2_match"] if lg["topics"][0] == c.FEE_CHARGED]
    taker = next(r for r in rows if r["is_taker_leg"])
    assert taker["fee"] == int(fee_charged[0]["data"], 16)
    assert all(r["fee"] == 0 for r in rows if not r["is_taker_leg"])
    assert taker["fee_asset"] == "collateral"


def test_v1_fee_asset_follows_received_asset() -> None:
    rows = [r for lg in FIX["v1_match"] if (r := decode.decode_fill(lg, pseudo)) is not None]
    for r in rows:
        assert r["fee_asset"] == ("shares" if r["side"] == "BUY" else "collateral")


def test_fill_decoder_ignores_other_logs() -> None:
    lg = dict(FIX["v1_match"][0])
    assert decode.decode_fill(lg | {"address": "0x" + "ab" * 20}, pseudo) is None
    assert decode.decode_fill(FIX["TokenRegistered"][0], pseudo) is None


def test_identity_decoders() -> None:
    tok = decode.decode_token(FIX["TokenRegistered"][0])
    assert tok is not None and tok["condition_id"].startswith("0x") and tok["token0"].isdigit()
    prep = decode.decode_condition(FIX["ConditionPreparation"][0])
    assert prep is not None and prep["event"] == "preparation" and prep["outcome_slot_count"] == 2
    res = decode.decode_condition(FIX["ConditionResolution"][0])
    assert res is not None and res["event"] == "resolution" and len(res["payouts"]) == 2
    qi = decode.decode_question(FIX["QuestionInitialized"][0])
    assert qi is not None and qi["text"].startswith("q: title:")
    qr = decode.decode_question(FIX["QuestionResolved"][0])
    assert qr is not None and qr["event"] == "uma_resolved" and qr["payouts"]
    qp = decode.decode_question(FIX["QuestionPrepared"][0])
    assert qp is not None and qp["text"].startswith("question:") and qp["market_id"]
    mp = decode.decode_question(FIX["MarketPrepared"][0])
    assert mp is not None and mp["text"].startswith("title:")
    assert decode.decode_question(FIX["v1_match"][0]) is None
    assert decode.decode_token(FIX["v1_match"][0]) is None
    assert decode.decode_condition(FIX["v1_match"][0]) is None


def test_fixture_counts() -> None:
    kinds = Counter(lg["topics"][0][:10] for lg in FIX["v2_match"])
    assert kinds[c.FEE_CHARGED[:10]] == 1


def test_legacy_question_initialized() -> None:
    text = b"q: title: NFL Thursday: Dolphins vs. Bengals"
    head = f"{224:064x}" + "0" * 64 * 6  # offset to bytes after 7 head words
    data = "0x" + head + f"{len(text):064x}" + (text + b"\0" * (-len(text) % 32)).hex()
    lg = {
        "address": "0xcb1822859cef82cd2eb4e6276c7916e692995130",
        "topics": [c.QUESTION_INITIALIZED_LEGACY, "0x" + "ab" * 32],
        "data": data,
        "blockNumber": "0x1",
        "blockTimestamp": "0x2",
        "transactionHash": "0x" + "00" * 32,
        "logIndex": "0x0",
    }
    row = decode.decode_question(lg)
    assert row is not None and row["event"] == "uma_initialized" and row["text"] == text.decode()


def test_foreign_token_registered_is_ignored() -> None:
    """Unrelated contracts emit TokenRegistered with other emitters and indexing (D-038)."""
    base = {
        "data": "0x" + "11" * 32,
        "blockNumber": "0x1",
        "blockTimestamp": "0x2",
        "transactionHash": "0x" + "00" * 32,
        "logIndex": "0x0",
    }
    three = base | {
        "address": "0xa4e076849c55287ca93e4506e76de4731e290ab5",
        "topics": [c.TOKEN_REGISTERED, "0x" + "01" * 32, "0x" + "02" * 32],
    }
    four_foreign = base | {
        "address": "0x87b81fd5b3845f68854f7c407477bad1bc1108d1",
        "topics": [c.TOKEN_REGISTERED, "0x" + "01" * 32, "0x" + "02" * 32, "0x" + "03" * 32],
    }
    assert decode.decode_token(three) is None
    assert decode.decode_token(four_foreign) is None
    assert decode.decode_question(three) is None
