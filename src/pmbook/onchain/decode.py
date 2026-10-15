"""Pure decoders from raw ``eth_getLogs`` entries to table rows (rules in docs/METHODS.md §2).

Fills: one row per ``OrderFilled`` log ("leg"). The taker leg is the one whose ``taker`` is
the emitting exchange; its ``maker`` field is the taker's wallet. Addresses are replaced by
pseudonymous ids before a row is returned.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from pmbook.onchain import contracts as c

Log = Mapping[str, Any]
Row = dict[str, Any]


def _words(data: str) -> list[int]:
    raw = data[2:] if data.startswith("0x") else data
    return [int(raw[i : i + 64], 16) for i in range(0, len(raw), 64)]


def _topics(log: Log, n: int) -> bool:
    """Same topic0 can be emitted by unrelated contracts with different indexing."""
    return len(log["topics"]) == n


def _addr(topic: str) -> str:
    return "0x" + topic[-40:].lower()


def _base(log: Log) -> Row:
    return {
        "block_number": int(log["blockNumber"], 16),
        "block_ts": int(log["blockTimestamp"], 16),
        "tx_hash": log["transactionHash"].lower(),
        "log_index": int(log["logIndex"], 16),
    }


def _dyn_bytes(data: str, offset_word: int) -> bytes:
    """ABI-decode a dynamic ``bytes`` argument whose head offset sits in word ``offset_word``."""
    raw = bytes.fromhex(data[2:])
    off = int.from_bytes(raw[32 * offset_word : 32 * offset_word + 32], "big")
    n = int.from_bytes(raw[off : off + 32], "big")
    return raw[off + 32 : off + 32 + n]


def _text(b: bytes) -> str:
    return b.decode("utf-8", errors="replace")


def decode_fill(log: Log, pseudo: Callable[[str], str]) -> Row | None:
    """Decode a V1 or V2 ``OrderFilled`` from a venue exchange; ``None`` for anything else."""
    address = log["address"].lower()
    ex = c.EXCHANGES.get(address)
    t0 = log["topics"][0].lower()
    if ex is None or t0 not in (c.ORDER_FILLED_V1, c.ORDER_FILLED_V2) or not _topics(log, 4):
        return None
    w = _words(log["data"])
    maker, taker = _addr(log["topics"][2]), _addr(log["topics"][3])
    if t0 == c.ORDER_FILLED_V1:
        maker_asset, taker_asset, maker_amt, taker_amt, fee = w[:5]
        # Asset id 0 is collateral; the order's maker gives makerAsset and receives takerAsset.
        if maker_asset == 0:
            side, token, collateral, shares = "BUY", taker_asset, maker_amt, taker_amt
        else:
            side, token, collateral, shares = "SELL", maker_asset, taker_amt, maker_amt
        # V1 fee is charged in the asset the order receives (METHODS §2.2).
        fee_asset = "shares" if side == "BUY" else "collateral"
    else:
        side_n, token, maker_amt, taker_amt, fee = w[:5]
        side = "BUY" if side_n == 0 else "SELL"
        collateral, shares = (maker_amt, taker_amt) if side == "BUY" else (taker_amt, maker_amt)
        fee_asset = "collateral"
    return _base(log) | {
        "exchange": ex.name,
        "exchange_version": ex.version,
        "neg_risk": ex.neg_risk,
        "order_hash": log["topics"][1].lower(),
        "maker_id": pseudo(maker),
        "taker_id": pseudo(taker),
        "is_taker_leg": taker == address,
        "side": side,
        "token_id": str(token),
        "collateral_amount": collateral,
        "share_amount": shares,
        "fee": fee,
        "fee_asset": fee_asset,
        "price": collateral / shares if shares else None,
    }


def decode_token(log: Log) -> Row | None:
    """Venue exchanges only: other contracts reuse the ``TokenRegistered`` signature."""
    if (
        log["topics"][0].lower() != c.TOKEN_REGISTERED
        or log["address"].lower() not in c.EXCHANGES
        or not _topics(log, 4)
    ):
        return None
    return _base(log) | {
        "emitter": log["address"].lower(),
        "token0": str(int(log["topics"][1], 16)),
        "token1": str(int(log["topics"][2], 16)),
        "condition_id": log["topics"][3].lower(),
    }


def decode_condition(log: Log) -> Row | None:
    t0 = log["topics"][0].lower()
    events = (c.CONDITION_PREPARATION, c.CONDITION_RESOLUTION)
    if log["address"].lower() != c.CONDITIONAL_TOKENS or t0 not in events or not _topics(log, 4):
        return None
    w = _words(log["data"])
    resolved = t0 == c.CONDITION_RESOLUTION
    payouts: list[int] | None = None
    if resolved:  # (outcomeSlotCount, offset, len, payouts...)
        n = w[2]
        payouts = w[3 : 3 + n]
    return _base(log) | {
        "event": "resolution" if resolved else "preparation",
        "condition_id": log["topics"][1].lower(),
        "oracle": _addr(log["topics"][2]),
        "question_id": log["topics"][3].lower(),
        "outcome_slot_count": w[0],
        "payouts": [str(p) for p in payouts] if payouts is not None else None,
    }


def decode_question(log: Log) -> Row | None:
    """UMA adapter questions/resolutions and NegRisk adapter market/question text."""
    t0 = log["topics"][0].lower()
    row = _base(log) | {
        "emitter": log["address"].lower(),
        "question_id": None,
        "market_id": None,
        "event": None,
        "text": None,
        "settled_price": None,
        "payouts": None,
        "index": None,
    }
    want = {
        c.QUESTION_INITIALIZED: 4,
        c.QUESTION_INITIALIZED_LEGACY: 2,
        c.QUESTION_RESOLVED: 3,
        c.QUESTION_PREPARED: 3,
        c.MARKET_PREPARED: 3,
    }.get(t0)
    if want is None or not _topics(log, want):
        return None
    if t0 in (c.QUESTION_INITIALIZED, c.QUESTION_INITIALIZED_LEGACY):
        row |= {
            "event": "uma_initialized",
            "question_id": log["topics"][1].lower(),
            "text": _text(_dyn_bytes(log["data"], 0)),
        }
    elif t0 == c.QUESTION_RESOLVED:
        w = _words(log["data"])
        price = int(log["topics"][2], 16)
        if price >= 2**255:
            price -= 2**256
        row |= {
            "event": "uma_resolved",
            "question_id": log["topics"][1].lower(),
            "settled_price": str(price),
            "payouts": [str(p) for p in w[2 : 2 + w[1]]],
        }
    elif t0 == c.QUESTION_PREPARED and log["address"].lower() == c.NEG_RISK_ADAPTER:
        row |= {
            "event": "negrisk_question",
            "market_id": log["topics"][1].lower(),
            "question_id": log["topics"][2].lower(),
            "index": _words(log["data"])[0],
            "text": _text(_dyn_bytes(log["data"], 1)),
        }
    elif t0 == c.MARKET_PREPARED and log["address"].lower() == c.NEG_RISK_ADAPTER:
        row |= {
            "event": "negrisk_market",
            "market_id": log["topics"][1].lower(),
            "text": _text(_dyn_bytes(log["data"], 1)),
        }
    else:
        return None
    return row
