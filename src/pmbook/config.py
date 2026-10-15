"""Runtime settings (environment variables prefixed ``PMBOOK_``) and public endpoints."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from pmbook import __version__

USER_AGENT = f"pmbook/{__version__} research; github.com/thanatchon36/pmbook"

# Tier 1 endpoints (MISSION §3.1): general-purpose infrastructure, never venue-operated.
# Keyless archive RPCs verified in docs/RECON.md §4.
POLYGON_RPC_URLS = (
    "https://gateway.tenderly.co/public/polygon",
    "https://rpc-mainnet.matic.quiknode.pro",
    "https://polygon.drpc.org",
)
BINANCE_URL = "https://data-api.binance.vision"

# Registrable domains operated by the venue (MISSION §1.4). Hosts under these are Tier 2:
# contacted only when PMBOOK_TIER2=1, i.e. after Checkpoint R. Their URLs live in pmbook.venue.
VENUE_DOMAINS = frozenset({"polymarket.com"})


class Tier2DisabledError(RuntimeError):
    """A venue-hosted endpoint was requested without ``PMBOOK_TIER2=1`` (MISSION §1.4, §9)."""


def is_venue_host(host: str) -> bool:
    """True if ``host`` is, or is a subdomain of, a venue-operated domain."""
    host = host.lower().rstrip(".")
    return any(host == d or host.endswith("." + d) for d in VENUE_DOMAINS)


class Settings(BaseSettings):
    """Settings overridable via ``PMBOOK_*`` environment variables or a ``.env`` file."""

    model_config = SettingsConfigDict(env_prefix="PMBOOK_", env_file=".env", extra="ignore")

    tier2: bool = False  # Checkpoint R gate; see MISSION §1.4 and §9
    data_dir: Path = Path("data")
    polygon_rpc_urls: tuple[str, ...] = POLYGON_RPC_URLS
    http_timeout_s: float = 30.0
    http_max_retries: int = 6
    http_backoff_base_s: float = 1.0
    http_backoff_cap_s: float = 60.0
