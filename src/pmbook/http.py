"""Polite, read-only HTTP access to public endpoints.

Only GET is exposed. pmbook never sends orders, signatures or credentials (MISSION §1),
so there is deliberately no method here that could do so.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable, Mapping
from typing import Any

import httpx
import structlog

from pmbook.config import USER_AGENT, Settings, Tier2DisabledError, is_venue_host

log = structlog.get_logger(__name__)


RETRY_STATUS = frozenset({429, 500, 502, 503, 504})


def backoff_delay(attempt: int, base: float, cap: float, retry_after: float | None = None) -> float:
    """Exponential back-off with full jitter; honours a server ``Retry-After`` when larger."""
    delay = random.uniform(0, min(cap, base * 2**attempt))
    if retry_after is not None:
        delay = max(delay, min(retry_after, cap))
    return delay


def _retry_after(resp: httpx.Response) -> float | None:
    value = resp.headers.get("retry-after")
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


class PublicClient:
    """GET-only client with a descriptive User-Agent and back-off on 429/5xx."""

    def __init__(
        self,
        settings: Settings | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.settings = settings or Settings()
        self._sleep = sleep
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=self.settings.http_timeout_s,
            transport=transport,
            follow_redirects=True,
        )

    def get_json(self, url: str, params: Mapping[str, Any] | None = None) -> Any:
        """GET ``url`` and decode JSON, retrying transient failures."""
        s = self.settings
        if is_venue_host(httpx.URL(url).host) and not s.tier2:
            raise Tier2DisabledError(f"{url} is venue-hosted (Tier 2); requires PMBOOK_TIER2=1")
        for attempt in range(s.http_max_retries + 1):
            try:
                resp = self._client.get(url, params=params)
            except httpx.TransportError as exc:
                if attempt == s.http_max_retries:
                    raise
                delay = backoff_delay(attempt, s.http_backoff_base_s, s.http_backoff_cap_s)
                log.warning("http.transport_error", url=url, error=str(exc), sleep=delay)
                self._sleep(delay)
                continue
            if resp.status_code in RETRY_STATUS and attempt < s.http_max_retries:
                delay = backoff_delay(
                    attempt, s.http_backoff_base_s, s.http_backoff_cap_s, _retry_after(resp)
                )
                log.warning("http.retry", url=url, status=resp.status_code, sleep=delay)
                self._sleep(delay)
                continue
            resp.raise_for_status()
            return resp.json()
        raise RuntimeError("unreachable")  # pragma: no cover

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> PublicClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
