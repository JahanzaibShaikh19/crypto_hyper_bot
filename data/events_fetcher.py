"""
data/events_fetcher.py — Coin-specific events calendar.

Tracks: token unlocks, coin burns, mainnet launches,
exchange listings, hard forks, partnerships.

Sources:
  - CoinGecko events endpoint (free tier)
  - CoinMarketCal RSS (free, no auth)
"""
import asyncio
import feedparser
import httpx
from loguru import logger

from config import COINGECKO_BASE_URL
from utils.cache import cache_get, cache_set
from utils.rate_limiter import COINGECKO_LIMITER, RSS_LIMITER


COINMARKETCAL_RSS = "https://coinmarketcal.com/en/rss/event"

# Event type to score mapping
EVENT_SCORES = {
    # Bearish (supply increase, uncertainty)
    "token_unlock":     -1.5,
    "vesting":          -1.5,
    "hard_fork_contentious": -1.0,
    "team_token_sale":  -2.0,

    # Bullish (demand increase, supply decrease)
    "coin_burn":        1.0,
    "mainnet_launch":   1.5,
    "major_upgrade":    1.0,
    "binance_listing":  2.0,
    "coinbase_listing": 1.5,
    "exchange_listing": 1.0,
    "partnership":      1.0,
    "integration":      0.8,
    "halving":          2.0,

    # Context-dependent
    "hard_fork": 0.5,
    "airdrop":   0.3,
}


async def fetch_coingecko_events(coin_id: str) -> list:
    """
    Fetch upcoming events for a specific coin from CoinGecko.
    """
    cache_key = f"cg:events:{coin_id}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    await COINGECKO_LIMITER.acquire()

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{COINGECKO_BASE_URL}/events",
                params={"coin_id": coin_id, "upcoming_events_only": "true"}
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.debug(f"CoinGecko events error: {e}")
        return []

    events = []
    for item in data.get("data", [])[:10]:
        event_type = item.get("type", "").lower()
        description = item.get("description", "")
        event_date  = item.get("starts_at", "")

        score = _score_event(event_type, description)

        events.append({
            "coin_id": coin_id,
            "type": event_type,
            "description": description[:200],
            "date": event_date,
            "score": score,
            "source": "coingecko",
        })

    cache_set(cache_key, events, 14400)  # 4 hour cache
    return events


async def fetch_coinmarketcal_rss() -> list:
    """
    Fetch upcoming events from CoinMarketCal RSS.
    Public RSS — no authentication needed.
    """
    cached = cache_get("cmc:events:rss")
    if cached is not None:
        return cached

    await RSS_LIMITER.acquire()

    try:
        feed = await asyncio.get_event_loop().run_in_executor(
            None, feedparser.parse, COINMARKETCAL_RSS
        )
    except Exception as e:
        logger.debug(f"CoinMarketCal RSS error: {e}")
        return []

    events = []
    for entry in feed.entries[:30]:
        title    = entry.get("title", "")
        summary  = entry.get("summary", "")
        published = entry.get("published", "")

        text = (title + " " + summary).lower()
        event_type = _detect_event_type(text)
        score = _score_event(event_type, text)

        # Extract coin symbol from title if possible
        import re
        symbol_match = re.search(r'\b([A-Z]{2,10})\b', title)
        symbol = symbol_match.group(1) if symbol_match else None

        events.append({
            "title": title,
            "summary": summary[:200],
            "date": published,
            "type": event_type,
            "score": score,
            "symbol": symbol,
            "source": "coinmarketcal",
        })

    cache_set("cmc:events:rss", events, 14400)
    return events


def _detect_event_type(text: str) -> str:
    """Detect event type from text."""
    text = text.lower()

    if any(kw in text for kw in ["unlock", "vesting", "cliff", "release tokens"]):
        return "token_unlock"
    elif any(kw in text for kw in ["burn", "burning", "buyback"]):
        return "coin_burn"
    elif any(kw in text for kw in ["mainnet", "launch", "go live"]):
        return "mainnet_launch"
    elif any(kw in text for kw in ["binance listing", "lists on binance"]):
        return "binance_listing"
    elif any(kw in text for kw in ["coinbase listing", "lists on coinbase"]):
        return "coinbase_listing"
    elif any(kw in text for kw in ["listing", "exchange"]):
        return "exchange_listing"
    elif any(kw in text for kw in ["partnership", "partner", "collaborate"]):
        return "partnership"
    elif any(kw in text for kw in ["upgrade", "hard fork", "fork"]):
        return "major_upgrade"
    elif any(kw in text for kw in ["halving", "halvening"]):
        return "halving"
    elif any(kw in text for kw in ["airdrop"]):
        return "airdrop"
    else:
        return "general"


def _score_event(event_type: str, description: str = "") -> float:
    """
    Score an event. Buy-the-rumor-sell-the-news detection:
    if price already pumped 30%+ for this event, flip sign.
    """
    base_score = EVENT_SCORES.get(event_type, 0.0)

    # "Buy the rumor sell the news" — if already pumped, reduce bullish
    if "already" in description.lower() or "priced in" in description.lower():
        base_score *= 0.3

    return base_score


def get_event_timing_score(event_date_str: str, base_score: float) -> dict:
    """
    Score depends on how close the event is.
    7 days before: half the score (rumor)
    1 day before: full score
    Day of: full score
    After event: sell-the-news — flip sign partially
    """
    import datetime
    try:
        from dateutil import parser as dp
        event_dt = dp.parse(event_date_str)
        if event_dt.tzinfo is None:
            import pytz
            event_dt = pytz.UTC.localize(event_dt)
        now = datetime.datetime.now(datetime.timezone.utc)
        days_until = (event_dt - now).days

        if days_until > 7:
            multiplier = 0.3
            phase = "FAR"
        elif days_until > 1:
            multiplier = 0.7
            phase = "APPROACHING"
        elif days_until >= 0:
            multiplier = 1.0
            phase = "IMMINENT"
        else:
            # Post-event: sell the news (flip positive scores, amplify negative)
            if base_score > 0:
                multiplier = -0.3
            else:
                multiplier = 1.2
            phase = "POST_EVENT"

        return {
            "days_until": days_until,
            "phase": phase,
            "adjusted_score": base_score * multiplier,
            "multiplier": multiplier,
        }
    except Exception:
        return {"days_until": 999, "phase": "UNKNOWN", "adjusted_score": 0.0, "multiplier": 0}
