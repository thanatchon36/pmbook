"""Read-only Polygon JSON-RPC client over general-purpose public endpoints (Tier 1).

JSON-RPC needs HTTP POST, so this is the one module allowed to POST (tests/test_guardrails.py).
Only the read-only methods in ``ALLOWED_METHODS`` can be called; nothing here can sign or send.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from typing import Any

import httpx
import structlog

from pmbook.config import USER_AGENT, Settings, Tier2DisabledError, is_venue_host
from pmbook.http import RETRY_STATUS, backoff_delay

log = structlog.get_logger(__name__)

ALLOWED_METHODS = frozenset(
    {
        "eth_blockNumber",
        "eth_chainId",
        "eth_getBlockByNumber",
        "eth_getCode",
        "eth_getLogs",
        "eth_getTransactionReceipt",
    }
)

# Provider messages meaning "too many results for this range; ask for fewer blocks".
_CAP_MARKERS = (
    "more than",
    "too many",
    "limit exceeded",
    "limited to",
    "response size",
    "range is too large",
    "ranges over",
)


class RpcError(RuntimeError):
    """A JSON-RPC error that retrying the same request will not fix."""


class ResultCapExceeded(RpcError):
    """The provider refused the range because it holds too many logs; split the range."""


class RpcClient:
    """Sequential JSON-RPC client with failover across an ordered endpoint list."""

    def __init__(
        self,
        urls: Sequence[str] | None = None,
        settings: Settings | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.settings = settings or Settings()
        self.urls = list(urls or self.settings.polygon_rpc_urls)
        if not self.urls:
            raise ValueError("no RPC endpoints configured")
        for url in self.urls:
            if is_venue_host(httpx.URL(url).host):
                raise Tier2DisabledError(f"{url} is venue-operated; Tier 1 needs general RPC")
        self._active = 0
        self._sleep = sleep
        self._id = 0
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT, "Content-Type": "application/json"},
            timeout=self.settings.http_timeout_s,
            transport=transport,
        )

    @property
    def url(self) -> str:
        return self.urls[self._active]

    def call(self, method: str, params: list[Any]) -> Any:
        """Call a read-only method, retrying transient failures and failing over endpoints."""
        if method not in ALLOWED_METHODS:
            raise ValueError(f"RPC method {method!r} is not in the read-only allowlist")
        attempts = (self.settings.http_max_retries + 1) * len(self.urls)
        for attempt in range(attempts):
            self._id += 1
            payload = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params}
            try:
                resp = self._client.post(self.url, json=payload)
            except httpx.TransportError as exc:
                log.warning("rpc.transport_error", url=self.url, error=str(exc)[:200])
                self._wait(attempt)
                continue
            if resp.status_code in RETRY_STATUS:
                self._wait(attempt, resp.headers.get("retry-after"))
                continue
            try:
                body = resp.json()
            except ValueError:
                self._wait(attempt)
                continue
            if "result" in body:
                return body["result"]
            err = body.get("error") or {}
            msg = f"{err.get('message', '')} {err.get('data', '')}".lower()
            if any(m in msg for m in _CAP_MARKERS):
                raise ResultCapExceeded(msg.strip())
            if "timed out" in msg or "timeout" in msg or resp.status_code >= 500:
                self._wait(attempt)
                continue
            raise RpcError(f"{self.url}: {err}")
        raise RpcError(f"{method} failed after {attempts} attempts")

    def _wait(self, attempt: int, retry_after: str | None = None) -> None:
        """Back off; after exhausting retries on one endpoint, fail over to the next."""
        per_url = self.settings.http_max_retries + 1
        if (attempt + 1) % per_url == 0 and len(self.urls) > 1:
            self._active = (self._active + 1) % len(self.urls)
            log.warning("rpc.failover", url=self.url)
        try:
            ra = float(retry_after) if retry_after is not None else None
        except ValueError:
            ra = None
        s = self.settings
        self._sleep(
            backoff_delay(attempt % per_url, s.http_backoff_base_s, s.http_backoff_cap_s, ra)
        )

    def block_number(self) -> int:
        return int(self.call("eth_blockNumber", []), 16)

    def block_timestamp(self, number: int) -> int:
        block = self.call("eth_getBlockByNumber", [hex(number), False])
        return int(block["timestamp"], 16)

    def get_logs(
        self,
        from_block: int,
        to_block: int,
        topics: list[Any],
        address: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        flt: dict[str, Any] = {"fromBlock": hex(from_block), "toBlock": hex(to_block)}
        if address:
            flt["address"] = list(address)
        flt["topics"] = topics
        result = self.call("eth_getLogs", [flt])
        if not isinstance(result, list):
            raise RpcError(f"eth_getLogs returned {type(result).__name__}")
        return result

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> RpcClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
