"""Wallet pseudonymisation (MISSION §1.8, METHODS §5).

Addresses become ``HMAC-SHA256(salt, lowercase_address)[:16]`` in hex. The salt is a local
secret that is never committed; losing it makes new ids incomparable with old ones, so it is
created once and then only read.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from functools import lru_cache
from pathlib import Path


def load_or_create_salt(path: Path) -> bytes:
    """Read the salt at ``path``, creating a new 32-byte one (mode 0600) if it does not exist."""
    if path.exists():
        salt = path.read_bytes()
        if len(salt) < 32:
            raise ValueError(f"salt at {path} is shorter than 32 bytes")
        return salt
    path.parent.mkdir(parents=True, exist_ok=True)
    salt = secrets.token_bytes(32)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(salt)
    return salt


class Pseudonymizer:
    """Maps addresses to stable pseudonymous ids. Raw addresses never leave this object."""

    def __init__(self, salt: bytes) -> None:
        if len(salt) < 32:
            raise ValueError("salt must be at least 32 bytes")
        self._salt = salt
        self.id = lru_cache(maxsize=1_000_000)(self._id)

    def _id(self, address: str) -> str:
        return hmac.new(self._salt, address.lower().encode(), hashlib.sha256).hexdigest()[:32]
