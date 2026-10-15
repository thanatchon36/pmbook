# Decision log

Format: **ID — date — phase — decision.** *Why:* rationale. *Rejected:* alternatives. Newest at the bottom.

- **D-001 — 2026-10-15 — P0 — Run all phases on Opus 5.5** (the session model), not the per-phase model/effort suggestions in MISSION §8. *Why:* one autonomous session; quality bar is unchanged. *Rejected:* switching models mid-session (the user can still do so with `/model`).
- **D-002 — 2026-10-15 — P0 — Repo at `~/github/pmbook`, public GitHub repo `thanatchon36/pmbook`** created in Phase 0 so CI can run, following the sibling research repos. The user approved this in the Phase 0 plan. *Rejected:* a private repo (the mission is open source; PyPI/HF/LinkedIn stay behind Checkpoint B).
- **D-003 — 2026-10-15 — P0 — Package name `pmbook`.** It is free on PyPI (`pmbook`, `bookprob`, `oddsdepth` and `polystruct` all return 404) and on HF (`thanatchon36/pmbook-polymarket` not taken). GitHub has unrelated `PMBook` repos, so there is no clash under this account. *Rejected:* the alternates, which are unnecessary.
- **D-004 — 2026-10-15 — P0 — Terms decision: raw-data redistribution is NOT permitted; no raw dataset release.** Polymarket ToU (effective 2026-08-11) §4 forbids redistributing "Data" (raw, derived, aggregated or anonymised, explicitly including on-chain) to Capital Market Clients or market-data distributors. It also forbids those parties from using it, and grants only a personal, non-sublicensable licence. A public dataset cannot exclude such recipients, and publishing one arguably makes pmbook a market-data distributor. Consequences:
  1. No public raw Parquet or Hugging Face dataset of Polymarket API data.
  2. The release is code, rebuild scripts (`pmbook backfill`/`record`), the paper's tables and figures, and a dataset card describing how to rebuild.
  3. Whether even the **derived market-day panel** may be released is a legal-risk call for the user. It goes to **Checkpoint C**, and the default until answered is **not to release it**.

  *Why:* the guardrail says unclear terms are restrictive. *Rejected:* "on-chain data is public, so it is fine". The ToU names on-chain data explicitly, and the guardrail requires following the terms.
- **D-005 — 2026-10-15 — P0 — Data access stays within the ToU.** pmbook does no HTML scraping. It uses only documented public APIs, which Polymarket's docs present as a resource for "builders, researches, and analysts". It stays far below the documented Cloudflare limits, identifies itself in the User-Agent, and is non-commercial research by an independent individual (not a Capital Market Client). Trading is restricted for some jurisdictions (including Thailand); pmbook never trades, and Content Features are permitted everywhere. *Rejected:* none; noted for transparency.
- **D-006 — 2026-10-15 — P0 — Timeline corrections vs MISSION §2** (detail in TIMELINE.md):
  - January 2026 crypto fees covered only 15-min (and, from 12 Feb, 5-min) crypto up/down markets.
  - 18 Feb 2026 sports fees covered only NCAAB and Serie A.
  - Other crypto markets were treated from 6 Mar, and only those created after 6 Mar.
  - The "April 2026" fee-formula correction was on 31 Mar 2026.
  - New concurrent changes: the 28 Apr 2026 exchange/collateral migration (orders wiped), the 28 May 2026 Taker Rebate Program, and the 10 Jul 2026 sports rate change 0.03 → 0.05 with rebate 25 % → 15 %.

  These force design changes to §2/§4, so **Checkpoint E** applies (see D-013).
