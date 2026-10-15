"""Rule-based classification of market text into the venue's fee categories (METHODS §1.4).

The categories are those of Fee Structure V2 (docs/TIMELINE.md): crypto, sports, finance,
politics, economics, culture, weather, tech, mentions, other, and the fee-free geopolitics.
Rules are ordered; the first matching rule wins and its name is recorded so that every label
can be traced. Rules were developed against fee-rate silver labels and a hand-labelled
sample (METHODS §1.4; DECISIONS D-040). They see only public question text.

Flags:

* ``short_crypto``: crypto up/down markets over a fixed short window (5 min to 4 h), a
  structurally different class handled separately in the analysis (MISSION §3.3).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

CATEGORIES = (
    "crypto",
    "sports",
    "finance",
    "politics",
    "economics",
    "culture",
    "weather",
    "tech",
    "mentions",
    "other",
    "geopolitics",
)

# Fee Structure V2 taker rates (2026-03-30). Sports moves to 0.05 on 2026-07-10.
RATE_GROUP = {
    "crypto": "r07",
    "sports": "r03",
    "finance": "r04",
    "politics": "r04",
    "mentions": "r04",
    "tech": "r04",
    "economics": "r05",
    "culture": "r05",
    "weather": "r05",
    "other": "r05",
    "geopolitics": "r00",
}


@dataclass(frozen=True)
class Label:
    category: str
    rule: str
    short_crypto: bool = False


def _rx(*words: str) -> re.Pattern[str]:
    return re.compile(r"(?<![\w$])(?:" + "|".join(words) + r")(?![\w])", re.IGNORECASE)


CRYPTO_ASSETS = _rx(
    r"bitcoin", r"btc", r"ethereum", r"eth", r"ether", r"solana", r"sol", r"xrp", r"ripple",
    r"dogecoin", r"doge", r"cardano", r"ada", r"bnb", r"hyperliquid", r"hype", r"litecoin",
    r"ltc", r"avalanche", r"avax", r"chainlink", r"link", r"polkadot", r"tron", r"trx",
    r"shiba inu", r"shib", r"pepe", r"sui", r"toncoin", r"ton", r"monero", r"xmr", r"usdt",
    r"usdc", r"tether", r"stablecoin", r"memecoin", r"altcoin", r"crypto(?:currency|currencies)?",
    r"pump\.fun", r"fartcoin", r"bonk", r"wif", r"trump coin", r"\$trump", r"world liberty",
    r"fdv", r"airdrop", r"token launch", r"megaeth", r"pudgy penguins", r"nft",
    r"microstrategy", r"saylor", r"coinbase", r"binance", r"satoshi", r"etf flows?",
)  # fmt: skip
UP_DOWN = re.compile(r"\bup or down\b", re.IGNORECASE)
SHORT_WINDOW = re.compile(
    r"\b\d{1,2}(?::\d{2})?\s?(?:am|pm)\b(?:\s?-\s?\d{1,2}(?::\d{2})?\s?(?:am|pm))?\s*et\b"
    r"|\b(?:5|15|30)[- ]?(?:min|minute)s?\b|\b(?:1|4)[- ]?(?:h|hour)s?\b",
    re.IGNORECASE,
)

MENTIONS = re.compile(
    r"\b(?:say|says|said|mention|mentions|tweet the word)\b[^?]{0,80}[\"“'‘]"
    r"|\bwhat will .{1,60} say\b|\bmention(?:ed|s)?\b.{0,40}\bduring\b",
    re.IGNORECASE,
)
TWEET_COUNT = re.compile(r"\b(?:tweets?|posts?)\b.{0,40}\bfrom\b.{0,40}\bto\b|# of tweets", re.I)

WEATHER = _rx(
    r"temperature", r"highest temp", r"lowest temp", r"°[cf]", r"degrees", r"rainfall",
    r"precipitation", r"snowfall", r"inches of (?:rain|snow)", r"hurricane", r"tropical storm",
    r"named storms?", r"tornado(?:es)?", r"heat ?wave", r"weather", r"noaa", r"el niño",
    r"la niña", r"hottest (?:year|month|day)", r"earthquake", r"magnitude", r"wildfire",
    r"climate",
)  # fmt: skip

ESPORTS = _rx(
    r"counter-strike", r"cs2", r"cs:go", r"dota 2", r"dota", r"league of legends", r"lol:",
    r"valorant", r"overwatch", r"rainbow six", r"call of duty", r"honor of kings",
    r"mobile legends", r"starcraft ii", r"starcraft", r"rocket league", r"pubg", r"apex legends",
    r"esports?", r"total kills", r"map \d", r"game \d winner", r"first blood", r"lck", r"lpl",
    r"lec", r"lcs", r"iem", r"blast premier", r"pgl", r"esl", r"the international",
    r"fortnite", r"tekken", r"street fighter", r"chess", r"fide", r"magnus carlsen",
)  # fmt: skip
SPORTS = _rx(
    r"nfl", r"nba", r"wnba", r"mlb", r"nhl", r"mls", r"ncaa[bf]?", r"cfb", r"college football",
    r"college basketball", r"march madness", r"final four", r"super bowl", r"world series",
    r"stanley cup", r"nba finals", r"playoffs?", r"premier league", r"epl", r"la liga",
    r"laliga", r"serie a", r"serie b", r"bundesliga", r"ligue 1", r"eredivisie", r"liga mx",
    r"champions league", r"europa league", r"conference league", r"ucl", r"uel", r"fa cup",
    r"copa (?:america|libertadores|sudamericana|del rey)", r"world cup", r"fifa", r"uefa",
    r"euro 20\d\d", r"afcon", r"a-league", r"j1 league", r"k league", r"süper lig", r"super lig",
    r"primeira liga", r"primera a", r"primera división", r"brasileirão", r"saudi pro league",
    r"ufc", r"mma", r"boxing", r"bout", r"knockout", r"fight night", r"wwe", r"f1",
    r"formula 1", r"grand prix", r"nascar", r"indycar", r"motogp", r"tennis", r"atp", r"wta",
    r"wimbledon", r"us open", r"french open", r"roland garros", r"australian open", r"golf",
    r"pga", r"lpga", r"liv golf", r"masters tournament", r"the masters", r"ryder cup",
    r"cricket", r"ipl", r"t20", r"odi", r"test match", r"big bash", r"rugby", r"six nations",
    r"super rugby", r"nrl", r"afl", r"cycling", r"tour de france", r"olympics?", r"olympic",
    r"athletics", r"marathon", r"darts", r"snooker", r"handball", r"volleyball", r"baseball",
    r"basketball", r"football", r"soccer", r"hockey", r"heisman", r"mvp", r"rookie of the year",
    r"ballon d'or", r"golden boot", r"draft pick", r"first overall pick", r"coach of the year",
    r"cy young", r"o/u \d", r"over/under", r"spread:", r"handicap", r"moneyline",
    r"both teams to score", r"anytime goalscorer", r"exact score", r"total (?:goals|points|sets|games|runs|corners)",
    r"halftime", r"1h", r"2h", r"to qualify", r"relegated", r"relegation", r"promoted",
    r"top scorer", r"top batter", r"top bowler", r"win the (?:league|title|cup|series|match|game|fight)",
    r"win on 20\d\d-\d\d-\d\d", r"end in a draw", r"grand slam", r"medal", r"podium",
    r"pole position", r"fastest lap", r"home run", r"touchdowns?", r"rushing yards", r"strikeouts",
)  # fmt: skip
VERSUS = re.compile(r"\b(?:vs\.?|v\.)\s", re.IGNORECASE)
# A title that is (or starts with) "<name> vs. <name>", optionally followed by ": <prop>".
MATCHUP = re.compile(r"^(?:[^:?]{2,60}:\s)?[^:?]{2,60}\s(?:vs\.?|v\.)\s[^:?]{2,60}(?::|\?|$|\s\()")
# Matchup titles that are not games: elections and conflicts.
NOT_A_GAME = _rx(
    r"debate",
    r"election",
    r"primary",
    r"polls?",
    r"nominee",
    r"mayor",
    r"governor",
    r"senate",
    r"president",
    r"parliament",
    r"seat",
    r"war",
    r"ceasefire",
    r"invasion",
    r"strikes?",
    r"troops",
    r"peace",
    r"talks",
    r"sanctions",
    r"tariffs?",
)

GEOPOLITICS = _rx(
    r"war", r"ceasefire", r"cease-fire", r"truce", r"invade", r"invasion", r"invades",
    r"military", r"troops", r"airstrikes?", r"strikes? on", r"missiles?", r"drones? strike",
    r"nuclear", r"warhead", r"nato", r"ukraine", r"ukrainian", r"zelensky(?:y)?", r"kremlin",
    r"putin", r"russia", r"russian", r"gaza", r"hamas", r"hezbollah", r"houthis?", r"israel",
    r"idf", r"netanyahu", r"iran", r"iranian", r"khamenei", r"tehran", r"syria", r"assad",
    r"taiwan", r"north korea", r"kim jong un", r"pyongyang", r"venezuela", r"maduro",
    r"sanctions?", r"peace deal", r"peace talks", r"hostages?", r"annex", r"blockade",
    r"coup", r"regime", r"insurgents?", r"rebels?", r"militants?", r"terror(?:ist)? attack",
    r"un security council", r"g7", r"g20", r"brics", r"diplomatic", r"embassy", r"foreign minister",
    r"defense minister", r"pentagon", r"greenland", r"panama canal", r"strait of hormuz",
    r"south china sea", r"kashmir", r"india and pakistan", r"pakistan", r"sudan", r"yemen",
    r"lebanon", r"west bank", r"crimea", r"donbas", r"kursk", r"kyiv", r"moscow",
)  # fmt: skip
POLITICS = _rx(
    r"election", r"elected", r"re-?election", r"primary", r"primaries", r"caucus", r"nominee",
    r"nomination", r"presidential", r"president", r"vice president", r"senate", r"senator",
    r"house seat", r"congress(?:ional)?", r"governor", r"gubernatorial", r"mayor(?:al)?",
    r"parliament", r"prime minister", r"chancellor", r"cabinet", r"secretary of", r"impeach(?:ed|ment)?",
    r"approval rating", r"poll(?:s|ing)?", r"democrats?", r"republicans?", r"gop", r"dnc", r"rnc",
    r"labour", r"tory", r"conservatives?", r"party", r"coalition", r"vote", r"votes", r"ballot",
    r"referendum", r"electoral", r"swing state", r"trump", r"biden", r"harris", r"vance",
    r"newsom", r"desantis", r"aoc", r"obama", r"pelosi", r"schumer", r"mcconnell", r"musk.{0,20}doge",
    r"executive order", r"pardon", r"supreme court", r"scotus", r"justice", r"indicted", r"convicted",
    r"sentenced", r"government shutdown", r"shutdown", r"bill", r"legislation", r"filibuster",
    r"veto", r"white house", r"press secretary", r"attorney general", r"fbi", r"doj", r"cia",
    r"deport(?:ed|ation|ations)?", r"ice raids?", r"immigration", r"tariff exemption",
    r"midterms?", r"speaker of the house", r"leader of", r"minister", r"seats",
)  # fmt: skip
ECONOMICS = _rx(
    r"fed", r"federal reserve", r"fomc", r"interest rates?", r"rate (?:cut|hike)s?", r"bps",
    r"basis points", r"cpi", r"inflation", r"pce", r"ppi", r"gdp", r"recession", r"unemployment",
    r"jobless", r"nonfarm", r"payrolls?", r"jobs report", r"jobs added", r"ecb", r"bank of england",
    r"boe", r"bank of japan", r"boj", r"central bank", r"tariffs?", r"trade deal", r"trade war",
    r"debt ceiling", r"national debt", r"deficit", r"treasury yields?", r"10-year yield",
    r"exchange rate", r"usd to", r"housing starts", r"home prices", r"retail sales",
    r"consumer confidence", r"ism", r"pmi", r"jolts", r"powell", r"fed chair", r"gas prices?",
    r"egg prices?", r"minimum wage", r"stimulus", r"irs", r"tax(?:es)?", r"budget",
)  # fmt: skip
FINANCE = _rx(
    r"s&p 500", r"s&p", r"spx", r"nasdaq", r"dow jones", r"dow", r"russell 2000", r"vix",
    r"stock", r"stocks", r"shares", r"share price", r"market cap", r"ipo", r"earnings", r"eps",
    r"revenue", r"quarterly", r"dividend", r"buyback", r"nyse", r"ticker", r"close (?:above|below)",
    r"closes (?:above|below)", r"all[- ]time high", r"nvidia", r"nvda",
    r"tesla", r"tsla", r"apple", r"aapl", r"microsoft", r"msft", r"amazon", r"amzn", r"meta",
    r"alphabet", r"googl", r"netflix", r"palantir", r"pltr", r"gamestop", r"gme", r"amd",
    r"intel", r"berkshire", r"gold", r"silver", r"crude oil", r"oil price", r"wti", r"brent",
    r"natural gas", r"copper", r"commodit(?:y|ies)", r"hedge fund", r"bankrupt(?:cy)?",
    r"acquisition", r"acquire", r"merger", r"largest company", r"trillion",
)  # fmt: skip
TECH = _rx(
    r"ai model", r"best ai", r"top ai", r"llm", r"openai", r"chatgpt", r"gpt-?\d", r"gpt",
    r"anthropic", r"claude", r"gemini", r"grok", r"xai", r"deepseek", r"mistral", r"llama",
    r"lmarena", r"chatbot arena", r"agi", r"artificial intelligence", r"iphone", r"ios",
    r"android", r"apple event", r"wwdc", r"spacex", r"starship", r"starlink", r"falcon 9",
    r"launch", r"rocket", r"nasa", r"blue origin", r"neuralink", r"tiktok", r"app store",
    r"google search", r"semiconductor", r"chip", r"quantum", r"robotaxi", r"waymo", r"self-driving",
    r"humanoid", r"optimus", r"vision pro", r"software", r"tech", r"github", r"x\.com",
)  # fmt: skip
CULTURE = _rx(
    r"movie", r"film", r"box office", r"opening weekend", r"rotten tomatoes", r"oscars?",
    r"academy awards?", r"best picture", r"grammys?", r"emmys?", r"golden globes?", r"tony awards?",
    r"album", r"song", r"single", r"billboard", r"hot 100", r"spotify", r"streams?", r"youtube",
    r"mrbeast", r"netflix top", r"tv show", r"season \d", r"episode", r"finale", r"bachelor(?:ette)?",
    r"survivor", r"big brother", r"love island", r"eurovision", r"taylor swift", r"kanye", r"ye",
    r"drake", r"kendrick", r"beyoncé", r"beyonce", r"rihanna", r"bieber", r"celebrity",
    r"married", r"engaged", r"divorce", r"pregnant", r"baby", r"dating", r"time person of the year",
    r"person of the year", r"pope", r"conclave", r"vatican", r"nobel", r"met gala", r"super bowl halftime",
    r"halftime show", r"wordle", r"tweets?", r"followers", r"subscribers", r"instagram",
    r"twitch", r"streamer", r"kick", r"podcast", r"book", r"gta vi", r"gta 6", r"video game",
    r"game of the year", r"the game awards", r"anime", r"jeopardy", r"wikipedia", r"google trends",
)  # fmt: skip

# Order matters: specific, high-precision rules first. Geopolitics before politics, because
# the control group must not absorb domestic politics (and vice versa).
_ORDER: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    ("weather", "weather", WEATHER),
    ("mentions", "mentions", MENTIONS),
    ("crypto", "crypto_assets", CRYPTO_ASSETS),
    ("sports", "esports", ESPORTS),
    ("sports", "sports_terms", SPORTS),
    ("economics", "economics_terms", ECONOMICS),
    ("geopolitics", "geopolitics_terms", GEOPOLITICS),
    ("politics", "politics_terms", POLITICS),
    ("tech", "tech_terms", TECH),
    ("finance", "finance_terms", FINANCE),
    ("culture", "culture_terms", CULTURE),
)


def classify(
    title: str | None,
    description: str | None = None,
    event_title: str | None = None,
    text_source: str | None = None,
) -> Label:
    """Category of one market. Titles decide; the description is a tie-breaker."""
    if text_source == "short_crypto_resolver":
        return Label("crypto", "short_crypto_resolver", short_crypto=True)
    head = " | ".join(t for t in (event_title, title) if t)
    if not head:
        return Label("other", "no_text")
    if UP_DOWN.search(head) and CRYPTO_ASSETS.search(head):
        return Label("crypto", "crypto_up_down", short_crypto=bool(SHORT_WINDOW.search(head)))
    if TWEET_COUNT.search(head):
        return Label("mentions", "tweet_count")
    # "Texas Tech vs. Alabama", "Tulsa Golden Hurricane": team names trip topical rules.
    if MATCHUP.search(title or "") and not NOT_A_GAME.search(head):
        return Label("sports", "matchup")
    for cat, rule, rx in _ORDER:
        if rx.search(head):
            return Label(cat, rule)
    if VERSUS.search(head):
        return Label("sports", "versus")
    if description:
        for cat, rule, rx in _ORDER:
            if rx.search(description[:400]):
                return Label(cat, rule + "_desc")
    return Label("other", "fallback")
