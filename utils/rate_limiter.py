"""
utils/rate_limiter.py — Async token-bucket rate limiter.

Respects free API limits so we don't get IP-banned.
Each API source registers its own limiter.
"""
import asyncio
import time
from collections import defaultdict
from loguru import logger


class RateLimiter:
    """
    Token bucket: allows `max_calls` per `period` seconds.
    Callers await limiter.acquire() before every API call.
    """

    def __init__(self, max_calls: int, period: float):
        self.max_calls = max_calls
        self.period = period
        self._calls: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            # Drop timestamps outside the window
            self._calls = [t for t in self._calls if now - t < self.period]

            if len(self._calls) >= self.max_calls:
                sleep_for = self.period - (now - self._calls[0])
                if sleep_for > 0:
                    logger.debug(f"Rate limit hit, sleeping {sleep_for:.1f}s")
                    await asyncio.sleep(sleep_for)
                    now = time.monotonic()
                    self._calls = [t for t in self._calls if now - t < self.period]

            self._calls.append(time.monotonic())


# Pre-configured limiters for each source
# Binance public: 1200 req/min → we stay well under
BINANCE_LIMITER     = RateLimiter(max_calls=30,  period=60)
# CoinGecko free: 30 req/min
COINGECKO_LIMITER   = RateLimiter(max_calls=25,  period=60)
# CryptoPanic free: 5 req/min
CRYPTOPANIC_LIMITER = RateLimiter(max_calls=4,   period=60)
# Alternative.me: very generous, be polite
FEAR_GREED_LIMITER  = RateLimiter(max_calls=10,  period=60)
# Mempool.space: no hard limit, be polite
MEMPOOL_LIMITER     = RateLimiter(max_calls=20,  period=60)
# RSS feeds: once per fetch cycle is enough
RSS_LIMITER         = RateLimiter(max_calls=30,  period=60)
# Web scraping: slow and polite
SCRAPE_LIMITER      = RateLimiter(max_calls=5,   period=60)
