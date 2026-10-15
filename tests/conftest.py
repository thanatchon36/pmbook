"""Tests never touch the network (MISSION §1.4: no venue contact before Checkpoint R)."""

import socket
from collections.abc import Iterator

import pytest


class NetworkBlockedError(RuntimeError):
    pass


@pytest.fixture(autouse=True)
def _block_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    def guard(*args: object, **kwargs: object) -> None:
        raise NetworkBlockedError("network access is disabled in tests")

    monkeypatch.setattr(socket.socket, "connect", guard)
    monkeypatch.setattr(socket.socket, "connect_ex", guard)
    monkeypatch.setattr(socket, "create_connection", guard)
    monkeypatch.setattr(socket, "getaddrinfo", guard)
    yield
