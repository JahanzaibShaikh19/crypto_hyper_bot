"""
data/macro_calendar.py — Economic calendar via TradingEconomics RSS.

Pipeline 5 (Events/Macro) is the most differentiated pipeline —
most bots ignore this entirely. Macro events move crypto MORE than
any indicator. CPI surprise = ±5% BTC in hours.

Uses TradingEconomics RSS which is free and doesn't require auth.
Also scrapes Investing.com calendar as backup.
"""
import asyncio
import re
import feedparser
import httpx
from datetime import datetime, timedelta
from loguru import logger

from utils.cache import cache_get, cache_set
from utils.rate_limiter import RSS_LIMITER, SCRAPE_LIMITER


TRADINGECONOMICS_CALENDAR_RSS = (
    "https://tradingeconomics.com/rss/calendar.aspx"
)

INVESTING_CALENDAR_URL = (
    "https://www.investing.com/economic-calendar/"
)

# High-impact events we track
HIGH_IMPACT_EVENTS = [
    "cpi", "consumer price index",
    "ppi", "producer price index",
    "fomc", "federal reserve", "fed rate",
    "interest rate decision",
    "non-farm payroll", "nfp", "jobs report",
    "gdp",
    "pce", "personal consumption",
    "ecb rate",
    "unemployment",
]

# Event impact mapping: event name pattern -> (crypto impact direction, magnitude)
EVENT_IMPACT = {
    # If CPI comes in LOWER than expected = Fed may pause = BULLISH crypto
    "cpi": {"low": ("BULLISH", 2.0), "high": ("BEARISH", 2.0)},
    "ppi": {"low": ("BULLISH", 1.5), "high": ("BEARISH", 1.5)},
    # Rate cut/pause = bullish, hike = bearish
    "rate cut": ("BULLISH", 2.5),
    "rate pause": ("BULLISH", 2.0),
    "rate hike": ("BEARISH", 2.0),
    # Strong jobs = Fed hawkish = bearish crypto
    "nfp": {"strong": ("BEARISH", 1.0), "weak": ("BULLISH", 1.0)},
    # GDP
    "gdp": {"beat": ("BULLISH", 0.5), "miss": ("BEARISH", 0.5)},
}


async def fetch_trading_economics_rss() -> list:
    """
    Fetch economic calendar from TradingEconomics RSS.
    Returns upcoming high-impact events for US market.
    """
    cached = cache_get("macro:te_rss")
    if cached is not None:
        return cached

    await RSS_LIMITER.acquire()

    try:
        feed = await asyncio.get_event_loop().run_in_executor(
            None, feedparser.parse, TRADINGECONOMICS_CALENDAR_RSS
        )
    except Exception as e:
        logger.warning(f"TradingEconomics RSS error: {e}")
        return []

    events = []
    for entry in feed.entries[:50]:
        title    = entry.get("title", "").lower()
        summary  = entry.get("summary", "").lower()
        published = entry.get("published", "")

        is_high_impact = any(kw in title or kw in summary
                             for kw in HIGH_IMPACT_EVENTS)
        is_us = any(x in title or x in summary
                    for x in ["united states", "us ", "federal", "fomc", "nfp"])

        if not is_high_impact:
            continue

        events.append({
            "title": entry.get("title", ""),
            "summary": entry.get("summary", ""),
            "published": published,
            "is_high_impact": is_high_impact,
            "is_us": is_us,
            "source": "tradingeconomics",
        })

    cache_set("macro:te_rss", events, 3600)  # 1 hour cache
    return events


async def parse_recent_macro_events() -> list:
    """
    Parse recent economic releases and determine their crypto impact.
    Returns list of processed events with score adjustments.
    """
    cached = cache_get("macro:processed")
    if cached is not None:
        return cached

    raw_events = await fetch_trading_economics_rss()

    processed = []
    for event in raw_events:
        text  = (event["title"] + " " + event["summary"]).lower()
        score = 0.0
        event_type = "UNKNOWN"

        # CPI analysis
        if "cpi" in text or "consumer price" in text:
            event_type = "CPI"
            if "lower" in text or "below" in text or "cooled" in text or "fell" in text:
                score = 2.0   # Cool inflation = bullish crypto
            elif "higher" in text or "above" in text or "hot" in text or "rose" in text:
                score = -2.0  # Hot inflation = hawkish Fed = bearish

        # Fed rate decisions
        elif "rate" in text and ("cut" in text or "lower" in text or "pause" in text):
            event_type = "FED_DOVISH"
            score = 2.5  # Fed cutting = massive liquidity = crypto bullish
        elif "rate" in text and ("hike" in text or "increase" in text or "raise" in text):
            event_type = "FED_HAWKISH"
            score = -2.0

        # Jobs / NFP
        elif "nfp" in text or "non-farm" in text or "payroll" in text:
            event_type = "NFP"
            if "strong" in text or "beat" in text or "above" in text:
                score = -1.0  # Strong jobs = Fed stays hawkish
            elif "weak" in text or "missed" in text or "below" in text:
                score = 1.0   # Weak jobs = Fed may cut

        # GDP
        elif "gdp" in text:
            event_type = "GDP"
            if "beat" in text or "strong" in text:
                score = 0.5
            elif "missed" in text or "weak" in text or "contracted" in text:
                score = -0.5

        if event_type != "UNKNOWN":
            processed.append({
                **event,
                "event_type": event_type,
                "crypto_score": score,
                "summary_short": event["title"][:80],
            })

    cache_set("macro:processed", processed, 3600)
    return processed


def get_next_fomc_estimate() -> dict:
    """
    Estimate days until next FOMC meeting.
    FOMC meets roughly every 6 weeks.
    Returns warning if meeting is within 5 days.
    """
    # Approximate 2024-2025 FOMC schedule
    # In production, scrape from federalreserve.gov
    known_fomc_dates = [
        datetime(2025, 1, 29),
        datetime(2025, 3, 19),
        datetime(2025, 5, 7),
        datetime(2025, 6, 18),
        datetime(2025, 7, 30),
        datetime(2025, 9, 17),
        datetime(2025, 10, 29),
        datetime(2025, 12, 10),
        datetime(2026, 1, 28),
        datetime(2026, 3, 18),
        datetime(2026, 5, 6),
        datetime(2026, 6, 17),
    ]

    now = datetime.utcnow()
    future_dates = [d for d in known_fomc_dates if d > now]

    if not future_dates:
        return {"days_away": 999, "date": "Unknown", "warning": False}

    next_date = min(future_dates)
    days_away = (next_date - now).days

    return {
        "days_away": days_away,
        "date": next_date.strftime("%b %d, %Y"),
        "warning": days_away <= 5,
        "warning_text": f"⚠️ FOMC in {days_away} days — expect volatility" if days_away <= 5 else None,
        "risk_score": -0.5 if days_away <= 5 else 0.0,  # Caution near FOMC
    }
