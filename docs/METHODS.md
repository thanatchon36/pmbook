# Methods

> Status: §2 (fill decoding) drafted in Phase 0 from decoded real transactions. The other sections are filled in Phases 1–3.

## 1. Data sources and coverage

Tier 1 only (D-026). Fills come from a full `eth_getLogs` crawl of the exchange contracts over keyless public RPC (RECON §4b). Market identity and question text come from on-chain `TokenRegistered`, CTF and UMA adapter events (RECON §7). Coverage reports: Phase 1.

### 1.3 Market identity

One row per *venue condition*, meaning a condition whose outcome tokens are registered on a venue exchange (D-038). Its question text is found by one of three paths:

- **UMA path:** the condition's oracle is a UMA adapter. Text comes from the adapter's `QuestionInitialized` (question id match, same emitter).
- **NegRisk path:** the oracle is the NegRisk adapter. The outcome question comes from `QuestionPrepared` and the event title from `MarketPrepared`.
- **No text:** the short-crypto resolver (D-039).

From the ancillary data only `title`, `description` (truncated to 1,500 characters) and the event title are kept. The resolution payout map and the initializer address are dropped. Most ancillary data is `key: value` text; some 2025 NegRisk data is JSON, and both forms are parsed. Code: `pmbook.labels.markets`.

### 1.4 Category labels and their validation

**Classifier.** `pmbook.labels.categories` maps each market's title (and event title; the description is a tie-breaker) to one of the eleven Fee Structure V2 categories. It uses ordered regular-expression rules: the first match wins and the rule name is stored. Short-window crypto up/down markets are flagged `short_crypto` and handled separately in the analysis (MISSION §3.3).

**Two validation sources:**

1. **Fee-rate silver labels** (`pmbook.labels.feerates`) are the venue's own assignment, revealed by on-chain fees. The implied taker rate `fee / (shares × p(1−p))` of each market's taker legs at 0.1 ≤ p ≤ 0.9, between 2026-03-31 and 2026-07-09, is mapped to the nearest rate group (r00/r03/r04/r05/r07; ±0.004). A label is assigned with ≥ 5 legs and ≥ 90 % agreement. Silver labels identify rate groups, not categories: r04 and r05 each pool four categories, and r00 pools geopolitics with fee-disabled markets. Before 31 Mar the V1 encoding charges a flat `0.10 × min(p, 1−p) × shares` in every treated category (verified on 2026-03-23, D-041), so pre-fix fees reveal only *whether* a market was treated.
2. **Hand-labelled sample:** 300 markets, stratified by predicted category (floor 15 per category), drawn from markets created since 2025-10-01 that have question text (seed 20261015). **The annotator is an AI model (Claude Opus 5.5), not the author.** It labelled from the titles alone, without seeing the predictions. Eight items are flagged as ambiguous between two categories (D-042).

**Protocol.** Rule set v1 was frozen before the hand labels were compared with it. The 300-item sample is a held-out test set. Later rule changes are developed on a separate dev sample and on the silver labels, and are re-tested on a fresh held-out sample. Accuracy, per-class precision and recall, and confusion matrices are produced by `pmbook labels evaluate`. The analysis re-runs on the high-confidence subsample (markets whose rule label agrees with the silver group), as MISSION §4 requires.

## 2. Decoding exchange fills from Polygon logs

### 2.1 Event shapes

**V1 exchanges** (CTF Exchange `0x4bFb…982E` and NegRisk CTF Exchange `0xC5d5…f80a`; active until 2026-04-28):

```
OrderFilled(bytes32 indexed orderHash, address indexed maker, address indexed taker,
            uint256 makerAssetId, uint256 takerAssetId,
            uint256 makerAmountFilled, uint256 takerAmountFilled, uint256 fee)
OrdersMatched(bytes32 indexed takerOrderHash, address indexed takerOrderMaker,
              uint256 makerAssetId, uint256 takerAssetId,
              uint256 makerAmountFilled, uint256 takerAmountFilled)
```

