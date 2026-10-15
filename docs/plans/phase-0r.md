# Phase 0r: re-run of Phase 0 under the revised MISSION (2026-10-15)

The revised MISSION adds a two-tier data model. Tier 1 is on-chain data plus public reference data and is always allowed. Tier 2 is venue-hosted APIs, which are allowed only after Checkpoint R. It also adds a home-jurisdiction exclusion and a private-until-B repository. Most of the original Phase 0 still holds: contracts, OrderFilled decoding, Terms, timeline and name check. This plan covers the gap.

## Done before this plan
- Checkpoint 0 answered: yes to (a), (b) and (c). Checkpoint R is deferred.
- GitHub repo switched from public to **private**.
- The Tier 2 L2 recorder (old Phase 1 WIP) is parked untouched on the local branch `tier2-recorder`, for Phase 5.

## Steps
1. **Tier gate.**
   - Add `Settings.tier2` (`PMBOOK_TIER2`, default off).
   - Move the venue hosts into `pmbook.venue`, which raises `ImportError` unless the flag is on.
   - `PublicClient` refuses venue-operated hosts unless the flag is on.
   - Tests: the gate itself; a static scan that venue hostnames appear only under `venue/`; a `conftest.py` that blocks all real sockets in tests.
2. **Layout per MISSION §5:**
   - `onchain/`, `reference/`, `labels/`, `filters/`, `venue/` (Tier 2).
   - Drop the `record/`, `sources/` and `backfill/` stubs.
   - The CLI gains `labels`. `record` refuses to run without Tier 2.
3. **Recon delta (Tier 1 only):**
   - Keyless archive RPC capacity: the Tenderly public gateway and QuickNode public endpoint serve multi-thousand-block `eth_getLogs`.
   - Market-identity events: `TokenRegistered`, `ConditionPreparation`/`Resolution`, UMA `QuestionInitialized` with question text.
   - Update RECON.md and METHODS.md.
4. **Decisions:** log Checkpoint 0, the repo going private, the recorder being parked, the Tier 1 backfill replacing the Data-API hybrid, Checkpoint D not being re-triggered, and the history of pre-mission venue contact.
5. **Docs:** reframe README, pyproject and CITATION as venue-agnostic market-design research. Update the dataset card to Tier 1 streams.
6. **Verify and ship:** ruff, mypy and pytest green; `pmbook --help` works. Commit, tag `phase-0r`, push to the private repo, CI green.

## Out of scope here
Phase 1 builds the RPC client (a JSON-RPC POST with a read-only method allowlist), the backfill, pseudonymisation and the home-jurisdiction filter.