- **D-007 — 2026-10-15 — P0 — Historical fee status comes from chain, never from Gamma.** Gamma `feesEnabled`/`feeSchedule`/`feeType` are current-state snapshots, and pre-fee markets show `null`. Gamma `feeType` is kept as a category label. *Rejected:* inferring treatment dates from Gamma.
- **D-008 — 2026-10-15 — P0 — Backfill must decode both exchange generations:** V1 (2 contracts, until 2026-04-28) and V2 (3 contracts: CTF V2, NegRisk V2, Protocol V2 `ExchangeV3`), with different ABIs and fee units (METHODS §2). *Rejected:* V1-only decoding, which would lose everything after 28 Apr.
- **D-009 — 2026-10-15 — P0 — Price history:** use the CLOB `/prices-history?fidelity=1` route for the backfill (1-minute history verified back to 2025-10-01). Data API `/v2/prices-history` returned empty for the same token and window. CLOB is now "legacy", but v1 data routes are frozen rather than removed. Re-test v2 in Phase 2. *Rejected:* v2 only, which leaves gaps.
- **D-010 — 2026-10-15 — P0 — Kalshi stream:** in scope as **optional**, implemented only in Phase 2 if time allows. The public markets endpoint needs no auth. *Why:* RQ5 cross-venue substitution is secondary; within-Polymarket substitution to geopolitics is primary.
- **D-011 — 2026-10-15 — P0 — WS subscription sharding:** no per-connection asset cap is documented (the 100-token cap was removed 2025-05-28). Use ≤ 500 assets per connection anyway to bound the blast radius of a disconnect. Gap detection uses REST snapshot reconciliation because the market channel has no sequence numbers. *Rejected:* a single giant connection.
- **D-012 — 2026-10-15 — P0 — Polygon RPC: `polygon.drpc.org` (keyless) is the only free archive-capable endpoint found.** publicnode needs a token for archive data, polygon-rpc.com is disabled, and ankr needs a key. The keyless dRPC accepts ≤ 100-block `eth_getLogs` ranges. The full backfill window needs ≥ 184 k such requests and roughly 1–2.5 B logs (RECON §4). That is beyond what a keyless public endpoint can reasonably serve → **Checkpoint D** raised early (formally a Phase 2 checkpoint). No account was created anywhere. Options are in the Checkpoint D/E report; recommended: D-014.
- **D-013 — 2026-10-15 — P0 — Proposed design changes (pending Checkpoint E):**
  1. **Treatment is defined at market level** from on-chain realised fees (first day a market's taker legs carry fee > 0), not category × date. The main cohort is 30 Mar 2026; early cohorts are NCAAB/Serie A (18 Feb) and new crypto markets (≥ 6 Mar); geopolitics is never treated.
  2. **Add the 10 Jul 2026 sports rate change (0.03 → 0.05) as a second, dose-response experiment** for RQ1/RQ2.
  3. **The fee-intensity variable** for the triple-diff is the realised on-chain fee/notional, with the `p(1−p)` quintile as the pre-specified instrument/proxy. The V1-era formula (≤ 31 Mar) was not ∝ p(1−p).
  4. **The main event window is truncated to [−8w, +4w)** around 30 Mar, because the 28 Apr migration (orders wiped, new collateral) hits all markets including controls. ±8w is kept as a robustness check with a migration indicator.
  5. **Taker rebates (28 May) are added to the concurrent-changes list.**
  6. **The short-duration crypto exclusion stays**, so the January 2026 "crypto" date drops out of the main analysis.
- **D-014 — 2026-10-15 — P0 — Recommended backfill architecture (pending Checkpoint D):** use a **hybrid** approach.
  - (a) **Data API v2 `/v2/trades?condition=…&taker_only=false`** per market for the analysis universe (excluding short-duration crypto). It has keyset paging with no depth cap and returns taker and maker wallets, side, size, price and tx hash.
  - (b) **On-chain receipts** (`eth_getTransactionReceipt`) for a stratified random sample of those tx hashes, per market-week. This recovers fees, verifies treatment dates and sizes the V1 maker-fee anomaly, and makes the reconciliation a built-in check.
  - (c) **Full `eth_getLogs` decoding only for short windows** (e.g. ±2 days around each rollout date), to audit (a).

  This keeps the on-chain record as ground truth while cutting RPC load by roughly 3 orders of magnitude. *Rejected:* a full-window `eth_getLogs` crawl on a keyless endpoint (load and etiquette); signing up for an RPC key (the user's call, and Guardrail 6).
- **D-015 — 2026-10-15 — P0 — Phase 0 dependencies kept minimal** (httpx, typer, pydantic-settings, structlog). pyarrow, polars, duckdb, websockets and prometheus-client are added in Phase 1 when first used. *Rejected:* declaring unused deps now.
- **D-016 — 2026-10-15 — P0 — PDF engine:** `tectonic` is not installed locally. Phase 4 will install it in CI (or use pandoc + a TeX engine from the runner). *Rejected:* deciding now.
- **D-017 — 2026-10-15 — P0 — `mypy --strict` applies to the whole package**, which is stricter than MISSION's four packages. *Why:* cheap at this size; relax per module only if a third-party stub forces it.
- **D-018 — 2026-10-15 — P0 — Guardrail enforcement test** (`tests/test_guardrails.py`) scans `src/pmbook` for signing, key, credential and order-posting markers, and for non-GET HTTP verbs. The HTTP client exposes GET only.
- **D-019 — 2026-10-15 — P0 — Checkpoint C resolved (owner): release = code + paper only.** Code, rebuild scripts, the paper's tables and figures, and the dataset card. No raw data, **no derived panel**. Supersedes the open item in D-004 (3). MISSION §7's HF dataset is dropped. The dataset card documents rebuilding only.
- **D-020 — 2026-10-15 — P0 — Checkpoint D resolved (owner): hybrid backfill (D-014) adopted.** Data API v2 per-market trades (taker + maker legs) for the analysis universe. On-chain receipts for a stratified sample give fees and treatment-date verification. Full `eth_getLogs` decoding runs only in ±2-day audit windows around rollout dates. Keyless `polygon.drpc.org`, no accounts. MISSION §3.1 `fills_onchain` becomes `fills_onchain_sample` + `fills_onchain_windows`. "≥ 99 % reconciliation" is measured on the sampled receipts vs Data API rows.
- **D-021 — 2026-10-15 — P0 — Checkpoint E resolved (owner): D-013 design changes accepted** (market-level on-chain treatment; 30 Mar main cohort with 18 Feb and 6 Mar early cohorts; main window [−8w, +4w) around 30 Mar; 10 Jul sports dose-response; realised fee/notional intensity; taker rebates as a concurrent change). PREREGISTRATION.md (Phase 3) is written on this basis.

### Revised MISSION (2026-10-15): Tier 1 / Tier 2 model, Checkpoint R, home-jurisdiction exclusion, private until B

- **D-022 — 2026-10-15 — P0r — Checkpoint 0 answered (owner):** (a) paper #1 is the fee-design study; (b) §1 guardrails accepted in full; (c) the repository stays private until Checkpoint B. **Checkpoint R deferred** by the owner: Phases 1–4 run on Tier 1 only, and R is asked again before Phase 5.
- **D-023 — 2026-10-15 — P0r — Repository made private.** Supersedes D-002. `thanatchon36/pmbook` was public from Phase 0 until today (commits `853f735`, `8850ac2`). Those commits contained the old MISSION, the scaffold and the recon docs, but no data, credentials or employer references. Copies may exist in caches or forks; this cannot be undone and is recorded for transparency. *Rejected:* deleting and recreating the repo (it does not remove external copies and loses the CI history).
- **D-024 — 2026-10-15 — P0r — The Tier 2 L2 recorder is parked** untouched on the local branch `tier2-recorder` (commit `1dd92e0`). It holds the old Phase 1 work: Gamma/CLOB REST/WS sources, runner, writers and validate, with 46 tests. It returns only in Phase 5, after Checkpoint R, restructured into `pmbook.venue`. Its useful Tier-1-agnostic parts (Parquet writer, schema and validate scaffolding) may be cherry-picked in Phase 1. *Rejected:* discarding it; keeping it on main behind the flag (dead code on the critical path).
- **D-025 — 2026-10-15 — P0r — Venue-hosted endpoints were contacted before the revised MISSION.** This happened in the original Phase 0 recon (RECON §1–§2) and in the parked recorder's development, before Checkpoint R existed. From this commit on, nothing in `main` can contact a venue host without `PMBOOK_TIER2=1`:
  - `pmbook.venue` refuses to import.
  - `PublicClient` refuses venue hosts.
  - A static test confines venue hostnames to `pmbook/venue/`.
  - `tests/conftest.py` blocks all sockets in tests.
  - The `record` CLI exits with code 3.

  Facts learned from those probes (D-007, D-009 and RECON §1–§2) are used only as background and Tier 2 design notes, never as data.
- **D-026 — 2026-10-15 — P0r — Backfill architecture is Tier-1 only; supersedes D-014/D-020 (Data-API hybrid) and D-009 (CLOB price history).** Fills, fees, makers and takers come from a full `eth_getLogs` crawl of the exchange contracts over 2025-10-01 → present. Market identity comes from `TokenRegistered`, CTF and UMA events (RECON §7). Mid proxies are built from fills (MISSION §3.2), documented in METHODS. Checkpoints C and E outcomes (D-019, D-021) stand: the Terms analysis is unchanged, and the D-013 design stays, with treatment measured on chain. *Rejected:* keeping the Data API hybrid (Tier 2, so not allowed before R).
- **D-027 — 2026-10-15 — P0r — Checkpoint D not re-triggered.** D-012 assumed a 100-block keyless limit. Re-probing (RECON §4b) found the Tenderly public gateway serving 3,000-block ranges at ~3.7 MB/s, keyless, capped at 20k results per call, with QuickNode public as fallback. Even ~1–2 TB of JSON is a multi-day sequential crawl, which is feasible. Etiquette rules:
  - Sequential requests (one in flight per provider).
  - Adaptive ranges.
  - Back-off on errors.
  - Descriptive User-Agent.
  - Resumable checkpoints.
  - Raw logs cached locally so nothing is fetched twice.

  A Phase 1 pilot (±7 days around 2026-03-30, the densest period) measures real throughput. If the projected full crawl is over 14 days, or a provider objects or rate-limits persistently, Checkpoint D is raised then. Local disk has 884 GB free, against an estimated 100–250 GB as Parquet. *Rejected:* asking now (the evidence says it is feasible); signing up for a keyed free tier (accounts are the owner's call).
- **D-028 — 2026-10-15 — P0r — Layout per MISSION §5:** `onchain/`, `reference/`, `labels/`, `filters/`, `venue/` (Tier 2), `schema/`, `validate/`, `panel/`, `micro/`, `analysis/`. The old `record/`, `sources/` and `backfill/` stubs are removed. The CLI adds `labels`; `record` is Tier 2-gated. JSON-RPC needs HTTP POST. Phase 1 adds a dedicated RPC client with a read-only method allowlist (`eth_getLogs`, `eth_getBlockByNumber`, `eth_blockNumber`, `eth_getTransactionReceipt`, `eth_chainId`, `eth_getCode`), and the guardrail scan is narrowed to allow POST only there.
- **D-029 — 2026-10-15 — P0r — Venue-agnostic framing (§1.9):** the README, pyproject description and CITATION title describe prediction-market microstructure and fee design; the venue is named only in data/background sections. The `polymarket` keyword is removed from package metadata.
- **D-030 — 2026-10-15 — P0r — Home-jurisdiction filter design (implemented in Phase 1):** the filter runs at ingestion on the UMA ancillary question text (plus negRisk event text). It uses a case-insensitive keyword list covering:
  - the country, the currency, major cities and provinces;
  - institutions (parliament, constitutional court, election commission, the central bank);
  - major listed companies, political parties, and current and former PMs and party leaders;
  - Thai-script detection.

  A manual review covers all matches plus a random residual sample of 200 non-matched questions that mention Southeast Asia.
  - **Committed:** the keyword list (`src/pmbook/filters/`) and an aggregate review summary in DECISIONS (counts, precision on the review sample, keywords added). No question text, ids or titles of excluded markets.
  - **Local only, gitignored (`data/filters/`):** the excluded condition ids and the per-question review notes, because a released list would itself mention the excluded markets.

  Markets whose question text is unavailable on chain are held back from the panel until classified. *Rejected:* a filter applied only at analysis time (the guardrail requires ingestion).

### Phase 1: on-chain backfill

- **D-031 — 2026-10-15 — P1 — The venue exchange set is the five known contracts.** A 17-point census (50-block samples every ~26.6 days, 2025-10-01 → 2026-10-15) found that every `OrderFilled`/`OrdersMatched`/`FeeCharged` log of material volume comes from V1 CTF, V1 NegRisk (until 2026-04-28) and V2 CTF, V2 NegRisk and `ExchangeV3` (from 2026-04-28; `ExchangeV3` ≈ 0.3 % of logs). Four other contracts emit the V1 topics at ≤ 2 logs per sample; these are unrelated deployments of the open-source exchange code and are excluded. The cut-over is clean: no V1 fills in samples after 28 Apr and no V2 fills before it. `pmbook validate` enforces this per day.
- **D-032 — 2026-10-15 — P1 — How "excluded at ingestion" is implemented for fills.** Fill logs carry token ids, not text. So the identity crawl (question text → condition → token) runs first, strictly in time order from the V1 exchange deployment (2022-09-26, block 33,605,403). It drops matched questions and remembers their condition and token ids in the local registry `data/filters/excluded.json`. The fills crawl for day D runs only when identity is complete through D, and drops legs on excluded tokens at decode time, so they are never written. Tokens whose question text is not found on chain are kept in the raw partitions but held back from the panel until classified (D-030). *Rejected:* filtering at panel time only, which would leave excluded markets in stored tables.
- **D-033 — 2026-10-15 — P1 — Fills crawl fetches only the `OrderFilled` topics.** `OrdersMatched` and `FeeCharged` are redundant given the taker-leg rule and the V2 taker-leg `fee` (METHODS §2.2), and skipping them cuts transfer by ~40 %. The sampled-receipt audit (METHODS §2.5) re-checks both against receipts.
- **D-034 — 2026-10-15 — P1 — Pseudonymisation happens at decode time.**
  - **Pseudonymised:** maker and taker addresses become HMAC-SHA256 ids. The salt is local (`secrets/pseudonym.salt`, gitignored, mode 0600, created once).
  - **Not pseudonymised:** order hashes and tx hashes stay in the local raw partitions, because the receipt audit and deduplication need them.
  - **Re-identification risk:** a tx hash leads back to on-chain addresses. The raw partitions are therefore never released (D-019), and released outputs are aggregates only (§1.8).

  The taker-leg flag (`taker == exchange`) is computed before hashing.
- **D-035 — 2026-10-15 — P1 — RPC endpoints and chunking.** The Tenderly public gateway is the primary endpoint. It is about 5× faster than QuickNode public, which caps `eth_getLogs` at 10,000 blocks. Settings:
  - **Range caps:** QuickNode's range-limit error and Tenderly's 20,000-result error both count as "split the range" (`ResultCapExceeded`).
  - **Chunk sizing:** chunks aim at ~10k logs, grow at most 2× (4× when empty), and are capped at 10,000 blocks.
  - **Finality:** the crawl stops 300 blocks behind head.
  - **Day boundaries:** UTC days are mapped to blocks by interpolation search seeded from the previous day's boundary, and cached.
  - **Parallelism:** one request in flight per provider. Parallelism means separate processes on separate providers over disjoint date ranges.
- **D-036 — 2026-10-15 — P1 — Amounts are stored as raw 6-dp int64.** Values above int64 (never observed; that would be over $9.2 trillion) are stored as null rather than wrapped. Prices are kept as float64 alongside.
- **D-037 — 2026-10-15 — P1 — Binance reference data** is 1-minute spot klines for BTC/ETH/SOL/XRP-USDT from the keyless `data-api.binance.vision` mirror, starting 2025-10-01. A day is stored only when complete (1,440 rows), with `venue = "binance"`.
- **D-038 — 2026-10-15 — P1 — Identity decoding accepts only the venue emitter and the expected topic count.** The identity crawl queries topics without an address filter, so that question text from every UMA adapter generation is captured. Unrelated contracts reuse the `TokenRegistered` signature. Some index two arguments rather than three (for example `0xa4e0…0ab5` and `0x2cd8…bc9e` on 2026-02-16), and this crashed the crawl. Others match the venue's 4-topic layout (for example `0x87b8…`, `0x403c…`, and ~30 smaller emitters).
  - **Tokens:** only the five venue exchanges are accepted.
  - **Topic count:** every decoder checks it (legacy `QuestionInitialized` has 2 topics, `QuestionResolved`/`QuestionPrepared`/`MarketPrepared` have 3, the others 4).
  - **Questions:** all emitters are still kept. The panel joins questions through `conditions_onchain.oracle`, so foreign questions never reach it.
  - **Cleanup:** the 7,528 foreign token rows already written (0.86 % of 878,278) were removed in place from 321 partitions. Days up to 2026-02-15 were not re-crawled: venue rows are unaffected because the decoder change only drops rows. This is the one exception to "raw parts are never modified". It is equivalent to re-running the fixed decoder over those days, which yields the same venue rows. It was done during the initial crawl, before any partition was frozen or used in analysis.
- **D-039 — 2026-10-15 — P2 — Conditions from the short-crypto resolver carry no question text.** In the venue data, 240k conditions (from 2025-08 onward) have oracle `0x58e1…efde`. They are prepared through an ERC-4337 entry point (`0x4337…f108`), and no adapter emits question text for them. About 95 % resolve 1,439–1,455 minutes after preparation, which matches short-window crypto up/down markets created a day ahead. Treatment: `text_source = short_crypto_resolver`, category `crypto` with flag `short_crypto`. They are handled separately in the analysis, as MISSION §3.3 requires. The label is confirmed against fee-rate silver labels in Phase 2 (METHODS §1.4). They cannot be screened by the home-jurisdiction text filter, but they are crypto price markets by construction.
- **D-040 — 2026-10-15 — P1 — Fills pilot and full-crawl orchestration.**
  - **Pilot day 2026-03-23 (near peak density):** 11.8M legs, 4.45M taker legs, 640 MB of Parquet, 21 min on QuickNode public. The receipt audit passed 30/30 transactions. Integrity: one leg priced outside (0, 1], examined in Phase 2.
  - **Pilot shortened:** it was cut to this one complete day (plus a partial 03-24 that the full crawl resumes), because a 15-day pilot alone would take ~5 h and the full crawl is resumable over the same partitions.
  - **Full crawl:** three `systemd --user` transient units (`pmbook-identity`, `pmbook-fills-a` 2025-10-01..2026-03-22 on QuickNode, `pmbook-fills-b` 2026-03-24.. on Tenderly). Detached shells were killed with the controlling session twice.
  - **Expected size:** ~90 GB of Parquet. 840 GB is free.
