"""
data/fear_greed_fetcher.py — Alternative.me Fear & Greed Index.

Free, no API key needed.
Contrarian indicator: extreme fear = buy signal, extreme greed = sell signal.
Willy Woo and many quants use sentiment as a contrarian tool.
"""
import httpx
from loguru import logger
from config import FEAR_GREED_URL, FEAR_EXTREME, FEAR, GREED, GREED_EXTREME
from utils.cache import cache_get, cache_set
from utils.rate_limiter import FEAR_GREED_LIMITER


async def fetch_fear_greed() -> dict:
    """
    Returns current Fear & Greed index with interpretation.

    Score 0-100:
      0-25  = Extreme Fear   → contrarian BULLISH
      25-45 = Fear           → mild bullish
      45-55 = Neutral
      55-75 = Greed          → mild bearish
      75-100 = Extreme Greed → contrarian BEARISH

    Also returns yesterday's score for momentum detection.
    A 15+ point swing in 24h = significant sentiment shift.
    """
    cached = cache_get("fear_greed")
    if cached is not None:
        return cached

    await FEAR_GREED_LIMITER.acquire()

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(FEAR_GREED_URL)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning(f"Fear & Greed fetch error: {e}")
        return _default_response()

    entries = data.get("data", [])
    if len(entries) < 1:
        return _default_response()

    current = entries[0]
    yesterday = entries[1] if len(entries) > 1 else current

    current_value  = int(current.get("value", 50))
    yesterday_value = int(yesterday.get("value", 50))
    change_24h = current_value - yesterday_value

    interpretation = _interpret(current_value)
    signal_score = _to_signal_score(current_value)

    # Large 24h swing = momentum shift detection
    momentum_shift = abs(change_24h) >= 15
    if momentum_shift:
        shift_direction = "BULLISH shift" if change_24h > 0 else "BEARISH shift"
    else:
        shift_direction = None

    result = {
        "value": current_value,
        "label": current.get("value_classification", "Neutral"),
        "yesterday": yesterday_value,
        "change_24h": change_24h,
        "signal_score": signal_score,  # -1 to +1
        "interpretation": interpretation,
        "momentum_shift": momentum_shift,
        "shift_direction": shift_direction,
    }

    cache_set("fear_greed", result, 3600)  # 1 hour — it only updates daily
    logger.info(f"Fear & Greed: {current_value} ({result['label']}) signal={signal_score:+.1f}")
    return result


def _interpret(value: int) -> str:
    if value <= FEAR_EXTREME:
        return "EXTREME_FEAR"
    elif value <= FEAR:
        return "FEAR"
    elif value <= GREED:
        return "NEUTRAL"
    elif value <= GREED_EXTREME:
        return "GREED"
    else:
        return "EXTREME_GREED"


def _to_signal_score(value: int) -> float:
    """
    Convert 0-100 F&G value to -1 to +1 signal score.
    Inverted because it's a contrarian indicator:
    extreme fear = strong buy, extreme greed = strong sell.
    """
    if value <= 25:
        return 1.0   # Extreme fear = contrarian long
    elif value <= 45:
        return 0.5   # Fear = mild long
    elif value <= 55:
        return 0.0   # Neutral
    elif value <= 75:
        return -0.5  # Greed = mild short
    else:
        return -1.0  # Extreme greed = contrarian short


def _default_response() -> dict:
    return {
        "value": 50,
        "label": "Neutral",
        "yesterday": 50,
        "change_24h": 0,
        "signal_score": 0.0,
        "interpretation": "NEUTRAL",
        "momentum_shift": False,
        "shift_direction": None,
    }
