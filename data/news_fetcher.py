"""
data/news_fetcher.py — Crypto news from 100% FREE sources.

CryptoPanic free API discontinued April 2026.
Replaced with 3 zero-cost alternatives:

  1. CoinDesk RSS        — Professional crypto journalism
  2. Cointelegraph RSS   — High volume crypto news
  3. Decrypt RSS         — Quality crypto/web3 news
  4. The Block RSS       — Institutional-grade news
  5. Binance Announcements RSS — Listings/delistings (unchanged)

All RSS feeds — zero API keys, zero cost, no rate limits.
NLP sentiment scoring via TextBlob replaces community vote ratio.
"""
import asyncio
import feedparser
import httpx
from loguru import logger

from config import CACHE_NEWS
from utils.cache import cache_get, cache_set
from utils.rate_limiter import RSS_LIMITER
from utils.nlp_helper import combined_score, sentiment_score


# ═══════════════════════════════════════════
# FREE RSS NEWS SOURCES (replacing CryptoPanic)
# ═══════════════════════════════════════════
NEWS_RSS_FEEDS = {
    "coindesk":      "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "cointelegraph": "https://cointelegraph.com/rss",
    "decrypt":       "https://decrypt.co/feed",
    "theblock":      "https://www.theblock.co/rss.xml",
    "bitcoinmagazine": "https://bitcoinmagazine.com/.rss/full/",
}

BINANCE_RSS = "https://www.binance.com/en/support/announcement/rss"

# Coin symbol → keywords to filter coin-specific news
COIN_KEYWORDS = {
    "BTCUSDT":  ["bitcoin", "btc", "satoshi", "lightning network", "halving"],
    "ETHUSDT":  ["ethereum", "eth", "vitalik", "eip", "dencun", "pectra"],
    "SOLUSDT":  ["solana", "sol", "phantom", "jito"],
    "BNBUSDT":  ["binance", "bnb", "bnb chain", "bsc"],
    "AVAXUSDT": ["avalanche", "avax", "subnet"],
    "ADAUSDT":  ["cardano", "ada", "iohk", "hoskinson"],
    "DOTUSDT":  ["polkadot", "dot", "parachain", "gavin wood"],
    "LINKUSDT": ["chainlink", "link", "oracle"],
    "SOLUSDT":  ["solana", "sol"],
    "NEARUSDT": ["near protocol", "near"],
    "ARBUSDT":  ["arbitrum", "arb"],
    "OPUSDT":   ["optimism", "op "],
}


async def _fetch_rss_feed(source_name: str, url: str) -> list:
    """Fetch and parse a single RSS feed. Returns raw entries."""
    await RSS_LIMITER.acquire()
    try:
        feed = await asyncio.get_event_loop().run_in_executor(
            None, feedparser.parse, url
        )
        if feed.bozo and not feed.entries:
            logger.debug(f"RSS parse warning for {source_name}: {feed.bozo_exception}")
        return feed.entries[:25]
    except Exception as e:
        logger.debug(f"RSS fetch error ({source_name}): {e}")
        return []


def _parse_entry(entry: object, source: str) -> dict:
    """Parse a feedparser entry into a normalized news item."""
    title   = entry.get("title", "").strip()
    summary = entry.get("summary", entry.get("description", "")).strip()
    link    = entry.get("link", "")
    published = entry.get("published", "")

    # Strip HTML tags from summary
    import re
    summary_clean = re.sub(r"<[^>]+>", " ", summary).strip()

    full_text = f"{title} {summary_clean}"
    nlp = combined_score(full_text)
    recency = _recency_weight(published)

    return {
        "title":            title,
        "summary":          summary_clean[:200],
        "published_at":     published,
        "link":             link,
        "source":           source,
        "sentiment":        nlp["final"],
        "recency_weight":   recency,
        "weighted_sentiment": nlp["final"] * recency,
        "bearish_keywords": nlp["bearish_keywords"],
        "bullish_keywords": nlp["bullish_keywords"],
        "has_emergency":    nlp["has_emergency"],
        # No community votes anymore — NLP is primary
        "vote_ratio":       0.5 + (nlp["final"] * 0.5),  # synthetic proxy
    }


