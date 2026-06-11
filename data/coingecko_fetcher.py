"""
data/coingecko_fetcher.py — CoinGecko free API data.

Fetches:
  - Global market data (BTC dominance, total market cap, TOTAL2)
  - Per-coin fundamentals (volume, dev activity, community)
  - Trending coins

CoinGecko free tier: 30 req/min. We cache heavily.
"""
import asyncio
from typing import Optional
import httpx
from loguru import logger

from config import COINGECKO_BASE_URL, CACHE_FA
from utils.cache import cache_get, cache_set
from utils.rate_limiter import COINGECKO_LIMITER

# Map Binance symbols to CoinGecko IDs
COINGECKO_IDS = {
    "BTCUSDT":  "bitcoin",
    "ETHUSDT":  "ethereum",
    "SOLUSDT":  "solana",
    "BNBUSDT":  "binancecoin",
    "AVAXUSDT": "avalanche-2",
    "ADAUSDT":  "cardano",
    "DOTUSDT":  "polkadot",
    "LINKUSDT": "chainlink",
    "MATICUSDT":"matic-network",
    "ATOMUSDT": "cosmos",
    "NEARUSDT": "near",
    "ARBUSDT":  "arbitrum",
    "OPUSDT":   "optimism",
    "INJUSDT":  "injective-protocol",
    "SUIUSDT":  "sui",
    "APTUSDT":  "aptos",
}


async def _get(endpoint: str, params: dict = None) -> Optional[dict | list]:
    await COINGECKO_LIMITER.acquire()
    url = f"{COINGECKO_BASE_URL}{endpoint}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params=params or {})
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            logger.warning("CoinGecko rate limited — sleeping 60s")
            await asyncio.sleep(60)
        else:
            logger.warning(f"CoinGecko HTTP {e.response.status_code}")
    except Exception as e:
        logger.warning(f"CoinGecko error: {e}")
    return None


async def fetch_global_market() -> Optional[dict]:
    """
    Fetch global crypto market data.
    This is the foundation for Pipeline 2 (BTC/DOM/USD/Alts).

    Returns:
      - btc_dominance: BTC's % of total market cap
      - total_market_cap: total crypto market in USD
      - total_market_cap_24h_change: 24h % change
      - total2_approx: total market cap minus BTC (approximated)
      - btc_price: current BTC price from global data
    """
    cache_key = "cg:global"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    data = await _get("/global")
    if not data or "data" not in data:
        return None

    d = data["data"]
    market_cap = d.get("total_market_cap", {})
    market_cap_pct = d.get("market_cap_percentage", {})
    market_cap_24h = d.get("market_cap_change_percentage_24h_usd", 0)

    total_cap_usd = market_cap.get("usd", 0)
    btc_dominance = market_cap_pct.get("btc", 50)
    eth_dominance = market_cap_pct.get("eth", 15)

    # TOTAL2 = total minus BTC
    btc_cap = total_cap_usd * (btc_dominance / 100)
    total2 = total_cap_usd - btc_cap

    result = {
        "total_market_cap": total_cap_usd,
        "market_cap_24h_change": market_cap_24h,
        "btc_dominance": btc_dominance,
        "eth_dominance": eth_dominance,
        "btc_cap": btc_cap,
        "total2": total2,
        "active_cryptos": d.get("active_cryptocurrencies", 0),
        "ongoing_icos": d.get("ongoing_icos", 0),
    }

    cache_set(cache_key, result, 600)  # 10 min for market data
    return result


async def fetch_coin_data(symbol: str) -> Optional[dict]:
    """
    Fetch detailed fundamentals for a specific coin.
    Used in Pipeline 3 (Fundamental Analysis).

    Includes: price, volume, market cap, ATH, dev activity,
    community scores, 7-day price history.
    """
    coin_id = COINGECKO_IDS.get(symbol)
    if not coin_id:
        logger.debug(f"No CoinGecko ID for {symbol}, skipping FA")
        return None

    cache_key = f"cg:coin:{coin_id}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    data = await _get(f"/coins/{coin_id}", params={
        "localization": "false",
        "tickers": "false",
        "market_data": "true",
        "community_data": "true",
        "developer_data": "true",
        "sparkline": "false",
    })

    if not data:
        return None

    market = data.get("market_data", {})
    dev    = data.get("developer_data", {})
    community = data.get("community_data", {})

    current_price = market.get("current_price", {}).get("usd", 0)
    ath_price     = market.get("ath", {}).get("usd", 0)
    ath_pct_from  = market.get("ath_change_percentage", {}).get("usd", 0)
    volume_24h    = market.get("total_volume", {}).get("usd", 0)
    market_cap    = market.get("market_cap", {}).get("usd", 0)
    price_24h     = market.get("price_change_percentage_24h", 0)
    price_7d      = market.get("price_change_percentage_7d_in_currency", {}).get("usd", 0)
    vol_7d_avg    = volume_24h  # approximation — CoinGecko free doesn't give 7d avg directly

    # Developer activity — higher is more active project
    # Stars, forks, commits, issues = healthy project
    dev_score = min(100, (
        min(dev.get("stars", 0), 50000) / 500 +          # max 100 from stars
        min(dev.get("commit_count_4_weeks", 0), 100) +    # commits this month
        min(dev.get("closed_issues", 0), 50) / 5           # closed issues health
    ) / 3)

    # Community score composite
    community_score = data.get("community_score", 0)
    coingecko_score = data.get("coingecko_score", 0)

    result = {
        "symbol": symbol,
        "coin_id": coin_id,
        "price": current_price,
        "ath_price": ath_price,
        "ath_distance_pct": abs(ath_pct_from),  # How far below ATH
        "volume_24h": volume_24h,
        "market_cap": market_cap,
        "market_cap_rank": data.get("market_cap_rank", 999),
        "price_24h_change": price_24h,
        "price_7d_change": price_7d,
        "dev_score": dev_score,
        "community_score": community_score,
        "coingecko_score": coingecko_score,
        "dev_commits_4w": dev.get("commit_count_4_weeks", 0),
        "dev_stars": dev.get("stars", 0),
        "twitter_followers": community.get("twitter_followers", 0),
        "reddit_subscribers": community.get("reddit_subscribers", 0),
    }

    cache_set(cache_key, result, CACHE_FA)
    return result


async def fetch_trending() -> Optional[list]:
    """
    Fetch trending coins on CoinGecko.
    Trending = interest spike = potential signal amplifier.
    """
    cache_key = "cg:trending"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    data = await _get("/search/trending")
    if not data:
        return []

    coins = data.get("coins", [])
    trending = [c["item"]["symbol"].upper() for c in coins[:10]]

    cache_set(cache_key, trending, 1800)  # 30 min
    return trending


async def fetch_market_history(coin_id: str = "bitcoin", days: int = 90) -> Optional[list]:
    """
    Fetch historical market cap data for cycle position analysis.
    Used to determine if we're near ATH (distribution) or bottom (accumulation).
    """
    cache_key = f"cg:history:{coin_id}:{days}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    data = await _get(f"/coins/{coin_id}/market_chart", params={
        "vs_currency": "usd",
        "days": str(days),
        "interval": "daily",
    })

    if not data:
        return None

    market_caps = [x[1] for x in data.get("market_caps", [])]
    cache_set(cache_key, market_caps, CACHE_FA)
    return market_caps