Asset id `0` = collateral (USDC.e). The order's maker **gives** `makerAssetId` and **receives** `takerAssetId`. So `makerAssetId == 0` means the order is a BUY of outcome token `takerAssetId`, otherwise a SELL of `makerAssetId`. Amounts use 6 decimals for both collateral and outcome tokens.

**V2 exchanges** (CTF Exchange V2 `0xE111…996B`, NegRisk CTF Exchange V2 `0xe222…0F59`, Protocol V2 Exchange `0xe333…00Aa`; from 2026-04-28):

```
OrderFilled(bytes32 indexed orderHash, address indexed maker, address indexed taker,
            uint8 side, uint256 tokenId, uint256 makerAmountFilled,
            uint256 takerAmountFilled, uint256 fee, bytes32 builder, bytes32 metadata)
OrdersMatched(bytes32 indexed takerOrderHash, address indexed takerOrderMaker,
              uint8 side, uint256 tokenId, uint256 makerAmountFilled, uint256 takerAmountFilled)
FeeCharged(address indexed receiver, uint256 amount)
```

`side`: 0 = BUY, 1 = SELL. For a BUY, `makerAmountFilled` is collateral (pUSD) paid and `takerAmountFilled` is shares received. For a SELL, the reverse. Source: `Polymarket/ctf-exchange-v2` `src/exchange/mixins/Events.sol`.

### 2.2 Legs and roles (verified on real transactions)

One `matchOrders` transaction emits:

1. one `OrderFilled` per **maker order** filled. In it, `maker` = the resting order's signer/funder and `taker` = **the taker order's wallet**;
2. one `OrderFilled` for the **taker order**. In it, `maker` = the taker's wallet and `taker` = **the exchange contract address**;
3. one `OrdersMatched` with `takerOrderMaker` = the taker's wallet. On V2 it is preceded by `FeeCharged` when a fee is due.

Rules derived from this:

