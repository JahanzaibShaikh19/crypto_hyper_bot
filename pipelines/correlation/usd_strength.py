"""
pipelines/correlation/usd_strength.py — USD strength proxy (DXY).

Raoul Pal's framework: "Macro liquidity cycle drives ALL crypto moves."
When USD is strong, risk assets suffer. When USD weakens, liquidity
flows into crypto, equities, commodities.

We don't have a free DXY feed, so we:
1. Try TradingEconomics RSS for DXY mentions
2. Use USDT premium/discount as proxy
3. Default to neutral if unavailable
"""
import asyncio
import feedparser
import re
from loguru import logger
from utils.cache import cache_get, cache_set
from utils.rate_limiter import RSS_LIMITER

TRADING_ECONOMICS_DXY_URL = "https://tradingeconomics.com/rss/news.aspx?i=united+states+dollar"

# DXY thresholds
DXY_VERY_BEARISH_CRYPTO = 105   # Strong USD = bad for crypto
DXY_BEARISH_CRYPTO      = 103
DXY_NEUTRAL_LOWER       = 100
DXY_BULLISH_CRYPTO      = 100   # Weak USD = good for crypto
DXY_VERY_BULLISH_CRYPTO = 97


async def fetch_dxy_proxy() -> dict:
    """
    Try to get DXY level/direction from TradingEconomics RSS.
    Falls back to neutral if unavailable.
    """
    cached = cache_get("dxy:proxy")
    if cached is not None:
        return cached

    await RSS_LIMITER.acquire()

    dxy_value    = None
    dxy_change   = None
    dxy_direction = "NEUTRAL"

    try:
        feed = await asyncio.get_event_loop().run_in_executor(
            None, feedparser.parse, TRADING_ECONOMICS_DXY_URL
        )
        for entry in feed.entries[:5]:
            text = entry.get("title", "") + " " + entry.get("summary", "")
            # Look for DXY value like "102.34" or "dollar index 103"
            matches = re.findall(r'(?:dxy|dollar index|usd index)[^\d]*(\d{2,3}\.?\d{0,2})',
                                  text.lower())
            if matches:
                dxy_value = float(matches[0])
                # Direction from text
                if any(w in text.lower() for w in ["rises", "gains", "higher", "up"]):
                    dxy_direction = "RISING"
                elif any(w in text.lower() for w in ["falls", "drops", "lower", "down"]):
                    dxy_direction = "FALLING"
                break
    except Exception as e:
        logger.debug(f"DXY RSS error: {e}")

    # If we got a value, score it; otherwise neutral
    if dxy_value:
        score = _score_dxy(dxy_value, dxy_direction)
    else:
        score = {"score": 0.0, "level": "UNKNOWN", "note": "DXY unavailable — neutral assumed"}

    score["dxy_value"] = dxy_value
    score["dxy_direction"] = dxy_direction

    cache_set("dxy:proxy", score, 3600)
    return score


def _score_dxy(value: float, direction: str) -> dict:
    """Score DXY for crypto impact."""
    if value >= DXY_VERY_BEARISH_CRYPTO:
        base_score = -1.0
        level = "VERY_STRONG_USD"
        note = f"DXY {value:.1f} — very strong USD, bearish crypto macro"
    elif value >= DXY_BEARISH_CRYPTO:
        base_score = -0.5
        level = "STRONG_USD"
        note = f"DXY {value:.1f} — strong USD, headwind for crypto"
    elif value <= DXY_VERY_BULLISH_CRYPTO:
        base_score = 1.0
        level = "WEAK_USD"
        note = f"DXY {value:.1f} — weak USD, tailwind for crypto"
    elif value <= DXY_BULLISH_CRYPTO:
        base_score = 0.5
        level = "MILDLY_WEAK_USD"
        note = f"DXY {value:.1f} — mild USD weakness"
    else:
        base_score = 0.0
        level = "NEUTRAL_USD"
        note = f"DXY {value:.1f} — neutral range"

    # Direction modifier
    if direction == "RISING":
        base_score -= 0.3   # USD strengthening = bad for crypto
    elif direction == "FALLING":
        base_score += 0.3   # USD weakening = good for crypto

    return {
        "score": round(max(-1.0, min(1.0, base_score)), 3),
        "level": level,
        "note": note,
    }
