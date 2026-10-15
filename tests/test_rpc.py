import json
from typing import Any

import httpx
import pytest

from pmbook.config import Settings, Tier2DisabledError
from pmbook.onchain.rpc import ResultCapExceeded, RpcClient, RpcError

SETTINGS = Settings(_env_file=None, http_max_retries=2)  # type: ignore[call-arg]


def client(handler: Any, urls: list[str] | None = None) -> RpcClient:
    return RpcClient(
        urls or ["https://a.example/rpc", "https://b.example/rpc"],
        SETTINGS,
        transport=httpx.MockTransport(handler),
        sleep=lambda s: None,
    )


def ok(result: Any) -> httpx.Response:
    return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": result})


def test_allowlist_blocks_writes() -> None:
    rpc = client(lambda r: ok("0x1"))
    for method in ("eth_sendRawTransaction", "eth_sendTransaction", "eth_sign", "personal_sign"):
        with pytest.raises(ValueError, match="allowlist"):
            rpc.call(method, [])


def test_rejects_venue_endpoint() -> None:
    with pytest.raises(Tier2DisabledError):
        RpcClient(["https://rpc.polymarket.com"], SETTINGS)


def test_get_logs_builds_filter() -> None:
    seen: list[dict[str, Any]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        seen.append(body)
        assert req.method == "POST" and req.headers["user-agent"].startswith("pmbook/")
        return ok([])

    assert client(handler).get_logs(16, 31, [["0xabc"]], ["0xdef"]) == []
    flt = seen[0]["params"][0]
    assert flt == {
        "fromBlock": "0x10",
        "toBlock": "0x1f",
        "address": ["0xdef"],
        "topics": [["0xabc"]],
    }


def test_result_cap_raises() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": 1,
                "error": {
                    "code": -32602,
                    "message": "invalid params",
                    "data": "Query returned more than 20000 results.",
                },
            },
        )

    with pytest.raises(ResultCapExceeded):
        client(handler).get_logs(1, 2, [])


def test_retry_then_failover() -> None:
    hosts: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        hosts.append(req.url.host)
        if req.url.host == "a.example":
            return httpx.Response(429)
        return ok("0x2a")

    rpc = client(handler)
    assert rpc.block_number() == 42
    assert hosts == ["a.example"] * 3 + ["b.example"]
    assert rpc.url == "https://b.example/rpc"


def test_transport_error_and_bad_json_retry() -> None:
    calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("boom")
        if calls["n"] == 2:
            return httpx.Response(200, content=b"not json")
        if calls["n"] == 3:
            return httpx.Response(200, json={"id": 1, "error": {"message": "request timed out"}})
        return ok({"timestamp": "0x10"})

    assert client(handler).block_timestamp(5) == 16


def test_hard_error_raises() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": 1, "error": {"code": -32601, "message": "nope"}})

    with pytest.raises(RpcError):
        client(handler).block_number()


def test_gives_up_after_all_attempts() -> None:
    with pytest.raises(RpcError, match="failed after"):
        client(lambda r: httpx.Response(503, headers={"retry-after": "x"})).block_number()


def test_non_list_logs_rejected() -> None:
    with pytest.raises(RpcError):
        client(lambda r: ok({"x": 1})).get_logs(1, 2, [])


@pytest.mark.parametrize(
    "message",
    [
        "eth_getLogs is limited to a 10,000 range",
        "ranges over 10000 blocks are not supported on free plan",
        "Query returned more than 20000 results.",
    ],
)
def test_provider_range_limits_are_caps(message: str) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": 1, "error": {"code": -32614, "message": message}})

    with pytest.raises(ResultCapExceeded):
        client(handler).get_logs(1, 2, [])
