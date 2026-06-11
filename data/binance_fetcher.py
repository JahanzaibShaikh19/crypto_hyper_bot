"""
data/binance_fetcher.py — All Binance public API data.

Fetches:
  - OHLCV candles for any pair/timeframe
  - Funding rate (derivatives sentiment)
  - Open interest (OI) and OI change
  - Recent liquidations
  - 24h ticker stats

All endpoints are PUBLIC — no API key required for these.
Binance public rate limit: 1200 req/min weight. We stay way under.
"""
import asyncio
from typing import Optional
import httpx
import pandas as pd
import numpy as np
from loguru import logger

from config import BINANCE_BASE_URL, CACHE_OHLCV, CANDLES_LIMIT
from utils.cache import cache_get, cache_set
from utils.rate_limiter import BINANCE_LIMITER


async def _get(url: str, params: dict = None, timeout: int = 15) -> Optional[dict | list]:
    """Low-level async GET with rate limiting and error handling."""
    await BINANCE_LIMITER.acquire()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        logger.warning(f"Binance HTTP {e.response.status_code}: {url}")
    except Exception as e:
        logger.warning(f"Binance request error: {e} — {url}")
    return None


async def fetch_ohlcv(symbol: str, interval: str, limit: int = CANDLES_LIMIT) -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV candlestick data.

    Returns DataFrame with columns: open_time, open, high, low, close,
    volume, close_time, quote_volume, trades, taker_buy_base, taker_buy_quote.

    4H candles are Pentoshi's HTF structure — most important.
    """
    cache_key = f"ohlcv:{symbol}:{interval}:{limit}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    url = f"{BINANCE_BASE_URL}/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}

    data = await _get(url, params)
    if not data:
        return None

    df = pd.DataFrame(data, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades",
        "taker_buy_base", "taker_buy_quote", "ignore"
    ])

    # Convert types — Binance returns strings
    for col in ["open", "high", "low", "close", "volume",
                "quote_volume", "taker_buy_base", "taker_buy_quote"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["trades"] = pd.to_numeric(df["trades"], errors="coerce").astype(int)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
    df.drop(columns=["ignore"], inplace=True)
    df.set_index("open_time", inplace=True)
    df.sort_index(inplace=True)

    cache_set(cache_key, df, CACHE_OHLCV)
    logger.debug(f"OHLCV fetched: {symbol} {interval} ({len(df)} candles)")
    return df


async def fetch_funding_rate(symbol: str) -> Optional[dict]:
    """
    Fetch current funding rate for a USDT perpetual.

    Arthur Hayes: "Funding rate reveals who is over-leveraged."
    Positive funding = longs paying shorts (longs crowded)
    Negative funding = shorts paying longs (shorts crowded)
    """
    cache_key = f"funding:{symbol}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    url = f"{BINANCE_BASE_URL}/fapi/v1/premiumIndex"
    # Convert spot symbol to perp format if needed
    perp_symbol = symbol.replace("USDT", "USDT") if "USDT" in symbol else symbol

    data = await _get(url, {"symbol": perp_symbol})
    if not data:
        return {"funding_rate": 0.0, "mark_price": 0.0, "index_price": 0.0}

    result = {
        "funding_rate": float(data.get("lastFundingRate", 0)),
        "mark_price": float(data.get("markPrice", 0)),
        "index_price": float(data.get("indexPrice", 0)),
        "next_funding_time": data.get("nextFundingTime"),
        "symbol": symbol,
    }

    cache_set(cache_key, result, 300)  # 5 min cache for funding
    return result


async def fetch_open_interest(symbol: str) -> Optional[dict]:
    """
    Fetch current open interest for perpetual futures.

    Rising OI + rising price = strong trend (real buying)
    Rising OI + falling price = strong downtrend
    Falling OI + rising price = weak rally (short covering)
    """
    cache_key = f"oi:{symbol}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    # Current OI
    url = f"{BINANCE_BASE_URL}/fapi/v1/openInterest"
    data = await _get(url, {"symbol": symbol})

    if not data:
        return {"oi": 0.0, "oi_change_pct": 0.0}

    current_oi = float(data.get("openInterest", 0))

    # Historical OI for change calculation
    hist_url = f"{BINANCE_BASE_URL}/futures/data/openInterestHist"
    hist_data = await _get(hist_url, {
        "symbol": symbol,
        "period": "1h",
        "limit": 24,
    })

    oi_change_pct = 0.0
    if hist_data and len(hist_data) >= 2:
        oldest = float(hist_data[0].get("sumOpenInterest", current_oi))
        if oldest > 0:
            oi_change_pct = ((current_oi - oldest) / oldest) * 100

    result = {
        "oi": current_oi,
        "oi_change_pct": oi_change_pct,
        "oi_change_direction": "rising" if oi_change_pct > 2 else
                               "falling" if oi_change_pct < -2 else "neutral",
    }

    cache_set(cache_key, result, 600)  # 10 min
    return result


async def fetch_liquidations(symbol: str) -> Optional[dict]:
    """
    Fetch recent liquidation data.

    Large liquidation cascades = reversal signal.
    After mass short liquidations = short squeeze potential
    After mass long liquidations = bounce potential
    """
    cache_key = f"liq:{symbol}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    url = f"{BINANCE_BASE_URL}/fapi/v1/allForceOrders"
    data = await _get(url, {"symbol": symbol, "limit": 100})

    if not data:
        return {"long_liq_value": 0, "short_liq_value": 0, "cascade_detected": False}

    long_liq = sum(float(x.get("origQty", 0)) * float(x.get("price", 0))
                   for x in data if x.get("side") == "SELL")
    short_liq = sum(float(x.get("origQty", 0)) * float(x.get("price", 0))
                    for x in data if x.get("side") == "BUY")

    # Cascade if >$10M liquidated in one side recently
    cascade_detected = (long_liq > 10_000_000) or (short_liq > 10_000_000)

    result = {
        "long_liq_value": long_liq,
        "short_liq_value": short_liq,
        "cascade_detected": cascade_detected,
        "dominant_side": "LONGS" if long_liq > short_liq else "SHORTS",
    }

    cache_set(cache_key, result, 300)
    return result


async def fetch_ticker_24h(symbol: str) -> Optional[dict]:
    """24h price statistics."""
    cache_key = f"ticker24h:{symbol}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    url = f"{BINANCE_BASE_URL}/api/v3/ticker/24hr"
    data = await _get(url, {"symbol": symbol})

    if not data:
        return None

    result = {
        "price": float(data.get("lastPrice", 0)),
        "change_pct": float(data.get("priceChangePercent", 0)),
        "high": float(data.get("highPrice", 0)),
        "low": float(data.get("lowPrice", 0)),
        "volume": float(data.get("volume", 0)),
        "quote_volume": float(data.get("quoteVolume", 0)),
        "trades": int(data.get("count", 0)),
    }

    cache_set(cache_key, result, 300)
    return result


async def fetch_all_for_symbol(symbol: str) -> dict:
    """
    Fetch all Binance data for a symbol in parallel.
    Returns consolidated dict for pipeline consumption.
    """
    results = await asyncio.gather(
        fetch_ohlcv(symbol, "15m"),
        fetch_ohlcv(symbol, "1h"),
        fetch_ohlcv(symbol, "4h"),
        fetch_ohlcv(symbol, "1d"),
        fetch_funding_rate(symbol),
        fetch_open_interest(symbol),
        fetch_ticker_24h(symbol),
        return_exceptions=True,
    )

    # Unpack, replace exceptions with None
    def safe(r):
        return None if isinstance(r, Exception) else r

    return {
        "ohlcv_15m": safe(results[0]),
        "ohlcv_1h":  safe(results[1]),
        "ohlcv_4h":  safe(results[2]),
        "ohlcv_1d":  safe(results[3]),
        "funding":   safe(results[4]) or {},
        "oi":        safe(results[5]) or {},
        "ticker":    safe(results[6]) or {},
    }
