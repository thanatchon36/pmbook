"""MISSION §1.4 / §11: no venue-hosted endpoint is contacted unless PMBOOK_TIER2=1."""

import importlib
import re
import socket
import sys
from pathlib import Path

import httpx
import pytest

from pmbook.config import Settings, Tier2DisabledError, is_venue_host
from pmbook.http import PublicClient

SRC = Path(__file__).resolve().parents[1] / "src" / "pmbook"
# URLs or hostnames under a venue domain (the bare domain in config.VENUE_DOMAINS is the blocklist).
VENUE_HOST_RE = re.compile(r"(://|[a-z0-9-]\.)polymarket\.com", re.IGNORECASE)


def test_tier2_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PMBOOK_TIER2", raising=False)
    assert Settings(_env_file=None).tier2 is False  # type: ignore[call-arg]


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("gamma-api.polymarket.com", True),
        ("Polymarket.com.", True),
        ("clob.polymarket.com", True),
        ("notpolymarket.com", False),
        ("gateway.tenderly.co", False),
        ("data-api.binance.vision", False),
    ],
)
def test_is_venue_host(host: str, expected: bool) -> None:
    assert is_venue_host(host) is expected


def test_venue_package_refuses_import_without_tier2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PMBOOK_TIER2", raising=False)
    sys.modules.pop("pmbook.venue", None)
    with pytest.raises(Tier2DisabledError):
        importlib.import_module("pmbook.venue")


def test_venue_package_imports_with_tier2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PMBOOK_TIER2", "1")
    sys.modules.pop("pmbook.venue", None)
    try:
        assert importlib.import_module("pmbook.venue").GAMMA_URL.startswith("https://")
    finally:
        sys.modules.pop("pmbook.venue", None)


def test_client_refuses_venue_host_without_tier2() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={})

    settings = Settings(_env_file=None, tier2=False)  # type: ignore[call-arg]
    with PublicClient(settings, transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(Tier2DisabledError):
            client.get_json("https://gamma-api.polymarket.com/markets")
        assert client.get_json("https://data-api.binance.vision/api/v3/ping") == {}
    assert [str(r.url.host) for r in calls] == ["data-api.binance.vision"]


def test_venue_hostnames_only_in_venue_package() -> None:
    offenders = [
        str(p.relative_to(SRC))
        for p in SRC.rglob("*.py")
        if "venue" not in p.relative_to(SRC).parts[:1] and VENUE_HOST_RE.search(p.read_text())
    ]
    assert offenders == []


def test_network_is_blocked_in_tests() -> None:
    with pytest.raises(RuntimeError, match="network access is disabled"):
        socket.create_connection(("example.com", 443))
