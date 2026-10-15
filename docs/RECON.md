# Phase 0 recon: endpoints, limits, contracts, terms

Probed 2026-10-15 with unauthenticated GETs (UA `pmbook/0.0.1 research; github.com/thanatchon36/pmbook`), sent sequentially with ≥ 0.5 s spacing. Probe scripts: `scripts/recon/`.

## 1. Polymarket REST APIs

Documented limits are IP-based Cloudflare throttles: requests over the limit are delayed or queued, not rejected ([Rate Limits](https://docs.polymarket.com/api-reference/rate-limits.md)). pmbook stays well below them.

| API | Endpoint used | Documented limit | Probe result |
|---|---|---|---|
| Gamma | `GET /markets/keyset?limit≤100&closed=…&after_cursor=…` | `/markets` 300 req/10 s; listing 900/10 s | 200. `{markets, next_cursor}`. `closed` defaults to `false` (since 2026-04-09); pass `closed=true` for resolved markets. `include_tag=true` adds tags. Offset paging is deprecated |
| Gamma | `GET /events/keyset` | `/events` 500/10 s | (same shape as markets) |
| CLOB | `GET /book?token_id=` | 1,500/10 s | 200. `{market, asset_id, timestamp(ms), hash, bids[], asks[], min_order_size, tick_size, neg_risk, last_trade_price}`. **No sequence number** |
| CLOB | `GET /books` (batch) | 500/10 s | — |
| CLOB | `GET /clob-markets/{condition_id}` | general 9,000/10 s | 200. Compact: `r{mi=min_size, ma=max_spread, moas}`, `fd{r=rate, e=exponent, to=takerOnly}`, `mts` (tick), `v` (version) |
| CLOB | `GET /rewards/markets/current` | general | 200. `rewards_config[{rate_per_day, start_date, end_date, asset_address}]`, `rewards_max_spread`, `rewards_min_size`, `native_daily_rate`, `total_daily_rate`. Cursor paged |
| CLOB | `GET /prices-history?market=<token>&startTs&endTs&fidelity=1` | 1,000/10 s | 200. **1-minute history available back to 2025-10-01** (1,440 points/day tested) |
| Data API v2 | `GET /v2/prices-history?token_id=&start&end&bucket_seconds≥60` | 200/10 s | 200, but **empty for 2025-10-01** on a market that has CLOB history. Use the CLOB route for the backfill; re-test later |
| Data API v2 | `GET /v2/trades?condition=&taker_only=false&cursor=` | 300/10 s | 200. Keyset cursor with no depth limit. `taker_only=false` adds **maker rows** (one per leg). Fields: wallet, side, token, size, price, timestamp, tx hash. **No fee, no log index** |
| Data API v1 | `GET /trades?market=` | 200/10 s | 200. `limit ≤ 500`, `offset ≤ 1,000` (frozen legacy) |
| Data API v2 | `GET /v2/tokens?token_id=` | general 800/10 s | 200. token → condition, module (`v1_ctf`/v2), slug, neg_risk |

**Gamma market fields relevant to the study:** `conditionId`, `clobTokenIds` (JSON string), `positionIds` (v2), `version` (`v1` = CTF, `v2` = PositionManager), `negRisk`, `feesEnabled`, `feeType` (e.g. `sports_fees_v2`, `sports_fees_v3`, `crypto_fees_v2`, `politics_fees`), `feeSchedule{rate, exponent, takerOnly, rebateRate}`, `makerBaseFee`/`takerBaseFee` (legacy bps, 1000), `rewardsMinSize`, `rewardsMaxSpread`, `orderPriceMinTickSize`, `orderMinSize`, `createdAt`, `startDate`, `endDate`, `closed`, `umaResolutionStatus`, `volume*`, `liquidity*`, `events[]`, and `tags[]` with `include_tag`. **Fee fields reflect current state only.** In a sample of 600 closed high-volume markets, 412 had `feesEnabled=false`/`null` and the rest carried their category's current feeType.

## 2. WebSocket (market channel)

AsyncAPI spec: https://docs.polymarket.com/asyncapi.json. Server: `wss://ws-subscriptions-clob.polymarket.com/ws/market`.

- **Subscribe:** `{"type":"market","assets_ids":[…],"initial_dump":true,"level":2,"custom_feature_enabled":true}`. **Update:** `{"operation":"subscribe"|"unsubscribe","assets_ids":[…]}`, no reconnect needed.
- **Heartbeat:** client sends text `PING` every 10 s; server replies `PONG`.
- **Events:** `book` (full snapshot, `hash`, `timestamp` ms), `price_change` (level deltas `{asset_id, price, size (new aggregate; 0 = level removed), side, hash (order hash), best_bid, best_ask}`), `last_trade_price` (`price, size, side` (taker), `fee_rate_bps`, `transaction_hash`), `tick_size_change`, plus `best_bid_ask`, `new_market` and `market_resolved` with custom features.
- **Subscription limit:** the 100-token cap was removed on 2025-05-28 [CL]. No per-connection cap is documented. pmbook will still shard subscriptions (≤ 500 assets per connection; DECISIONS D-011).
- **Integrity:** there is **no sequence number** on the market channel, so gap detection cannot be sequence-based. The plan is periodic REST `/book` snapshots compared against the locally built book (level-by-level diff, plus the server `hash` where reproducible), and forced resync on mismatch, reconnect, or silence > N s. Details in Phase 1.

## 3. Contracts (Polygon, chain id 137)

| Era | Contract | Address | Source |
|---|---|---|---|
| ≤ 2026-04-28 | CTF Exchange (V1) | `0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E` | Polymarket/ctf-exchange README; py-clob-client `config.py` |
| ≤ 2026-04-28 | NegRisk CTF Exchange (V1) | `0xC5d563A36AE78145C45a50134d48A1215220f80a` | py-clob-client `config.py` |
| ≥ 2026-04-28 | CTF Exchange V2 | `0xE111180000d2663C0091e4f400237545B87B996B` | [CON]; Polymarket/ctf-exchange-v2 README |
| ≥ 2026-04-28 | NegRisk CTF Exchange V2 | `0xe2222d279d744050d28e00520010520000310F59` | [CON]; ctf-exchange-v2 README |
| 2026 (v2 position system) | Polymarket Protocol V2 Exchange (`ExchangeV3`) | `0xe3333700cA9d93003F00f0F71f8515005F6c00Aa` | [CON] |
| all | Conditional Tokens | `0x4D97DCd97eC945f40cF65F87097ACe5EA0476045` | [CON] |
| ≤ 2026-04-28 collateral | USDC.e | `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174` | py-clob-client |
| ≥ 2026-04-28 collateral | pUSD | `0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB` | [CON] |

Event topics (keccak of signature) are confirmed by matching live logs:

| Event | Signature | topic0 |
|---|---|---|
| V1 OrderFilled | `OrderFilled(bytes32,address,address,uint256,uint256,uint256,uint256,uint256)` | `0xd0a08e8c…c0f6` |
| V1 OrdersMatched | `OrdersMatched(bytes32,address,uint256,uint256,uint256,uint256)` | `0x63bf4d16…956c` |
| V2 OrderFilled | `OrderFilled(bytes32,address,address,uint8,uint256,uint256,uint256,uint256,bytes32,bytes32)` | `0xd543adfd…d8ee` |
| V2 OrdersMatched | `OrdersMatched(bytes32,address,uint8,uint256,uint256,uint256)` | `0x174b3811…ab7c` |
| V2 FeeCharged | `FeeCharged(address,uint256)` | `0x55bb3cad…0ab1` |

The `ExchangeV3` contract emits the V2 `OrderFilled` topic: it appears in the 2026-07-10 and 2026-10-14 samples, with 17–28 logs per 100 blocks.

## 4. Polygon RPC and backfill feasibility

| Endpoint (keyless) | `eth_blockNumber` | Archive `eth_getLogs` (2025-10) |
|---|---|---|
| `polygon-rpc.com` | 403 "tenant disabled" | — |
| `polygon-bor-rpc.publicnode.com` | OK | **403: archive needs a personal token** |
| `polygon.drpc.org` | OK | **OK for ≤ 100-block ranges.** 200+ blocks → HTTP 400 "ranges over 10000 blocks are not supported on free plan" (message inaccurate; the observed limit is between 100 and 200) |
| `1rpc.io/matic` | OK | not tested |
| `rpc.ankr.com/polygon` | requires API key | — |

Date → block map (binary search on block timestamps): 2025-10-01 = 77,106,032; 2026-01-05 = 81,225,971; 2026-02-18 = 83,126,389; 2026-03-30 = 84,854,382; 2026-04-28 = 86,107,178; 2026-07-10 = 89,957,737; 2026-10-15 = 95,544,717.

**Log volume** (`OrderFilled`, all five exchanges, one 100-block window per date):

| Date | Logs / 100 blocks |
|---|---|
| 2025-10-01 | 2,111 |
| 2026-01-05 | 14,477 |
| 2026-03-30 | 25,910 |
| 2026-04-29 | 15,259 |
| 2026-07-10 | 10,621 |
| 2026-10-14 | 6,058 |

Window 2025-10-01 → 2026-10-15 ≈ **18.4 M blocks → ≥ 184 k requests** at 100 blocks each, and on the order of **1–2.5 billion `OrderFilled` logs**. That is roughly 1–2 TB of JSON transfer and ~100–250 GB as Parquet. A large share comes from short-duration crypto up/down markets, which §4 excludes, but `tokenId` is not an indexed topic, so they cannot be filtered server-side. This exceeds what a keyless public endpoint can reasonably be asked to serve. It triggers **Checkpoint D** (see DECISIONS D-012).

## 5. Reference data

- Binance public klines: `https://api.binance.com/api/v3/klines` and the market-data-only mirror `https://data-api.binance.vision/api/v3/klines` both return 1-minute BTCUSDT for 2025-10-01, no key. pmbook uses the `data-api.binance.vision` mirror.
- Kalshi: `https://api.elections.kalshi.com/trade-api/v2/markets` answers without authentication. It is optional (RQ5 cross-venue); see D-010.

## 6. Terms of Use (summary; decision in DECISIONS D-004)

Polymarket.com Terms of Use, **effective 11 Aug 2026**, served as a Google Doc embedded at https://polymarket.com/tos. Relevant clauses (§4 prohibited uses, §5 IP):

- No "data mining tools, robots, crawlers, or similar data gathering and extraction tools to scrape or otherwise remove data from the Site, any other Interface, or Features". pmbook does no HTML scraping. It uses the documented public APIs, which Polymarket publishes "for builders, researchers, and analysts" (docs "Data Resources").
- No access to or use of "Data" (any data "directly or through an API, or any other means, including on-chain, whether in raw, derived, aggregated, or anonymized form") by **Capital Market Clients** or market-data distributors, absent written agreement.
- No "sell, resell, sublicense, redistribute, or otherwise commercially exploit the Data to any Capital Market Client or market data distributor".
- The site licence is personal, limited, non-sublicensable and non-transferable.
- Trading is not permitted for Restricted Persons (list includes the US, the UK, Thailand and others). Content Features remain usable everywhere. pmbook never trades.

robots.txt: `polymarket.com` allows all (`Disallow:` empty). The API hosts have no robots.txt (404).
