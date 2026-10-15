"""Tier 2: venue-hosted endpoints (MISSION §1.4, §3.2).

Importable only with ``PMBOOK_TIER2=1``, which the author sets only after Checkpoint R.
Until then nothing in pmbook may contact these hosts, tests included.
"""

from pmbook.config import Settings, Tier2DisabledError

if not Settings().tier2:
    raise Tier2DisabledError(
        "pmbook.venue is Tier 2 and requires PMBOOK_TIER2=1 (only after Checkpoint R; MISSION §9)."
    )

GAMMA_URL = "https://gamma-api.polymarket.com"
CLOB_URL = "https://clob.polymarket.com"
CLOB_WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
DATA_API_URL = "https://data-api.polymarket.com"
