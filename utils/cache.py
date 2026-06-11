"""
utils/cache.py — In-memory TTL cache.

Prevents hammering free APIs. Each fetcher uses this
to avoid redundant requests within the cache window.
"""
import time
from typing import Any, Optional
from loguru import logger


class TTLCache:
    """Simple time-to-live cache backed by a dict."""

    def __init__(self):
        self._store: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Optional[Any]:
        if key not in self._store:
            return None
        value, expires_at = self._store[key]
        if time.time() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl: int) -> None:
        self._store[key] = (value, time.time() + ttl)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    def stats(self) -> dict:
        now = time.time()
        alive = sum(1 for _, (_, exp) in self._store.items() if exp > now)
        return {"total_keys": len(self._store), "alive": alive}


# Singleton — all modules share one cache
_cache = TTLCache()


def cache_get(key: str) -> Optional[Any]:
    return _cache.get(key)


def cache_set(key: str, value: Any, ttl: int) -> None:
    _cache.set(key, value, ttl)


def cache_delete(key: str) -> None:
    _cache.delete(key)


def cached(ttl: int, key_prefix: str = ""):
    """
    Decorator for async functions.
    Uses function name + args as cache key.
    """
    def decorator(func):
        import functools
        import asyncio

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Build a cache key from prefix + function name + stringified args
            key_parts = [key_prefix or func.__name__] + [str(a) for a in args]
            cache_key = ":".join(key_parts)

            cached_val = cache_get(cache_key)
            if cached_val is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_val

            result = await func(*args, **kwargs)
            if result is not None:
                cache_set(cache_key, result, ttl)
            return result

        return wrapper
    return decorator
