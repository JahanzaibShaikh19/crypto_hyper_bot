"""
storage/performance_tracker.py — lightweight signal outcome tracker.

Checks fired signals after fixed horizons and records whether price moved in the
signal direction. This gives the bot feedback loops before any frontend work.
"""
from __future__ import annotations

import json
from loguru import logger

from data.binance_fetcher import fetch_ticker_24h
from storage.signal_db import (
    get_outcome_candidates,
    save_signal_outcome,
    get_outcome_summary,
)


HORIZONS = {
    "1h": 1,
    "4h": 4,
    "24h": 24,
}


def _entry_price_from_signal(signal: dict) -> float:
    try:
        context = json.loads(signal.get("context") or "{}")
        return float(context.get("price") or 0)
    except Exception:
        return 0.0


async def update_signal_outcomes() -> None:
    """Check pending signal outcomes for all configured horizons."""
    for horizon, hours in HORIZONS.items():
        candidates = get_outcome_candidates(hours_after=hours, horizon=horizon)
        for signal in candidates:
            try:
                symbol = signal["symbol"]
                direction = signal["direction"]
                entry_price = _entry_price_from_signal(signal)

                if entry_price <= 0 or direction not in ("LONG", "SHORT"):
                    continue

                ticker = await fetch_ticker_24h(symbol)
                current_price = float((ticker or {}).get("price") or 0)
                if current_price <= 0:
                    continue

                if direction == "LONG":
                    outcome_pct = ((current_price - entry_price) / entry_price) * 100
                else:
                    outcome_pct = ((entry_price - current_price) / entry_price) * 100

                save_signal_outcome(
                    signal_id=int(signal["id"]),
                    horizon=horizon,
                    outcome_pct=round(outcome_pct, 3),
                    is_win=outcome_pct > 0,
                )
            except Exception as e:
                logger.debug(f"Outcome tracking failed for signal {signal.get('id')}: {e}")


def get_performance_snapshot(days: int = 30) -> dict:
    return get_outcome_summary(days=days)