- **Taker leg:** the `OrderFilled` whose `taker` equals the emitting exchange's address. Its `maker` field is the **taker wallet**, and its side/price are the **taker's side and price**.
- **Maker legs:** all other `OrderFilled` logs in the transaction. Each one's `maker` field is a **maker wallet**.
- **Price** of a leg = collateral amount / share amount.
- **Complementary ("mint/merge") matches:** a maker leg may trade the *complementary* token. For example, the taker BUYs Up at 0.37 against makers BUYing Down at 0.63 (tx 0x1fd6…1111). Maker legs are mapped onto the taker's token via `p' = 1 − p` with the side flipped. Notional is measured on the taker leg.
- **Taker notional** (used for volume) = collateral amount on the taker leg. Share volume = shares on the taker leg.
- **Fee:**
  - *V2:* the taker leg carries `fee` (collateral units, 6 dp), equal to the `FeeCharged.amount` that precedes it. Maker legs carry `fee = 0`.
  - *V1:* `fee` is denominated in the asset the order **receives** (shares for a BUY, collateral for a SELL). It can be non-zero on **maker** legs (tx 0xb65e…, 2026-03-30). Phase 2 converts V1 fees to collateral at the leg price and reports maker-leg fees separately.

### 2.3 Fee formula checks

- **V2 (post 2026-04-28):** `fee = C × rate × p × (1 − p)` with `C` = taker shares, `p` = taker price and `rate` = `feeSchedule.rate`. Exact match on tx `0x1fd6d227…1111` (BTC up/down 5-min, 2026-10-14): 100 × 0.07 × 0.37 × 0.63 = 1.6317 = on-chain `fee` = `FeeCharged.amount`. On tx `0xfd906055…19ea` (ETH up/down 5-min, 2026-04-29), the implied rate is 0.072. This is probably a transitional parameter; Phase 2 investigates it.
- **V1 (30 Mar 2026, before the 31 Mar fix):** tx `0xb65e8b20…afaff` (BTC up/down 5-min). The fees match `fee = r × min(p, 1−p) × shares / p` for BUYs, in shares, with r = 0.10 (`takerBaseFee` = 1000 bps). Taker leg: 1.0101 shares at 0.99 gives fee 0.00102 shares. Maker leg: 1.0101 shares at 0.01 gives fee 0.10101 shares, i.e. 10 % of the shares received. This explains the "very high fees on low-priced trades" fixed on 31 Mar. **Implication:** fee intensity in the V1 era is not ∝ p(1−p). RQ1(b) must use the realised on-chain fee ratio, not an assumed curve (DECISIONS D-013).

### 2.4 Reconciliation against the Data API

The taker leg was matched to Data API `/v2/trades?user=<taker>&condition=<cid>` rows by transaction hash:

| tx | Date | Exchange | Market | On-chain taker leg | Data API row | Match |
|---|---|---|---|---|---|---|
| `0x70cf0fc7…19d8` | 2025-10-01 | V1 NegRisk | AI-model event (negRisk), "No" | SELL 338.03 @ 0.998, fee 0 | SELL 338.03 @ 0.998 | ✓ |
| `0xb65e8b20…afaff` | 2026-03-30 | V1 | BTC up/down 5-min, "Down" | BUY 1.0101 @ 0.99, fee 0.00102 sh | BUY 1.01006 @ 0.99 | ✓ (size differs by 0.004 %; Data API rounding, to check in Phase 2) |
| `0xfd906055…19ea` | 2026-04-29 | V2 | ETH up/down 5-min, "Up" | BUY 7.045452 @ 0.66, fee 0.11383 | BUY 7.045452 @ 0.66 | ✓ |
| `0x1fd6d227…1111` | 2026-10-14 | V2 | BTC up/down 5-min, "Up" | BUY 100 @ 0.37, fee 1.6317 | BUY 100 @ 0.37 | ✓ |

Wallet, side, size and price agree on all four. The Data API has **no fee and no log index**, so fees come only from chain. Decoder used: `scripts/recon/decode.py`.

*Tier note:* this cross-check was done in the original Phase 0, before Checkpoint R existed (D-025). Under the revised MISSION, Data API reconciliation is a Tier 2 cross-check that runs only if R is passed. Tier 1 validation instead relies on internal consistency:
- every `OrdersMatched` has exactly one taker leg;
- maker and taker legs balance;
- V2 `fee` equals `FeeCharged.amount`.

### 2.5 Tier 1 pipeline and decoding audit (Phase 1)

**Crawls** (`pmbook backfill identity|fills|binance`; D-032 to D-037):

1. **identity:** all-address `eth_getLogs` for `TokenRegistered`, CTF `ConditionPreparation`/`ConditionResolution`, UMA `QuestionInitialized`/`QuestionResolved` and NegRisk `QuestionPrepared`/`MarketPrepared`. It runs from 2022-09-26 strictly in time order. The home-jurisdiction filter runs on the question text here.
2. **fills:** `OrderFilled` (V1 and V2 topics) from the five venue exchanges (D-031), from 2025-10-01. One row per leg, with addresses pseudonymised at decode time.
3. **binance:** public 1-minute klines.

Storage is Parquet (zstd) under `dataset=<name>/date=YYYY-MM-DD/`, with schema version and `venue` in every file. Raw parts are written atomically and never modified. Crawls are resumable from per-day manifests, and orphaned parts from an interrupted flush are removed on resume.

**Decoding audit** (`pmbook validate --audit-per-day N`): for N random stored transactions per complete day, the receipt is re-fetched and checked:
- (a) the stored legs equal the receipt's venue `OrderFilled` logs, field by field;
- (b) taker legs = `OrdersMatched` events;
- (c) for V2, the sum of taker-leg fees = the sum of `FeeCharged`.

Per-day integrity checks:
- unique (tx, log_index);
- at least one taker leg per transaction;
- exchange generation consistent with the 2026-04-28 migration;
- price in (0, 1];
- fee ≥ 0.

## 3. Outcome definitions

_Phase 3, from PREREGISTRATION.md._

## 4. Estimators

_Phase 3._

## 5. Pseudonymisation

Wallet addresses in any released artifact are replaced with `HMAC-SHA256(salt, lowercase_address)` truncated to 16 bytes, hex encoded. The salt is local only and never committed.
