import json
from pathlib import Path
from typing import Any

from pmbook.onchain import contracts as c
from pmbook.onchain.audit import audit, check_receipt
from pmbook.onchain.decode import decode_fill
from pmbook.store import PartitionStore

FIX: dict[str, Any] = json.loads((Path(__file__).parent / "fixtures_logs.json").read_text())


def pseudo(a: str) -> str:
    return "id" + a[-6:]


def receipt(key: str) -> dict[str, Any]:
    logs = FIX[key]
    return {"logs": logs, "blockTimestamp": logs[0]["blockTimestamp"]}


def stored(key: str) -> list[dict[str, Any]]:
    return [r for lg in FIX[key] if (r := decode_fill(lg, pseudo)) is not None]


def test_clean_receipts_pass() -> None:
    for key in ("v1_match", "v2_match"):
        assert check_receipt(receipt(key), stored(key), pseudo, set()) == []


def test_detects_missing_leg_and_fee_mismatch() -> None:
    rows = stored("v2_match")[1:]
    problems = check_receipt(receipt("v2_match"), rows, pseudo, set())
    assert problems and "differ" in problems[0]
    bad = receipt("v2_match")
    bad["logs"] = [
        lg | {"data": "0x" + f"{1:064x}"} if lg["topics"][0] == c.FEE_CHARGED else lg
        for lg in bad["logs"]
    ]
    assert any(
        "FeeCharged" in p for p in check_receipt(bad, stored("v2_match"), pseudo, set()) or []
    )
    nomatch = receipt("v1_match")
    nomatch["logs"] = [lg for lg in nomatch["logs"] if lg["topics"][0] != c.ORDERS_MATCHED_V1]
    assert any(
        "OrdersMatched" in p
        for p in check_receipt(nomatch, stored("v1_match"), pseudo, set()) or []
    )


def test_excluded_tokens_skipped() -> None:
    tok = stored("v1_match")[0]["token_id"]
    assert check_receipt(receipt("v1_match"), [], pseudo, {tok}) is None


class FakeRpc:
    def __init__(self) -> None:
        self.by_tx = {FIX[k][0]["transactionHash"]: receipt(k) for k in ("v1_match", "v2_match")}

    def call(self, method: str, params: list[Any]) -> Any:
        assert method == "eth_getTransactionReceipt"
        return self.by_tx[params[0]]


def test_audit_over_partitions(tmp_path: Path) -> None:
    from datetime import date

    store = PartitionStore(tmp_path, "fills_onchain")
    rows = stored("v1_match") + stored("v2_match")
    store.write_part(date(2026, 3, 30), 1, 2, rows)
    res = audit(FakeRpc(), tmp_path, [date(2026, 3, 30), date(2026, 3, 31)], pseudo, set(), 10)  # type: ignore[arg-type]
    assert (res.sampled, res.passed, res.failures) == (2, 2, [])
