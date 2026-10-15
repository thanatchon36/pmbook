"""Fee timeline: treatment assignment for the staggered design (MISSION §3.1, docs/TIMELINE.md).

Every row cites at least one primary source key from docs/TIMELINE.md. ``scope`` is a fee
category (labels.categories.CATEGORIES), or a narrower subset described in ``subset``. Rates
are taker rates in the V2 formula ``fee = shares x rate x p(1-p)``; for the V1 era the on-chain
encoding differs (METHODS §2.3), so the analysis uses realised on-chain fees, and these rates
only define *when* and *where* fees switched on.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

import pyarrow as pa


@dataclass(frozen=True)
class FeeEvent:
    effective: str  # ISO-8601 UTC
    scope: str
    subset: str | None
    taker_rate: float | None
    maker_rebate: float | None
    new_markets_only: bool
    sources: str
    note: str


FEE_TIMELINE: tuple[FeeEvent, ...] = (
    FeeEvent(
        "2026-01-05T00:00:00Z", "crypto", "15-minute up/down markets", None, None, False,
        "CL", "First taker fees and maker rebates (V1 encoding).",
    ),
    FeeEvent(
        "2026-02-12T00:00:00Z", "crypto", "5-minute up/down markets (launched with fees)",
        None, None, True, "CL", "New market class.",
    ),
    FeeEvent(
        "2026-02-18T00:00:00Z", "sports", "NCAAB and Serie A", 0.03, 0.25, False,
        "CL;API", "feeType sports_fees_v2.",
    ),
    FeeEvent(
        "2026-03-06T00:00:00Z", "crypto", "all crypto (1H, 4H, daily, weekly)", 0.07, 0.20, True,
        "CL;API", "Only markets created after 6 Mar.",
    ),
    *(
        FeeEvent(
            "2026-03-30T00:00:00Z", cat, None, rate, 0.20 if cat == "crypto" else 0.25, False,
            "CL;FEES;MR;API", "Fee Structure V2.",
        )
        for cat, rate in (
            ("crypto", 0.07),
            ("sports", 0.03),
            ("finance", 0.04),
            ("politics", 0.04),
            ("mentions", 0.04),
            ("tech", 0.04),
            ("economics", 0.05),
            ("culture", 0.05),
            ("weather", 0.05),
            ("other", 0.05),
            ("geopolitics", 0.0),
        )
    ),
    FeeEvent(
        "2026-03-31T00:00:00Z", "all", None, None, None, False, "CL;TX",
        "Fee-calculation fix: share-based fee = C x rate x p(1-p).",
    ),
    FeeEvent(
        "2026-04-28T11:00:00Z", "all", None, None, None, False, "CL;CON;TX",
        "CLOB V2 exchanges; open orders wiped; fees set at match time.",
    ),
    FeeEvent(
        "2026-05-28T00:00:00Z", "all", "high-volume takers", None, None, False, "TR",
        "Taker Rebate Program lowers effective taker fees.",
    ),
    FeeEvent(
        "2026-07-10T00:00:00Z", "sports", None, 0.05, 0.15, False, "CL;API",
        "feeType sports_fees_v3.",
    ),
)  # fmt: skip

SCHEMA = pa.schema(
    [
        pa.field("venue", pa.string(), nullable=False),
        pa.field("effective", pa.timestamp("s", tz="UTC"), nullable=False),
        pa.field("scope", pa.string(), nullable=False),
        pa.field("subset", pa.string()),
        pa.field("taker_rate", pa.float64()),
        pa.field("maker_rebate", pa.float64()),
        pa.field("new_markets_only", pa.bool_(), nullable=False),
        pa.field("sources", pa.string(), nullable=False),
        pa.field("note", pa.string(), nullable=False),
    ]
)


def table() -> pa.Table:
    rows: list[dict[str, Any]] = []
    for e in FEE_TIMELINE:
        d = asdict(e)
        d["effective"] = datetime.fromisoformat(d["effective"].replace("Z", "+00:00"))
        rows.append({"venue": "polymarket", **d})
    return pa.Table.from_pylist(rows, schema=SCHEMA)
