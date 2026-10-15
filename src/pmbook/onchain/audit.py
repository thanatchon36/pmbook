"""Decoding audit on sampled transactions (Phase 1 deliverable; METHODS §2.5).

For a random sample of stored transactions, re-fetch the receipt and check:

1. every venue ``OrderFilled`` in the receipt is stored, with identical decoded fields;
2. taker legs == ``OrdersMatched`` events (one taker order per match);
3. V2: the taker legs' fee total == the ``FeeCharged`` total.

Transactions touching an excluded token are skipped (they are not stored by design).
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from pmbook.onchain import contracts as c
from pmbook.onchain.decode import decode_fill
from pmbook.onchain.rpc import RpcClient

COMPARED = (
    "log_index",
    "exchange",
    "maker_id",
    "taker_id",
    "is_taker_leg",
    "side",
    "token_id",
    "collateral_amount",
    "share_amount",
    "fee",
)


@dataclass
class AuditResult:
    sampled: int = 0
    skipped_excluded: int = 0
    passed: int = 0
    failures: list[str] = field(default_factory=list)


def audit_day(
    rpc: RpcClient,
    day_dir: Path,
    pseudo: Callable[[str], str],
    excluded_tokens: set[str],
    n: int,
    seed: int = 0,
) -> AuditResult:
    parts = sorted(day_dir.glob("part-*.parquet"))
    res = AuditResult()
    if not parts:
        return res
    stored: dict[str, list[dict[str, Any]]] = {}
    for p in parts:
        for row in pq.read_table(p, columns=["tx_hash", *COMPARED]).to_pylist():
            stored.setdefault(row["tx_hash"], []).append(row)
    rng = random.Random(f"{seed}:{day_dir.name}")
    sample = rng.sample(sorted(stored), min(n, len(stored)))
    for tx in sample:
        res.sampled += 1
        receipt = rpc.call("eth_getTransactionReceipt", [tx])
        problems = check_receipt(receipt, stored[tx], pseudo, excluded_tokens)
        if problems is None:
            res.skipped_excluded += 1
        elif problems:
            res.failures += [f"{day_dir.name} {tx[:10]}…: {p}" for p in problems]
        else:
            res.passed += 1
    return res


def check_receipt(
    receipt: dict[str, Any],
    stored: list[dict[str, Any]],
    pseudo: Callable[[str], str],
    excluded_tokens: set[str],
) -> list[str] | None:
    """Problems found (empty if clean); ``None`` if the tx touches an excluded token."""
    ts = receipt.get("blockTimestamp") or "0x0"
    decoded: list[dict[str, Any]] = []
    matched = fee_charged = 0
    for lg in receipt["logs"]:
        addr = lg["address"].lower()
        if addr not in c.EXCHANGES:
            continue
        t0 = lg["topics"][0].lower()
        if t0 in (c.ORDERS_MATCHED_V1, c.ORDERS_MATCHED_V2):
            matched += 1
        elif t0 == c.FEE_CHARGED:
            fee_charged += int(lg["data"], 16)
        else:
            row = decode_fill(lg | {"blockTimestamp": ts}, pseudo)
            if row is not None:
                decoded.append(row)
    if any(r["token_id"] in excluded_tokens for r in decoded):
        return None
    problems: list[str] = []
    want = sorted((tuple(r[k] for k in COMPARED) for r in decoded), key=lambda x: x[0])
    have = sorted((tuple(r[k] for k in COMPARED) for r in stored), key=lambda x: x[0])
    if want != have:
        problems.append(f"stored legs differ from receipt ({len(have)} vs {len(decoded)})")
    takers = [r for r in decoded if r["is_taker_leg"]]
    if len(takers) != matched:
        problems.append(f"{len(takers)} taker legs vs {matched} OrdersMatched")
    if any(r["exchange"] in ("ctf_v2", "negrisk_v2", "exchange_v3") for r in decoded):
        taker_fees = sum(r["fee"] for r in takers)
        if taker_fees != fee_charged:
            problems.append(f"taker fees {taker_fees} vs FeeCharged {fee_charged}")
    return problems


def audit(
    rpc: RpcClient,
    root: Path,
    days: list[date],
    pseudo: Callable[[str], str],
    excluded_tokens: set[str],
    per_day: int,
) -> AuditResult:
    total = AuditResult()
    for d in days:
        r = audit_day(
            rpc, root / "dataset=fills_onchain" / f"date={d}", pseudo, excluded_tokens, per_day
        )
        total.sampled += r.sampled
        total.skipped_excluded += r.skipped_excluded
        total.passed += r.passed
        total.failures += r.failures
    return total
