import stat
from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from pmbook.filters.home_jurisdiction import KEYWORDS, is_excluded, match
from pmbook.onchain.pseudonym import Pseudonymizer, load_or_create_salt
from pmbook.schema import SCHEMA_VERSION, read_version
from pmbook.store import INT64_MAX, PartitionStore, rows_to_table


def test_salt_created_once_with_private_mode(tmp_path: Path) -> None:
    path = tmp_path / "secrets" / "pseudonym.salt"
    salt = load_or_create_salt(path)
    assert len(salt) == 32 and load_or_create_salt(path) == salt
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    path.write_bytes(b"short")
    with pytest.raises(ValueError):
        load_or_create_salt(path)


def test_pseudonym_stable_case_insensitive_and_salted() -> None:
    a = Pseudonymizer(b"a" * 32)
    b = Pseudonymizer(b"b" * 32)
    addr = "0xAbCdEf0000000000000000000000000000000001"
    assert a.id(addr) == a.id(addr.lower())
    assert len(a.id(addr)) == 32 and addr.lower()[2:] not in a.id(addr)
    assert a.id(addr) != b.id(addr)
    with pytest.raises(ValueError):
        Pseudonymizer(b"x")


@pytest.mark.parametrize(
    "text",
    [
        "Will Thailand's PM survive a no-confidence vote?",
        "Bangkok governor election",
        "USD/THB above 36 on Friday?",
        "Will Pheu Thai win the most seats?",
        "Will the SET index close higher?",
        "Muay Thai fight: who wins?",
        "ราคาทอง",
        "thai baht weakens",
    ],
)
def test_filter_matches(text: str) -> None:
    assert is_excluded(text)


@pytest.mark.parametrize(
    "text",
    [
        "Will Bitcoin reach $150k?",
        "Will the Thunder win the NBA Finals?",
        "Taiwan election 2028",
        "Will Spotify stream counts exceed 1B?",
        "Setup of the new index fund",
        None,
        "",
    ],
)
def test_filter_does_not_match(text: str | None) -> None:
    assert not is_excluded(text)


def test_filter_reports_keywords() -> None:
    assert match("Shinawatra and Thailand, again Thailand") == ["shinawatra", "thailand"]
    assert all(k == k.lower() for ks in KEYWORDS.values() for k in ks)


def test_store_writes_metadata_and_nulls_overflow(tmp_path: Path) -> None:
    store = PartitionStore(tmp_path, "tokens_onchain")
    row = {
        "block_number": 5,
        "block_ts": 1_775_000_000,
        "tx_hash": "0x" + "0" * 64,
        "log_index": 1,
        "emitter": "0x1",
        "token0": "1",
        "token1": "2",
        "condition_id": "0xc",
    }
    path = store.write_part(date(2026, 3, 30), 5, 9, [row])
    table = pq.read_table(path)
    assert read_version(table.schema) == SCHEMA_VERSION
    assert table.column("venue").to_pylist() == ["polymarket"]
    assert store.parts(date(2026, 3, 30)) == [path]
    assert store.recover(date(2026, 3, 30), 4) == [path]
    schema = pa.schema([pa.field("venue", pa.string()), pa.field("amount", pa.int64())])
    table = rows_to_table([{"amount": INT64_MAX + 1}, {"amount": 7}], schema)
    assert table.column("amount").to_pylist() == [None, 7]
    assert read_version(schema) is None
