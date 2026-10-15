"""pyarrow schemas for every dataset pmbook writes, plus schema versioning (MISSION §3.3).

Every Parquet file carries ``pmbook.dataset`` and ``pmbook.schema_version`` in its key-value
metadata, and every table has a ``venue`` column. Bump ``SCHEMA_VERSION`` on any column change
and log it in docs/DECISIONS.md.
"""

from __future__ import annotations

import pyarrow as pa

SCHEMA_VERSION = "1.0"
VENUE = "polymarket"

TS = pa.timestamp("s", tz="UTC")
_LOG = [
    pa.field("venue", pa.string(), nullable=False),
    pa.field("block_number", pa.int64(), nullable=False),
    pa.field("block_ts", TS, nullable=False),
    pa.field("tx_hash", pa.string(), nullable=False),
    pa.field("log_index", pa.int32(), nullable=False),
]

SCHEMAS: dict[str, pa.Schema] = {
    # One row per OrderFilled log (maker legs and the taker leg). Amounts in raw 6-dp units.
    "fills_onchain": pa.schema(
        [
            *_LOG,
            pa.field("exchange", pa.string(), nullable=False),
            pa.field("exchange_version", pa.int8(), nullable=False),
            pa.field("neg_risk", pa.bool_(), nullable=False),
            pa.field("order_hash", pa.string(), nullable=False),
            pa.field("maker_id", pa.string(), nullable=False),  # pseudonymous
            pa.field("taker_id", pa.string(), nullable=False),  # pseudonymous
            pa.field("is_taker_leg", pa.bool_(), nullable=False),
            pa.field("side", pa.string(), nullable=False),  # side of this leg's order
            pa.field("token_id", pa.string(), nullable=False),  # uint256 as decimal string
            pa.field("collateral_amount", pa.int64()),
            pa.field("share_amount", pa.int64()),
            pa.field("fee", pa.int64()),
            pa.field("fee_asset", pa.string(), nullable=False),  # "collateral" | "shares"
            pa.field("price", pa.float64()),
        ]
    ),
    "tokens_onchain": pa.schema(
        [
            *_LOG,
            pa.field("emitter", pa.string(), nullable=False),
            pa.field("token0", pa.string(), nullable=False),
            pa.field("token1", pa.string(), nullable=False),
            pa.field("condition_id", pa.string(), nullable=False),
        ]
    ),
    "conditions_onchain": pa.schema(
        [
            *_LOG,
            pa.field("event", pa.string(), nullable=False),  # preparation | resolution
            pa.field("condition_id", pa.string(), nullable=False),
            pa.field("oracle", pa.string(), nullable=False),  # contract, not a person
            pa.field("question_id", pa.string(), nullable=False),
            pa.field("outcome_slot_count", pa.int32(), nullable=False),
            pa.field("payouts", pa.list_(pa.string())),
        ]
    ),
    "questions_onchain": pa.schema(
        [
            *_LOG,
            pa.field("emitter", pa.string(), nullable=False),
            pa.field("event", pa.string(), nullable=False),
            pa.field("question_id", pa.string()),
            pa.field("market_id", pa.string()),
            pa.field("text", pa.string()),
            pa.field("settled_price", pa.string()),
            pa.field("payouts", pa.list_(pa.string())),
            pa.field("index", pa.int32()),
        ]
    ),
    # Binance public 1-minute spot klines (venue = "binance"); RQ4 reference prices.
    "reference_binance": pa.schema(
        [
            pa.field("venue", pa.string(), nullable=False),
            pa.field("symbol", pa.string(), nullable=False),
            pa.field("open_time", pa.timestamp("ms", tz="UTC"), nullable=False),
            pa.field("open", pa.float64(), nullable=False),
            pa.field("high", pa.float64(), nullable=False),
            pa.field("low", pa.float64(), nullable=False),
            pa.field("close", pa.float64(), nullable=False),
            pa.field("volume", pa.float64(), nullable=False),
            pa.field("quote_volume", pa.float64(), nullable=False),
            pa.field("trades", pa.int64(), nullable=False),
            pa.field("taker_buy_base", pa.float64(), nullable=False),
            pa.field("taker_buy_quote", pa.float64(), nullable=False),
        ]
    ),
}


def schema_for(dataset: str) -> pa.Schema:
    """Schema for ``dataset`` with pmbook metadata attached."""
    return SCHEMAS[dataset].with_metadata(
        {"pmbook.dataset": dataset, "pmbook.schema_version": SCHEMA_VERSION}
    )


def read_version(schema: pa.Schema) -> str | None:
    meta = schema.metadata or {}
    value = meta.get(b"pmbook.schema_version")
    return value.decode() if value is not None else None
