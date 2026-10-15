"""Home-jurisdiction exclusion (MISSION §1.5, DECISIONS D-030).

Markets referencing Thailand (the country, its politics, elections, courts, public
institutions, companies, people or currency) are dropped at ingestion. Matching is
deliberately over-inclusive: a false positive costs one market, a false negative breaks a
guardrail. The keyword list is reviewed against a residual sample (DECISIONS D-030).
"""

from __future__ import annotations

import re

# Whole-word, case-insensitive. Keep groups explicit so the review log can cite them.
KEYWORDS: dict[str, tuple[str, ...]] = {
    "country": ("thailand", "thai", "thais", "siam", "siamese", "kingdom of thailand"),
    "places": (
        "bangkok",
        "krung thep",
        "phuket",
        "chiang mai",
        "chiang rai",
        "pattaya",
        "krabi",
        "koh samui",
        "ko samui",
        "hua hin",
        "ayutthaya",
        "khon kaen",
        "udon thani",
        "nakhon ratchasima",
        "korat",
        "hat yai",
        "songkhla",
        "pattani",
        "yala",
        "narathiwat",
        "suvarnabhumi",
        "don mueang",
        "isan",
        "isaan",
    ),
    "currency_markets": ("baht", "thb", "usdthb", "usd/thb", "thbusd", "set50", "set index"),
    "institutions": (
        "bank of thailand",
        "election commission of thailand",
        "constitutional court of thailand",
        "royal thai",
        "thai senate",
        "thai parliament",
        "national anti-corruption commission",
        "chakri",
        "vajiralongkorn",
        "rama x",
        "bhumibol",
        "sirikit",
    ),
    "politics": (
        "shinawatra",
        "thaksin",
        "yingluck",
        "paetongtarn",
        "srettha",
        "thavisin",
        "anutin",
        "charnvirakul",
        "prayut",
        "prayuth",
        "chan-o-cha",
        "prawit",
        "pita limjaroenrat",
        "limjaroenrat",
        "natthaphong",
        "ruengpanyawut",
        "pheu thai",
        "bhumjaithai",
        "move forward party",
        "palang pracharath",
        "democrat party of thailand",
        "united thai nation",
        "kla tham",
    ),
    "companies": (
        "ptt",
        "cp all",
        "charoen pokphand",
        "thai beverage",
        "thaibev",
        "singha",
        "chang beer",
        "kasikornbank",
        "kbank",
        "siam commercial",
        "scb x",
        "bangkok bank",
        "krungthai",
        "true corporation",
        "advanced info service",
        "airports of thailand",
        "thai airways",
        "gulf energy",
        "central pattana",
        "minor international",
    ),
    "culture_sport": ("muay thai", "thai league", "buriram", "bangkok united", "songkran"),
}

_THAI_SCRIPT = re.compile(r"[\u0E00-\u0E7F]")
_PATTERN = re.compile(
    r"(?<![a-z0-9])("
    + "|".join(
        sorted((re.escape(k) for ks in KEYWORDS.values() for k in ks), key=len, reverse=True)
    )
    + r")(?![a-z0-9])",
    re.IGNORECASE,
)


def match(text: str | None) -> list[str]:
    """Return the matched keywords (lowercased) or ``["<thai-script>"]``; empty if none."""
    if not text:
        return []
    hits = sorted({m.group(1).lower() for m in _PATTERN.finditer(text)})
    if _THAI_SCRIPT.search(text):
        hits.append("<thai-script>")
    return hits


def is_excluded(text: str | None) -> bool:
    return bool(match(text))
