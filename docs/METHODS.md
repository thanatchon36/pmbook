# Methods

> Status: §2 (fill decoding) drafted in Phase 0 from decoded real transactions. The other sections are filled in Phases 1–3.

## 1. Data sources and coverage

Tier 1 only (D-026). Fills come from a full `eth_getLogs` crawl of the exchange contracts over keyless public RPC (RECON §4b). Market identity and question text come from on-chain `TokenRegistered`, CTF and UMA adapter events (RECON §7). Coverage reports: Phase 1.

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

## 3. Outcome definitions

_Phase 3, from PREREGISTRATION.md._

## 4. Estimators

_Phase 3._

## 5. Pseudonymisation

Wallet addresses in any released artifact are replaced with `HMAC-SHA256(salt, lowercase_address)` truncated to 16 bytes, hex encoded. The salt is local only and never committed.
