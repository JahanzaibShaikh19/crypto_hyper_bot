"""
pipelines/events/coin_events.py — Coin-specific event scoring.
"""
from data.events_fetcher import (
    fetch_coingecko_events, fetch_coinmarketcal_rss,
    get_event_timing_score
)
from data.coingecko_fetcher import COINGECKO_IDS
from config import coin_from_symbol
from loguru import logger


async def score_coin_events(symbol: str) -> dict:
    """
    Fetch and score coin-specific upcoming events.
    """
    coin_id = COINGECKO_IDS.get(symbol)
    cg_events = []
    if coin_id:
        cg_events = await fetch_coingecko_events(coin_id)

    cmc_events = await fetch_coinmarketcal_rss()

    # Filter CMC events for this symbol
    coin_short = coin_from_symbol(symbol)
    relevant_cmc = [
        e for e in cmc_events
        if e.get("symbol") == coin_short or
           coin_short.lower() in (e.get("title", "")).lower()
    ]

    all_events = cg_events + relevant_cmc
    total_score = 0.0
    scored_events = []

    for event in all_events[:10]:
        base_score = event.get("score", 0)
        event_date = event.get("date", "")

        if event_date:
            timing = get_event_timing_score(event_date, base_score)
            adj_score = timing.get("adjusted_score", base_score)
            phase = timing.get("phase", "UNKNOWN")
            days_until = timing.get("days_until", 999)
        else:
            adj_score = base_score * 0.5
            phase = "UNKNOWN"
            days_until = 999

        total_score += adj_score
        if abs(adj_score) > 0.1:
            scored_events.append({
                "type": event.get("type", ""),
                "description": event.get("description", event.get("title", ""))[:80],
                "score": round(adj_score, 2),
                "phase": phase,
                "days_until": days_until,
            })

    total_score = max(-3.0, min(3.0, total_score))

    # Sort by impact
    scored_events.sort(key=lambda x: abs(x["score"]), reverse=True)

    return {
        "score": round(total_score, 3),
        "events": scored_events[:5],
        "has_major_event": any(abs(e["score"]) >= 1.5 for e in scored_events),
        "event_count": len(all_events),
    }