async def fetch_all_news_rss() -> list:
    """
    Fetch all news RSS feeds in parallel.
    Returns deduplicated list of news items sorted by recency.
    """
    cache_key = "news:rss:all"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    # Fetch all feeds simultaneously
    tasks = [
        _fetch_rss_feed(name, url)
        for name, url in NEWS_RSS_FEEDS.items()
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_items = []
    seen_titles = set()

    for source_name, entries in zip(NEWS_RSS_FEEDS.keys(), results):
        if isinstance(entries, Exception):
            logger.debug(f"Feed {source_name} failed: {entries}")
            continue
        for entry in entries:
            item = _parse_entry(entry, source_name)
            if not item["title"]:
                continue
            # Deduplicate by title similarity (first 60 chars)
            title_key = item["title"][:60].lower()
            if title_key in seen_titles:
                continue
            seen_titles.add(title_key)
            all_items.append(item)

    # Sort by recency weight (freshest first)
    all_items.sort(key=lambda x: x["recency_weight"], reverse=True)

    cache_set(cache_key, all_items, CACHE_NEWS)
    logger.info(f"News RSS: fetched {len(all_items)} items from {len(NEWS_RSS_FEEDS)} sources")
    return all_items


async def fetch_news_for_symbol(symbol: str) -> list:
    """
    Filter news items relevant to a specific coin.
    Uses keyword matching on title + summary.
    """
    all_news = await fetch_all_news_rss()

    keywords = COIN_KEYWORDS.get(symbol, [])
    if not keywords:
        # Fallback: use coin name from symbol
        coin = symbol.replace("USDT", "").lower()
        keywords = [coin]

    relevant = []
    for item in all_news:
        text = (item["title"] + " " + item["summary"]).lower()
        if any(kw in text for kw in keywords):
            relevant.append(item)

    # Always include general market news (top 5 most recent)
    general = [i for i in all_news if i not in relevant][:5]

    return relevant + general


# Keep this name so sentiment_scorer.py import doesn't break
async def fetch_cryptopanic(symbol: str = None, filter_type: str = "trending") -> list:
    """
    Drop-in replacement for the old fetch_cryptopanic().
    Now fetches from free RSS feeds instead.
    CryptoPanic free API was discontinued April 1, 2026.
    """
    if symbol:
        return await fetch_news_for_symbol(symbol)
    else:
        return await fetch_all_news_rss()


async def fetch_binance_announcements() -> list:
    """
    Monitor Binance announcements RSS for listings/delistings.
    Unchanged — Binance RSS is still free and working.
    """
    cache_key = "binance:rss"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    await RSS_LIMITER.acquire()

    try:
        feed = await asyncio.get_event_loop().run_in_executor(
            None, feedparser.parse, BINANCE_RSS
        )
    except Exception as e:
        logger.warning(f"Binance RSS error: {e}")
        return []

    items = []
    for entry in feed.entries[:20]:
        title     = entry.get("title", "")
        summary   = entry.get("summary", "")
        link      = entry.get("link", "")
        published = entry.get("published", "")

        title_lower = (title + " " + summary).lower()

        is_listing   = any(kw in title_lower for kw in
                           ["will list", "lists", "trading pairs",
                            "new listing", "opens trading", "adds"])
        is_delisting = any(kw in title_lower for kw in
                           ["delist", "remove", "discontinue", "removal"])
        is_update    = any(kw in title_lower for kw in
                           ["maintenance", "update", "upgrade", "scheduled"])

        if is_listing:
            signal_type   = "LISTING"
            score_override = 2.0
        elif is_delisting:
            signal_type   = "DELISTING"
            score_override = -2.0
        elif is_update:
            signal_type   = "UPDATE"
            score_override = 0.0
        else:
            signal_type   = "GENERAL"
            score_override = None

        items.append({
            "title":         title,
            "published":     published,
            "link":          link,
            "signal_type":   signal_type,
            "score_override": score_override,
            "source":        "binance_rss",
        })

    cache_set(cache_key, items, CACHE_NEWS)
    return items


def aggregate_news_score(news_items: list) -> dict:
    """
    Aggregate news items into a single pipeline score.
    Emergency bearish keywords override everything else.
    """
    if not news_items:
        return {
            "score": 0.0,
            "emergency": False,
            "emergency_reason": None,
            "summary": [],
        }

    # Emergency check first — one hack headline kills everything
    emergency_items = [n for n in news_items if n.get("has_emergency")]
    if emergency_items:
        worst = sorted(emergency_items, key=lambda x: x["sentiment"])[0]
        return {
            "score":             -2.0,
            "emergency":         True,
            "emergency_reason":  worst["title"],
            "emergency_keywords": worst.get("bearish_keywords", []),
            "summary":           [n["title"] for n in news_items[:3]],
        }

    # Weighted average (recency × sentiment)
    total_weight = sum(n.get("recency_weight", 1.0) for n in news_items)
    if total_weight == 0:
        return {"score": 0.0, "emergency": False,
                "emergency_reason": None, "summary": []}

    weighted_sum = sum(
        n.get("weighted_sentiment", n.get("sentiment", 0))
        for n in news_items
    )

    avg_score = weighted_sum / total_weight
    scaled    = avg_score * 4   # [-1,+1] → [-4,+4]

    # Top 3 headlines sorted by freshness
    top_headlines = [
        n["title"] for n in sorted(
            news_items,
            key=lambda x: x.get("recency_weight", 1.0),
            reverse=True,
        )[:3]
    ]

    # Source breakdown for transparency
    sources_used = list({n["source"] for n in news_items})

    return {
        "score":           max(-4.0, min(4.0, scaled)),
        "emergency":       False,
        "emergency_reason": None,
        "avg_sentiment":   round(avg_score, 3),
        "sources":         sources_used,
        "item_count":      len(news_items),
        "summary":         top_headlines,
    }


def _recency_weight(published_at: str) -> float:
    """
    Newer news = higher weight.
    <1h = 3×  |  <6h = 2×  |  <24h = 1×  |  older = 0.3×
    """
    import datetime
    try:
        import pytz
        from email.utils import parsedate_to_datetime
        try:
            dt = parsedate_to_datetime(published_at)
        except Exception:
            from dateutil import parser as dp
            dt = dp.parse(published_at)

        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)

        age_hours = (
            datetime.datetime.now(pytz.UTC) - dt
        ).total_seconds() / 3600

        if age_hours < 1:   return 3.0
        if age_hours < 6:   return 2.0
        if age_hours < 24:  return 1.0
        return 0.3

    except Exception:
        return 1.0
