"""Fee-rate silver labels: the venue's own category assignment, revealed by on-chain fees.

Under Fee Structure V2 each category group has its own taker rate (docs/TIMELINE.md), so the
implied rate of a market's taker fills identifies its group:

    r07 crypto · r03 sports · r04 finance/politics/mentions/tech
    r05 economics/culture/weather/other · r00 geopolitics (or fees disabled)

Only legs in the window ``SILVER_START``..``SILVER_END`` are used: before the 31 Mar fix the
V1 encoding is a flat base rate in every treated category, and from 10 Jul sports moves to
0.05, colliding with r05. Implied rate per taker leg (METHODS §2.3):

* V2 exchanges: ``fee / (shares x p(1-p))`` (fee in collateral);
* V1 exchanges: the fee is in the received asset; it is converted to collateral at the leg
  price first. The V1 post-fix formula is established empirically (D-041).
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pyarrow as pa

SILVER_START = "2026-03-31"
SILVER_END = "2026-07-09"
GROUP_RATES = {"r03": 0.03, "r04": 0.04, "r05": 0.05, "r07": 0.07}
TOLERANCE = 0.004
MIN_LEGS = 5  # fee-bearing (or fee-free) taker legs at 0.1 ≤ p ≤ 0.9 needed for a label
MIN_AGREEMENT = 0.9


def silver_labels(root: Path, markets: pa.Table) -> pa.Table:
    """One row per condition with a fee-rate group, or none if the evidence is too thin."""
    con = duckdb.connect()
    con.execute("set TimeZone = 'UTC'")
    con.register("markets", markets)
    glob = (root / "dataset=fills_onchain").as_posix() + "/*/*.parquet"
    rates = ", ".join(f"('{g}', {r})" for g, r in GROUP_RATES.items())
    sql = f"""
    with legs as (
        select f.token_id, f.price p, f.share_amount s,
               case when f.fee_asset = 'shares' then f.fee * f.price else f.fee end fee_c
        from read_parquet('{glob}', hive_partitioning = true) f
        where f.is_taker_leg and f.date between '{SILVER_START}' and '{SILVER_END}'
          and f.price between 0.1 and 0.9 and f.share_amount >= 1000000
    ),
    tok as (
        select condition_id, token0 token_id from markets
        union all select condition_id, token1 from markets
    ),
    r as (
        select tok.condition_id, legs.fee_c / (legs.s * legs.p * (1 - legs.p)) rate
        from legs join tok using (token_id)
    ),
    g as (select * from (values {rates}) v(grp, grate)),
    nearest as (
        select r.condition_id, r.rate,
               case when r.rate = 0 then 'r00'
                    else (select grp from g where abs(g.grate - r.rate) <= {TOLERANCE}
                          order by abs(g.grate - r.rate) limit 1) end grp
        from r
    ),
    top as (select condition_id, mode(grp) top_grp from nearest group by 1),
    per as (
        select condition_id, count(*) n_legs, any_value(top_grp) grp,
               avg(coalesce(grp = top_grp, false)::int) agreement, median(rate) median_rate
        from nearest join top using (condition_id) group by 1
    )
    select 'polymarket' venue, condition_id, n_legs, median_rate, agreement,
           case when n_legs >= {MIN_LEGS} and agreement >= {MIN_AGREEMENT} then grp end silver_group
    from per order by condition_id
    """
    return con.sql(sql).to_arrow_table()
