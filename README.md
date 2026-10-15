# pmbook

[![CI](https://github.com/thanatchon36/pmbook/actions/workflows/ci.yml/badge.svg)](https://github.com/thanatchon36/pmbook/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

> **Research only.** pmbook reads public market data. It has no account, no wallet, no keys, and no code that can place an order. Nothing here is trading advice.

pmbook is an open-source Python toolkit for studying prediction-market microstructure on Polymarket:

1. **Record** public CLOB data: L2 books, book deltas, trades, and market, fee and reward metadata, written to versioned Parquet.
2. **Reconstruct** historical fills and fees from public Polygon `OrderFilled` events.
3. **Analyse** the 2026 taker-fee rollout as a natural experiment in market quality. The paper is pre-registered and reproducible.

Status: **Phase 0 (recon and scaffold).** See [`MISSION.md`](MISSION.md) for the plan and [`docs/DECISIONS.md`](docs/DECISIONS.md) for the decision log.

## Quickstart

```bash
uv sync
uv run pmbook --help
```

## Data and terms

pmbook uses only documented, unauthenticated public endpoints and public chain data, sends a descriptive User-Agent and backs off on 429/5xx. Polymarket's Terms of Use restrict redistribution of its data, so this repo does not ship raw data. See [`docs/DECISIONS.md`](docs/DECISIONS.md) (D-004) and [`docs/RECON.md`](docs/RECON.md).

## Citation

See [`CITATION.cff`](CITATION.cff).

## License

Code: Apache-2.0.
