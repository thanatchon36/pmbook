"""Market identity table: one row per venue condition, with its question text (METHODS §1.3).

A *venue condition* is one whose outcome tokens are registered on a venue exchange
(``tokens_onchain``, venue emitters only; D-038). Text comes from three paths:

* UMA adapters: ``QuestionInitialized`` from the condition's oracle, keyed by question id;
* NegRisk adapter: ``QuestionPrepared`` (the outcome question) plus ``MarketPrepared`` (the
  event title), keyed by question id and market id;
* none: the short-duration crypto resolver (``SHORT_CRYPTO_ORACLES``) prepares conditions
  through an ERC-4337 entry point and publishes no text (D-039).

Only the title and the description are kept. The rest of the ancillary data (resolution
payout map, initializer address) is dropped here.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pyarrow as pa

from pmbook.onchain import contracts as c

SHORT_CRYPTO_ORACLES = ("0x58e1745bedda7312c4cddb72618923da1b90efde",)

# Ancillary text is mostly "q: title: T, description: D[, market_id: …][ res_data: …]"
# followed by ",initializer: …"
# (UMA) or "question: T, description: D, id: N" / "title: T, description: D, id: N" (NegRisk).
_TITLE = r"^\s*(?:q: )?(?:title|question): (.*?), description: "
_DESC = r", description: (.*?)(?:,? ?market_id: |\s*res_data: |,\s*initializer:|, id: \d+\s*$|$)"
DESC_CHARS = 1500


def _field(col: str, key: str, pattern: str) -> str:
    """SQL for one text field; some 2025 ancillary data is JSON (``{"title": …}``)."""
    js = f"coalesce(json_extract_string({col}, '$.{key}'), json_extract_string({col}, '$.q.{key}'))"
    rx = f"regexp_extract({col}, '{pattern}', 1, 's')"
    return f"nullif(trim(case when json_valid({col}) then {js} else {rx} end), '')"


def _glob(root: Path, ds: str) -> str:
    return (root / f"dataset={ds}").as_posix() + "/*/*.parquet"


def build_markets(root: Path) -> pa.Table:
    """Join tokens → conditions → question text; deterministic order by condition id."""
    con = duckdb.connect()
    con.execute("set TimeZone = 'UTC'")
    short = ", ".join(f"'{o}'" for o in SHORT_CRYPTO_ORACLES)
    sql = f"""
    with tok as (
        select condition_id, any_value(token0) token0, any_value(token1) token1,
               min(block_ts) registered_ts
        from read_parquet('{_glob(root, "tokens_onchain")}') group by 1
    ),
    prep as (
        select condition_id, arg_min(oracle, block_ts) oracle,
               arg_min(question_id, block_ts) question_id,
               arg_min(outcome_slot_count, block_ts) outcome_slot_count, min(block_ts) created_ts
        from read_parquet('{_glob(root, "conditions_onchain")}')
        where event = 'preparation' group by 1
    ),
    res as (
        select condition_id, min(block_ts) resolved_ts, arg_min(payouts, block_ts) payouts
        from read_parquet('{_glob(root, "conditions_onchain")}')
        where event = 'resolution' group by 1
    ),
    q as (select * from read_parquet('{_glob(root, "questions_onchain")}') where text is not null),
    uma as (
        select emitter, question_id, arg_min(text, block_ts) txt
        from q where event = 'uma_initialized' group by 1, 2
    ),
    nrq as (
        select question_id, arg_min(market_id, block_ts) market_id, arg_min(text, block_ts) txt
        from q where event = 'negrisk_question' group by 1
    ),
    nrm as (
        select market_id, arg_min(text, block_ts) txt
        from q where event = 'negrisk_market' group by 1
    ),
    joined as (
        select tok.condition_id, prep.oracle, prep.question_id, prep.outcome_slot_count,
               coalesce(prep.created_ts, tok.registered_ts) created_ts, res.resolved_ts,
               res.payouts, tok.token0, tok.token1,
               prep.oracle = '{c.NEG_RISK_ADAPTER}' neg_risk,
               nrq.market_id neg_risk_market_id,
               coalesce(uma.txt, nrq.txt) qtext, nrm.txt etext,
               case when uma.txt is not null then 'uma'
                    when nrq.txt is not null then 'negrisk'
                    when prep.oracle in ({short}) then 'short_crypto_resolver'
                    when prep.oracle is null then 'no_preparation'
                    else 'none' end text_source
        from tok
        left join prep using (condition_id)
        left join res using (condition_id)
        left join uma on uma.emitter = prep.oracle and uma.question_id = prep.question_id
        left join nrq on prep.oracle = '{c.NEG_RISK_ADAPTER}'
                     and nrq.question_id = prep.question_id
        left join nrm on nrm.market_id = nrq.market_id
    )
    select 'polymarket' venue, condition_id, oracle, question_id, outcome_slot_count,
           created_ts, resolved_ts, payouts, token0, token1, neg_risk, neg_risk_market_id,
           text_source,
           {_field("qtext", "title", _TITLE)} title,
           left({_field("qtext", "description", _DESC)}, {DESC_CHARS}) description,
           {_field("etext", "title", _TITLE)} event_title
    from joined order by condition_id
    """
    return con.sql(sql).to_arrow_table()
