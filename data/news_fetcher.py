"""
data/news_fetcher.py — News fetching from CryptoPanic and Binance RSS.

CryptoPanic provides community-voted crypto news with bullish/bearish votes.
Binance announcements RSS alerts on listings/delistings.
"""
import asyncio
import feedparser
import httpx
from loguru import logger

from config import CRYPTOPANIC_API_KEY, CRYPTOPANIC_BASE_URL, CACHE_NEWS
from utils.cache import cache_get, cache_set
from utils.rate_limiter import CRYPTOPANIC_LIMITER, RSS_LIMITER
from utils.nlp_helper import combined_score


BINANCE_RSS = "https://www.binance.com/en/support/announcement/rss"


async def fetch_cryptopanic(symbol: str = None, filter_type: str = "trending") -> list:
    """
    Fetch recent crypto news from CryptoPanic.
    Includes community vote ratio (bullish/bearish).

    symbol: filter by specific coin (e.g. "BTC"). None = general market.
    filter_type: 'trending' | 'hot' | 'important' | 'bullish' | 'bearish'

    Returns list of news items with sentiment scores.
    """
    coin_slug = None
    if symbol:
        coin_map = {
            "BTCUSDT": "BTC", "ETHUSDT": "ETH", "SOLUSDT": "SOL",
            "BNBUSDT": "BNB", "AVAXUSDT": "AVAX", "ADAUSDT": "ADA",
        }
        coin_slug = coin_map.get(symbol, symbol.replace("USDT", ""))

    cache_key = f"cryptopanic:{coin_slug or 'market'}:{filter_type}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    await CRYPTOPANIC_LIMITER.acquire()

    params = {
        "auth_token": CRYPTOPANIC_API_KEY or "free_tier",
        "public": "true",
        "filter": filter_type,
        "kind": "news",
        "limit": 20,
    }
    if coin_slug:
        params["currencies"] = coin_slug

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            url = f"{CRYPTOPANIC_BASE_URL}/posts/"
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning(f"CryptoPanic error: {e}")
        return []

    news_items = []
    for item in data.get("results", [])[:20]:
        title  = item.get("title", "")
        votes  = item.get("votes", {})
        created = item.get("published_at", "")

        positive_votes = votes.get("positive", 0)
        negative_votes = votes.get("negative", 0)
        total_votes    = positive_votes + negative_votes

        # Vote ratio: 0-1, 0.5 = neutral, >0.65 = bullish, <0.35 = bearish
        vote_ratio = positive_votes / total_votes if total_votes > 0 else 0.5

        # NLP fallback if no votes
        nlp = combined_score(title)

        if total_votes > 5:
            # Use vote ratio as primary signal
            sentiment = (vote_ratio - 0.5) * 2  # Normalize to -1..+1
        else:
            # Fall back to NLP
            sentiment = nlp["final"]

        # Recency weighting
        recency_weight = _recency_weight(created)

        news_items.append({
            "title": title,
            "published_at": created,
            "vote_ratio": vote_ratio,
            "positive_votes": positive_votes,
            "negative_votes": negative_votes,
            "sentiment": sentiment,
            "recency_weight": recency_weight,
            "weighted_sentiment": sentiment * recency_weight,
            "bearish_keywords": nlp["bearish_keywords"],
            "bullish_keywords": nlp["bullish_keywords"],
            "has_emergency": nlp["has_emergency"],
            "source": "cryptopanic",
        })

    cache_set(cache_key, news_items, CACHE_NEWS)
    return news_items


def _recency_weight(published_at: str) -> float:
    """
    Newer news = higher weight.
    <1 hour = 3x, <6 hours = 2x, <24 hours = 1x, older = 0.3x
    """
    import datetime
    try:
        from dateutil import parser as dateutil_parser
        dt = dateutil_parser.parse(published_at)
        if dt.tzinfo is None:
            import pytz
            dt = pytz.UTC.localize(dt)
        age_hours = (datetime.datetime.now(pytz.UTC) - dt).total_seconds() / 3600

        if age_hours < 1:
            return 3.0
        elif age_hours < 6:
            return 2.0
        elif age_hours < 24:
            return 1.0
        else:
            return 0.3
    except Exception:
        return 1.0


async def fetch_binance_announcements() -> list:
    """
    Monitor Binance announcements RSS for listings/delistings.

    Binance listing = instant +2 bullish signal for that coin.
    Delisting = instant -2 bearish signal.
    """
    cache_key = "binance:rss"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    await RSS_LIMITER.acquire()

    try:
        # feedparser can be slow, run in thread
        import asyncio
        feed = await asyncio.get_event_loop().run_in_executor(
            None, feedparser.parse, BINANCE_RSS
        )
    except Exception as e:
        logger.warning(f"Binance RSS error: {e}")
        return []

    items = []
    for entry in feed.entries[:20]:
        title   = entry.get("title", "")
        summary = entry.get("summary", "")
        link    = entry.get("link", "")
        published = entry.get("published", "")

        title_lower = (title + " " + summary).lower()

        # Detect announcement type
        is_listing = any(kw in title_lower for kw in
                         ["will list", "lists", "trading pairs", "new listing", "opens trading"])
        is_delisting = any(kw in title_lower for kw in
                           ["delist", "remove", "discontinue"])
        is_update = any(kw in title_lower for kw in
                        ["maintenance", "update", "upgrade", "scheduled"])

        if is_listing:
            signal_type = "LISTING"
            score_override = 2.0
        elif is_delisting:
            signal_type = "DELISTING"
            score_override = -2.0
        elif is_update:
            signal_type = "UPDATE"
            score_override = 0.0
        else:
            signal_type = "GENERAL"
            score_override = None

        items.append({
            "title": title,
            "published": published,
            "link": link,
            "signal_type": signal_type,
            "score_override": score_override,
            "source": "binance_rss",
        })

    cache_set(cache_key, items, CACHE_NEWS)
    return items


def aggregate_news_score(news_items: list) -> dict:
    """
    Aggregate multiple news items into a single score.
    Emergency (bearish keyword) overrides everything.
    """
    if not news_items:
        return {"score": 0.0, "emergency": False, "emergency_reason": None, "summary": []}

    # Check for emergency first
    emergency_items = [n for n in news_items if n.get("has_emergency")]
    if emergency_items:
        worst = sorted(emergency_items, key=lambda x: x["sentiment"])[0]
        return {
            "score": -2.0,
            "emergency": True,
            "emergency_reason": worst["title"],
            "emergency_keywords": worst.get("bearish_keywords", []),
            "summary": [n["title"] for n in news_items[:3]],
        }

    # Weighted average by recency
    total_weight = sum(n.get("recency_weight", 1) for n in news_items)
    if total_weight == 0:
        return {"score": 0.0, "emergency": False, "emergency_reason": None, "summary": []}

    weighted_sum = sum(
        n.get("weighted_sentiment", n.get("sentiment", 0))
        for n in news_items
    )

    avg_score = weighted_sum / total_weight
    # Scale from [-1,1] to [-4,+4] for pipeline range
    scaled = avg_score * 4

    return {
        "score": max(-4, min(4, scaled)),
        "emergency": False,
        "emergency_reason": None,
        "avg_vote_ratio": sum(n.get("vote_ratio", 0.5) for n in news_items) / len(news_items),
        "summary": [n["title"] for n in sorted(
            news_items, key=lambda x: x.get("recency_weight", 1), reverse=True
        )[:3]],
    }
