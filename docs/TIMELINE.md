# Institutional timeline: Polymarket fees, rebates, rewards and concurrent changes

All dates are UTC unless stated. "Accessed" = 2026-10-15 for every source below. The MISSION §2 claims were treated as hypotheses. The last column says whether each one was verified.

**Primary sources.** These are Polymarket-operated: the predictions changelog [CL], the docs pages [FEES], [MR], [TR], [LR], [MD] and [CON], the Gamma/CLOB public APIs [API], and Polygon on-chain transactions [TX].

| Date | Change | Rates / parameters | Source | Status vs MISSION |
|---|---|---|---|---|
| 2025-09-15 23:00 | WS `price_change` message structure changed | — | [CL] "September 15, 2025" | Pre-window; affects only the recorder parser |
| 2025-10-01 | Backfill window start (MISSION §3.2). Polygon block 77,106,032 | — | [TX] block-timestamp search | — |
| **2026-01-05** | **First taker fees + maker rebates, on 15-minute crypto up/down markets only**. Rebates paid daily | Fee peaks at 1.56 % at p = 0.5 (V1 formula, see METHODS) | [CL] "Jan 5, 2026 — Taker Fees & Maker Rebates" | **Differs:** the MISSION says "crypto markets (January 2026)". Only short-duration crypto up/down markets were treated, and §4 excludes that class anyway |
| 2026-02-11 (announced) → **2026-02-18** | Taker fees + maker rebates on **NCAAB and Serie A** markets. Rebates computed per market | Sports rate 0.03, rebate 25 % (feeType `sports_fees_v2`) | [CL] "Feb 11, 2026 — Taker Fees & Maker Rebates: NCAAB and Serie A"; [API] `feeType=sports_fees_v2` | **Differs:** the MISSION says "sports (18 Feb 2026)". Only two leagues were treated on that date |
| 2026-02-12 | 5-minute crypto markets launched with taker fees | Same curve as 15-min | [CL] "Feb 12, 2026" | Excluded class |
| 2026-03-01 (announced) → **2026-03-06** | Taker fees extended to **all crypto** markets (1H, 4H, daily, weekly), **only markets created after 6 Mar** | Crypto rate 0.07, rebate 20 % (`crypto_fees_v2`) | [CL] "Mar 1, 2026 — All Crypto Markets"; [API] | Partly matches (crypto) |
| **2026-03-30** | **Fee Structure V2**: fees in Crypto, Sports, Finance, Politics, Economics, Culture, Weather, Tech, Mentions, Other. **Geopolitics / world events fee-free** | Taker rate: Crypto 0.07; Sports 0.03 (until 10 Jul); Finance, Politics, Mentions, Tech 0.04; Economics, Culture, Weather, Other 0.05; Geopolitics 0. Maker rebate 20 % (crypto), 25 % (others). Makers pay 0 | [CL] "Mar 30, 2026 — Fee Structure V2"; [FEES]; [MR]; [API] feeTypes `politics_fees`, `economics_fees`, `finance_prices_fees`, `mentions_fees` | **Verified** (date, categories, geopolitics exemption) |
| **2026-03-31** | Fee-calculation fix: fees computed from the market's `feeSchedule` on a share basis. The 30 Mar implementation produced very high fees on low-priced trades | `fee = C × rate × p × (1 − p)` (exponent 1) | [CL] "Mar 31, 2026 — REST API Fee Fields Update". Secondary: PokerNews, 2026-04-01 (no verbatim Polymarket statement). [TX] 0xb65e… (30 Mar) shows the pre-fix V1 formula | **Differs:** the MISSION says "April 2026 fee-formula correction". The fix dates to 31 Mar |
| **2026-04-28 ~11:00** | **CLOB V2 / new exchange contracts / pUSD collateral**. ~1 h trading halt; **all open orders wiped**; fees set at match time (no `feeRateBps` in orders); new event ABI (`OrderFilled` with `side`, `tokenId`, `builder`, `metadata`; new `FeeCharged`) | CTF Exchange V2 `0xE111…996B`, NegRisk CTF Exchange V2 `0xe222…0F59` | [CL] "Apr 17, 2026" and "Apr 28, 2026"; [CON]; [TX] | **New confound**, not in MISSION. Platform-wide, 4 weeks after the main treatment |
| 2026-03-17 | March Madness liquidity rewards: $2M+ across live and pregame markets | Per-market daily rates (e.g. $60k/day full-game ML in-game) | [CL] "Mar 17, 2026" | Reward-budget change (MISSION §4 threat) |
| **2026-05-28** | **Taker Rebate Program** (tiered rebates to takers by weighted volume) | wV = size × (1 − p) × category weight | [TR] | **New confound**: lowers the effective taker fee for high-volume takers |
| **2026-07-10** (effective "at midnight UTC") | **Sports fee rate 0.03 → 0.05**; sports maker rebate 25 % → 15 % (`sports_fees_v3`) | — | [CL] "Jul 10, 2026 — Sports taker fee and maker rebate update"; [API] `sports_fees_v3` | **New dose change**: a second within-category treatment |
| 2026-07-02 | World Cup markets decimalised to 0.0025 tick | — | [CL] | Tick-size confound (sports, World Cup only) |
| 2026-08-07 / 08-14 | Crypto up/down markets resolve on Chainlink TWAP (30 s, then 60 s for 5-min markets) | — | [CL] | Excluded class |
| 2026-08 | $1M crypto TWAP liquidity rewards (5m/15m/4h crypto) | — | [LR] | Excluded class |
| 2026-08-17, 2026-09-04 | Crypto taker delay 250 → 50 ms, then 50 → 150 ms | — | [CL] | Excluded class (mostly) |
| 2026-09-04 | Data API v2; `prices-history` moves to the data host (min bucket 60 s) | — | [CL] | Data-source change |

