# Phase 1: on-chain backfill (Tier 1)

Goal (MISSION §8):
- fills, conditions and question text from 2025-10-01, all from chain;
- pseudonymisation;
- the home-jurisdiction filter;
- a coverage report.

Done when the coverage report exists, decoding is validated on sampled txs, `DATASET_CARD.md` is drafted and the filter tests pass.

## Census results (2026-10-15)
- 50-block samples every ~26.6 days across the window show that all venue fills come from the five known exchanges. V1 runs until 2026-04-28 and V2 after. The `ExchangeV3` exchange is small, at about 0.3 % of logs.
- Four other contracts emit the V1 topics at 2 logs per sample. They are unrelated deployments and are excluded (D-031).
- Density peaks around March 2026 at about 336 logs per block (all fill topics).
- Logs carry `blockTimestamp` on both Tenderly and QuickNode, so no block-header calls are needed.
- Token → condition: `TokenRegistered` on the V1 CTF exchange continues for V2-era markets, emitted in both token orders. The mapping is crawled from any emitter by topic.

## Design
1. **`onchain/contracts.py`:** exchange addresses and eras, plus topic0 constants computed from signatures (`eth-hash`) and tested against the hashes verified in RECON.
2. **`onchain/rpc.py`:** a JSON-RPC client.
   - POST only, with a read-only method allowlist.
   - An ordered endpoint list with failover, and back-off on 429/5xx and transport errors.
   - It detects provider result caps and raises `ResultCapExceeded`.
   - The guardrail scan permits `.post(` only in this file.
3. **`onchain/decode.py`:** pure functions from a log to a row.
   - Fill legs come from V1 and V2 `OrderFilled`, with the taker-leg flag computed before pseudonymisation.
   - Identity events: `TokenRegistered`, `ConditionPreparation`/`ConditionResolution`, UMA `QuestionInitialized`/`QuestionResolved`, and NegRisk `MarketPrepared`/`QuestionPrepared`.
4. **`onchain/pseudonym.py`:** HMAC-SHA256 with a local salt (`secrets/pseudonym.salt`, gitignored and created on first use), truncated to 16 bytes and hex encoded. Raw addresses are never written.
5. **`schema/`:** pyarrow schemas plus a version in the file metadata, and a `venue` column everywhere.
6. **`onchain/store.py`:** a Parquet writer. Raw partitions are never mutated.
   - Partitions are `dataset=<name>/date=YYYY-MM-DD/part-<first>-<last>.parquet`, written atomically (tmp file, then rename).
   - Per-day manifests record `done_through`. On resume, part files beyond `done_through` and `*.tmp` files are deleted.
7. **`onchain/backfill.py`:** the generic crawler over a `DatasetSpec` (addresses, topics, decoder, schema).
   - UTC day → block range comes from interpolation search, cached.
   - Adaptive chunking aims at about 10k logs per call and halves on the cap.
   - It stops at head minus 300 blocks for finality.
   - It runs one request in flight per endpoint. Disjoint date ranges can run in parallel processes on different endpoints.
8. **Order of the crawl:** identity datasets first (cheap), then fills. Tokens of excluded markets are dropped when fills are decoded. The exclusion is also re-applied at the first join (D-032).
9. **`filters/home_jurisdiction.py`:** a keyword and Thai-script matcher. Matches are dropped at ingestion of question rows and their ids go to the local `data/filters/` list. Manual review follows D-030.
10. **`validate/`:** a coverage report (expected and covered blocks per day per dataset, rows, gaps) plus integrity checks:
    - unique (tx, log_index);
    - exactly one taker leg per `OrdersMatched` in the audit windows;
    - V2 fee equals `FeeCharged`.
11. **CLI:** `pmbook backfill {identity,fills} --start --end [--rpc]` and `pmbook validate`.
12. **Pilot:** ±7 days around 2026-03-30, the densest period. Measure throughput and project the full crawl (D-027 threshold: 14 days).
