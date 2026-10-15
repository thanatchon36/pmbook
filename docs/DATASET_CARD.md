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

## Rebuilding

```bash
uv run pmbook backfill identity   # 2022-09-26 → yesterday, strictly in time order (filter runs here)
uv run pmbook backfill fills      # 2025-10-01 → yesterday; each day waits for identity
uv run pmbook backfill binance    # 2025-10-01 → yesterday
uv run pmbook validate --audit-per-day 20
```

All sources are keyless and public: Polygon logs via general-purpose public RPC (RECON §4b) and the Binance public market-data mirror. No venue-hosted endpoint is used (Checkpoint R is deferred).

## Known limitations
- Question text exists on chain only for UMA- and NegRisk-adapter markets. Conditions without on-chain text are held back from the panel (D-030); `pmbook validate` reports the share.
- Fills are legs of `OrderFilled`. Matches spanning maker legs on complementary tokens need the mapping `p' = 1 − p` (METHODS §2.2) at panel time.
- V1-era fees (until 2026-04-28) are denominated in the received asset and follow a different formula before 2026-03-31 (METHODS §2.3).
- No order-book data (Tier 2). Spreads are estimated from trades (METHODS §4).
