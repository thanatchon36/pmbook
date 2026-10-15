# pmbook

[![CI](https://github.com/thanatchon36/pmbook/actions/workflows/ci.yml/badge.svg)](https://github.com/thanatchon36/pmbook/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

> **Research only.** pmbook is academic, open-source research on public data. It is not a trading product and not advice, and it does not encourage participation in any market. It has no account, no wallet, no keys, and no code that can place an order.

pmbook is an open-source, venue-agnostic Python toolkit for prediction-market microstructure research, and the code behind a pre-registered paper on **fee design and market quality**: how a staggered taker-fee rollout with maker rebates changed volume, liquidity, maker composition and price efficiency.

The first case study reconstructs the complete trade-and-fee record of a large prediction market **from public Polygon chain data alone**, with no venue account, key or relationship:

1. **Backfill** exchange fills, fees, conditions and question text from public chain events (Tier 1).
2. **Label** markets into fee categories, validated on a hand-labelled sample.
3. **Analyse** the rollout with heterogeneity-robust staggered DiD, event studies and a fee-intensity triple-difference. The analysis is pre-registered and reproducible with `make reproduce`.

Venue-hosted APIs (Tier 2) are disabled by default (`PMBOOK_TIER2`) and stay unused until the author completes a separate legal check (Checkpoint R in [`MISSION.md`](MISSION.md)).

Status: **Phase 0 (recon and scaffold).** See [`MISSION.md`](MISSION.md) for the plan and [`docs/DECISIONS.md`](docs/DECISIONS.md) for the decision log.

## Quickstart

```bash
uv sync
uv run pmbook --help
```

## Data and terms

pmbook reads public chain data through general-purpose RPC endpoints and public reference data. It sends a descriptive User-Agent, backs off on errors and caches aggressively. The venue's Terms of Use restrict redistribution of its data, so this project releases code and the paper only, not data; rebuild locally with `pmbook backfill`. Wallet addresses are pseudonymised, and the paper reports aggregates only. See [`docs/DECISIONS.md`](docs/DECISIONS.md) (D-004, D-019, D-026).

## Citation

See [`CITATION.cff`](CITATION.cff).

## License

Code: Apache-2.0.
