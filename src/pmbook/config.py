"""Runtime settings (environment variables prefixed ``PMBOOK_``) and public endpoints."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from pmbook import __version__

USER_AGENT = f"pmbook/{__version__} research; github.com/thanatchon36/pmbook"

# Public, unauthenticated endpoints verified in Phase 0 (docs/RECON.md).
GAMMA_URL = "https://gamma-api.polymarket.com"
CLOB_URL = "https://clob.polymarket.com"
CLOB_WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
DATA_API_URL = "https://data-api.polymarket.com"
BINANCE_URL = "https://data-api.binance.vision"
POLYGON_RPC_URL = "https://polygon.drpc.org"


class Settings(BaseSettings):
    """Settings overridable via ``PMBOOK_*`` environment variables or a ``.env`` file."""

    model_config = SettingsConfigDict(env_prefix="PMBOOK_", env_file=".env", extra="ignore")

    data_dir: Path = Path("data")
    polygon_rpc_url: str = POLYGON_RPC_URL
    http_timeout_s: float = 30.0
    http_max_retries: int = 6
    http_backoff_base_s: float = 1.0
    http_backoff_cap_s: float = 60.0
