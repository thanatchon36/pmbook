import httpx
import pytest

from pmbook.config import USER_AGENT, Settings
from pmbook.http import PublicClient, backoff_delay


def make_client(handler: httpx.MockTransport, sleeps: list[float]) -> PublicClient:
    settings = Settings(http_max_retries=3, http_backoff_base_s=1.0, http_backoff_cap_s=10.0)
    return PublicClient(settings=settings, transport=handler, sleep=sleeps.append)


def test_user_agent_and_get_only() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"ok": True})

    with make_client(httpx.MockTransport(handler), []) as client:
        assert client.get_json("https://example.org/x", params={"a": 1}) == {"ok": True}
    assert seen[0].method == "GET"
    assert seen[0].headers["user-agent"] == USER_AGENT
    assert USER_AGENT.startswith("pmbook/") and "github.com/thanatchon36/pmbook" in USER_AGENT
    assert not hasattr(PublicClient, "post")


def test_retries_on_429_then_succeeds_honouring_retry_after() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, headers={"Retry-After": "5"})
        return httpx.Response(200, json=[1])

    sleeps: list[float] = []
    with make_client(httpx.MockTransport(handler), sleeps) as client:
        assert client.get_json("https://example.org/x") == [1]
    assert calls["n"] == 3
    assert len(sleeps) == 2 and all(s >= 5 for s in sleeps)


def test_gives_up_after_max_retries() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    sleeps: list[float] = []
    with (
        make_client(httpx.MockTransport(handler), sleeps) as client,
        pytest.raises(httpx.HTTPStatusError),
    ):
        client.get_json("https://example.org/x")
    assert len(sleeps) == 3


def test_transport_error_retried() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("boom")
        return httpx.Response(200, json={})

    sleeps: list[float] = []
    with make_client(httpx.MockTransport(handler), sleeps) as client:
        assert client.get_json("https://example.org/x") == {}
    assert len(sleeps) == 1


def test_transport_error_raised_when_exhausted() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    with make_client(httpx.MockTransport(handler), []) as client, pytest.raises(httpx.ConnectError):
        client.get_json("https://example.org/x")


def test_non_retryable_error_raises_immediately() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    sleeps: list[float] = []
    with (
        make_client(httpx.MockTransport(handler), sleeps) as client,
        pytest.raises(httpx.HTTPStatusError),
    ):
        client.get_json("https://example.org/x")
    assert sleeps == []


def test_backoff_bounds() -> None:
    for attempt in range(10):
        d = backoff_delay(attempt, 1.0, 60.0)
        assert 0 <= d <= 60.0
    assert backoff_delay(0, 1.0, 60.0, retry_after=30.0) == 30.0
    assert backoff_delay(0, 1.0, 60.0, retry_after=600.0) == 60.0


def test_bad_retry_after_ignored() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "Wed, 21 Oct 2015 07:28:00 GMT"})
        return httpx.Response(200, json={})

    sleeps: list[float] = []
    with make_client(httpx.MockTransport(handler), sleeps) as client:
        client.get_json("https://example.org/x")
    assert len(sleeps) == 1 and sleeps[0] <= 1.0
