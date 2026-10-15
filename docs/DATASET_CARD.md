# Dataset card (draft skeleton)

> **Release decision (D-004): no raw Polymarket data is redistributed.** Polymarket's Terms of Use restrict redistribution of its data, including on-chain data in raw, derived, aggregated or anonymised form. This card documents how to **rebuild** the dataset locally with `pmbook record` / `pmbook backfill`. Whether the derived panel can be released is pending Checkpoint C.

## Datasets (rebuilt locally)
| name | source | cadence | partitioning |
|---|---|---|---|
| markets | Gamma API | hourly | `dataset=markets/date=YYYY-MM-DD/` |
| book_snapshots | CLOB `/book` | 5 min | … |
| book_deltas | CLOB WS market channel | streaming | … |
| fills_onchain | Polygon `OrderFilled` | daily | … |
| trades_api | Data API v2 | daily | … |
| prices_history | CLOB `/prices-history` | daily | … |
| reference_binance | Binance public klines | daily | … |

## Privacy
Wallet addresses pseudonymised with HMAC-SHA256 and a local secret salt (METHODS §5).

## Known limitations
_TBD in Phase 2._
