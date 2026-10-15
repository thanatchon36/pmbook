"""Contract addresses and event topics (verified in docs/RECON.md §3, §7 and the Phase 1 census)."""

from __future__ import annotations

from dataclasses import dataclass

from eth_hash.auto import keccak


def topic0(signature: str) -> str:
    """keccak256 of an event signature, as a 0x-prefixed lowercase hex string."""
    return "0x" + keccak(signature.encode()).hex()


@dataclass(frozen=True)
class Exchange:
    name: str
    version: int  # 1 = CTF Exchange V1 ABI, 2 = V2 ABI
    neg_risk: bool


# The venue's exchanges. Other contracts emitting the same topics are unrelated deployments
# of the open-source exchange code and are excluded (DECISIONS D-031).
EXCHANGES: dict[str, Exchange] = {
    "0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e": Exchange("ctf_v1", 1, False),
    "0xc5d563a36ae78145c45a50134d48a1215220f80a": Exchange("negrisk_v1", 1, True),
    "0xe111180000d2663c0091e4f400237545b87b996b": Exchange("ctf_v2", 2, False),
    "0xe2222d279d744050d28e00520010520000310f59": Exchange("negrisk_v2", 2, True),
    "0xe3333700ca9d93003f00f0f71f8515005f6c00aa": Exchange("exchange_v3", 2, False),
}

CONDITIONAL_TOKENS = "0x4d97dcd97ec945f40cf65f87097ace5ea0476045"
NEG_RISK_ADAPTER = "0xd91e80cf2e7be2e162c6513ced06f1dd0da35296"

ORDER_FILLED_V1 = topic0(
    "OrderFilled(bytes32,address,address,uint256,uint256,uint256,uint256,uint256)"
)
ORDER_FILLED_V2 = topic0(
    "OrderFilled(bytes32,address,address,uint8,uint256,uint256,uint256,uint256,bytes32,bytes32)"
)
ORDERS_MATCHED_V1 = topic0("OrdersMatched(bytes32,address,uint256,uint256,uint256,uint256)")
ORDERS_MATCHED_V2 = topic0("OrdersMatched(bytes32,address,uint8,uint256,uint256,uint256)")
FEE_CHARGED = topic0("FeeCharged(address,uint256)")

TOKEN_REGISTERED = topic0("TokenRegistered(uint256,uint256,bytes32)")
CONDITION_PREPARATION = topic0("ConditionPreparation(bytes32,address,bytes32,uint256)")
CONDITION_RESOLUTION = topic0("ConditionResolution(bytes32,address,bytes32,uint256,uint256[])")
QUESTION_INITIALIZED = topic0(
    "QuestionInitialized(bytes32,uint256,address,bytes,address,uint256,uint256)"
)
# Legacy UMA CTF adapter (oracle 0xcb18…5130, 2022): same text payload, different ABI.
QUESTION_INITIALIZED_LEGACY = topic0(
    "QuestionInitialized(bytes32,bytes,uint256,address,uint256,uint256,bool)"
)
QUESTION_RESOLVED = topic0("QuestionResolved(bytes32,int256,uint256[])")
MARKET_PREPARED = topic0("MarketPrepared(bytes32,address,uint256,bytes)")
QUESTION_PREPARED = topic0("QuestionPrepared(bytes32,bytes32,uint256,bytes)")
