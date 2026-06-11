"""
data/mempool_fetcher.py — Bitcoin on-chain data via Mempool.space API.

Willy Woo's principle: "On-chain reveals what price hides."
Mempool congestion, fee trends, and tx volume tell the real story
of network utilization vs. speculation.
"""
import asyncio
import httpx
from loguru import logger

from config import MEMPOOL_BASE_URL, CACHE_MEMPOOL
from utils.cache import cache_get, cache_set
from utils.rate_limiter import MEMPOOL_LIMITER


async def _get(endpoint: str) -> dict | list | None:
    await MEMPOOL_LIMITER.acquire()
    url = f"{MEMPOOL_BASE_URL}{endpoint}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.debug(f"Mempool error {endpoint}: {e}")
        return None


async def fetch_mempool_stats() -> dict:
    """
    Fetch mempool and network statistics.

    High mempool congestion = network is being heavily used = bullish demand
    High fees = users willing to pay a premium = activity is real
    """
    cached = cache_get("mempool:stats")
    if cached is not None:
        return cached

    # Recommended fees
    fees_data = await _get("/v1/fees/recommended")
    # Mempool overview
    mempool_data = await _get("/v1/mempool")
    # Current hashrate and difficulty
    hashrate_data = await _get("/v1/mining/hashrate/3d")

    fees = {}
    if fees_data:
        fees = {
            "fastest_fee": fees_data.get("fastestFee", 0),
            "half_hour_fee": fees_data.get("halfHourFee", 0),
            "hour_fee": fees_data.get("hourFee", 0),
            "economy_fee": fees_data.get("economyFee", 0),
            "minimum_fee": fees_data.get("minimumFee", 0),
        }

    mempool = {}
    if mempool_data:
        mempool = {
            "count": mempool_data.get("count", 0),          # Unconfirmed transactions
            "vsize": mempool_data.get("vsize", 0),           # Size in vbytes
            "total_fee": mempool_data.get("total_fee", 0),   # Total fees waiting
        }

    # Congestion level
    unconfirmed_count = mempool.get("count", 0)
    if unconfirmed_count > 100000:
        congestion = "HIGH"
        congestion_score = 0.5   # High demand = bullish
    elif unconfirmed_count > 50000:
        congestion = "MEDIUM"
        congestion_score = 0.2
    else:
        congestion = "LOW"
        congestion_score = -0.1  # Low activity = slightly bearish

    # Fee trend (proxy: if fast fee is high, demand is real)
    fast_fee = fees.get("fastest_fee", 0)
    if fast_fee > 100:
        fee_signal = "HIGH_DEMAND"
        fee_score = 0.5
    elif fast_fee > 30:
        fee_signal = "NORMAL"
        fee_score = 0.0
    else:
        fee_signal = "LOW_DEMAND"
        fee_score = -0.2

    result = {
        "fees": fees,
        "mempool": mempool,
        "congestion": congestion,
        "congestion_score": congestion_score,
        "fee_signal": fee_signal,
        "fee_score": fee_score,
        "total_score": (congestion_score + fee_score) / 2,
        "unconfirmed_tx": unconfirmed_count,
        "fast_fee_sat_vb": fast_fee,
    }

    cache_set("mempool:stats", result, CACHE_MEMPOOL)
    return result


async def fetch_blockchain_stats() -> dict:
    """
    Fetch aggregate blockchain statistics.
    7-day transaction count trend = adoption signal.
    """
    cached = cache_get("mempool:blockchain")
    if cached is not None:
        return cached

    # Blocks in last 24h
    blocks_data = await _get("/v1/blocks/0")  # Last 10 blocks

    tx_count_24h = 0
    if blocks_data and isinstance(blocks_data, list):
        tx_count_24h = sum(b.get("tx_count", 0) for b in blocks_data[:6])  # ~6 blocks/hour * 4

    result = {
        "tx_count_24h_approx": tx_count_24h,
        "active": tx_count_24h > 0,
    }

    cache_set("mempool:blockchain", result, CACHE_MEMPOOL)
    return result


async def fetch_all_mempool() -> dict:
    """Fetch all mempool data in parallel."""
    stats, blockchain = await asyncio.gather(
        fetch_mempool_stats(),
        fetch_blockchain_stats(),
        return_exceptions=True,
    )

    return {
        "stats":      stats if not isinstance(stats, Exception) else {},
        "blockchain": blockchain if not isinstance(blockchain, Exception) else {},
    }
