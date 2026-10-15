# Phase 0 recon probes

Throwaway, read-only probes used to verify contract events and fee semantics (docs/RECON.md, docs/METHODS.md §2).
Public keyless RPC only; no keys, no signing.

```bash
cd scripts/recon
uv run --no-project --with 'eth-hash[pycryptodome]' python decode.py <tx_hash>
```