## Liquidity Rewards (MISSION §2 claim)

Verified. Makers earn daily rewards for resting orders inside a per-market `max_spread` (cents from the size-cutoff-adjusted mid) with size ≥ `min_size`. Orders must rest ≥ 3.5 s, two-sided quoting is boosted, the scaling factor c = 3.0, and the minimum payout is $1. Per-market parameters are exposed in Gamma (`rewardsMinSize`, `rewardsMaxSpread`) and CLOB `/rewards/markets/current` (`rewards_max_spread`, `rewards_min_size`, `rewards_config[].rate_per_day`, `native_daily_rate`, `total_daily_rate`). Sources: [LR], [API].

## Fee mechanics: claims vs evidence

- **Formula** `fee = C × rate × p(1−p)`: verified **exactly** on-chain for the V2 exchange (tx 0x1fd6…1111, 2026-10-14: 100 shares × 0.07 × 0.37 × 0.63 = 1.6317 pUSD, matching both the `OrderFilled.fee` and `FeeCharged` fields). The V1 exchange (≤ 2026-04-28) used a different on-chain formula; see METHODS §2.
- **Makers pay zero**: holds on the V2 exchange (maker legs have `fee = 0`). On the V1 exchange, tx 0xb65e… (2026-03-30) has a **non-zero `fee` on a maker leg**. Phase 2 must characterise this before RQ3/RQ1 use the claim.
- **Fee parameters per market** (`feesEnabled`, `feeSchedule{rate, exponent, takerOnly, rebateRate}`, `feeType`): present in Gamma, but they show **current state only**. A market resolved before fees shows `null`. Historical fee status must come from on-chain `fee` fields.

## Sources

- [CL] Predictions changelog, https://docs.polymarket.com/changelog/predictions.md
- [FEES] Trading fees, https://docs.polymarket.com/trading/fees.md
- [MR] Maker Rebates Program, https://docs.polymarket.com/programs/maker-rebates.md
- [TR] Taker Rebate Program, https://docs.polymarket.com/programs/taker-rebates.md
- [LR] Liquidity Rewards, https://docs.polymarket.com/programs/liquidity-rewards.md
- [MD] Market details (fee schedule fields), https://docs.polymarket.com/market-data/market-details.md
- [CON] Contracts, https://docs.polymarket.com/resources/contracts.md
- [API] Live probes of `gamma-api.polymarket.com/markets/keyset` and `clob.polymarket.com/clob-markets/{cid}`, 2026-10-15 (see RECON.md)
- [TX] Polygon transactions decoded in METHODS §2
- Secondary (context only): PokerNews, "Polymarket blunder prompts quick U-turn on new fees", 2026-04-01, https://www.pokernews.com/prediction-markets/news/2026/04/polymarket-blunder-prompts-quick-u-turn-new-polymarket-fees-50947.htm
