"""MISSION §1.1: no code path may sign or post orders, hold keys or derive API credentials.

This test scans the shipped package for markers of such code paths and fails if any appear.
"""

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "pmbook"

FORBIDDEN = [
    r"py_clob_client",
    r"clob[_-]client",
    r"signTypedData|sign_typed_data|eth_sign\b|personal_sign",
    r"private[_ ]?key",
    r"mnemonic",
    r"eth_account|web3\.eth\.account|Account\.from_key",
    r"create_or_derive_api_creds|derive_api_key|/auth/api-key",
    r"POLY_API_KEY|POLY_PASSPHRASE|POLY_SIGNATURE",
    r"\.post\(|\.put\(|\.delete\(|\.patch\(",
    r"method\s*=\s*['\"](POST|PUT|DELETE|PATCH)['\"]",
    r"['\"]/orders?['\"]",
    r"eth_sendRawTransaction|eth_sendTransaction",
]


def test_no_order_or_signing_code() -> None:
    offenders: list[str] = []
    for path in SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN:
            for m in re.finditer(pattern, text, flags=re.IGNORECASE):
                line = text.count("\n", 0, m.start()) + 1
                offenders.append(f"{path.relative_to(SRC)}:{line}: {m.group(0)!r}")
    assert not offenders, "Forbidden order/signing markers found:\n" + "\n".join(offenders)


def test_scanner_detects_markers(tmp_path: Path) -> None:
    sample = "client.post('/order', json=signed)\nkey = private_key\n"
    hits = [p for p in FORBIDDEN if re.search(p, sample, flags=re.IGNORECASE)]
    assert len(hits) >= 3
