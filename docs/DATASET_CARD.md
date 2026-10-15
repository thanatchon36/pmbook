# Dataset card (draft skeleton)

> **Release decision (D-004, D-019): no data is redistributed, neither raw nor derived.** The venue's Terms of Use restrict redistribution of its data, including on-chain data in raw, derived, aggregated or anonymised form. This card documents how to **rebuild** the datasets locally with `pmbook backfill`. The paper's tables and figures are the only released outputs.

## Datasets (rebuilt locally; Tier 1 unless noted)
| name | source | cadence | partitioning |
|---|---|---|---|
| fills_onchain | Polygon `OrderFilled`/`OrdersMatched`/`FeeCharged` (V1 + V2 exchanges) | daily | `dataset=fills_onchain/date=YYYY-MM-DD/` |
| tokens_onchain | exchange `TokenRegistered` | daily | … |
| conditions_onchain | CTF `ConditionPreparation`/`ConditionResolution` | daily | … |
| questions_onchain | UMA CTF adapter `QuestionInitialized`/`QuestionResolved`; NegRisk adapter `QuestionPrepared`/`MarketPrepared` | daily | … |
| category_labels | derived from question text (rule-based + LLM-assisted), validated on ≥ 300 hand labels | per release | … |
| fee_timeline | public announcements and documentation (docs/TIMELINE.md) | static | — |
| reference_binance | Binance public 1-minute klines | daily | … |
| kalshi_public (optional) | Kalshi public market data, no auth | daily | … |
| *Tier 2, only after Checkpoint R:* markets_meta, prices_history, trades_api, book_snapshots, book_deltas | venue-hosted APIs | — | — |

Every table carries a `venue` column (`"polymarket"` for now) and an embedded schema version.

## Exclusions
Markets referencing Thailand are excluded at ingestion (D-030) and appear in no table, figure or released file.

## Privacy
Wallet addresses are pseudonymised with HMAC-SHA256 and a local secret salt that is never committed (METHODS §5). Only aggregates are reported.

## Known limitations
_TBD in Phases 1–2._
