"""
pipelines/events/macro_events.py — Macro event scoring for the events pipeline.
"""
from data.macro_calendar import parse_recent_macro_events, get_next_fomc_estimate
from loguru import logger


async def score_macro_events() -> dict:
    """
    Score macro events for the events pipeline.
    Returns aggregate score and event context.
    """
    events = await parse_recent_macro_events()
    fomc   = get_next_fomc_estimate()

    total_score = 0.0
    event_details = []

    for event in events[:5]:  # Top 5 most recent relevant events
        score = event.get("crypto_score", 0)
        total_score += score
        event_details.append({
            "type": event.get("event_type", ""),
            "score": score,
            "summary": event.get("summary_short", "")[:80],
        })

    # Add FOMC risk
    total_score += fomc.get("risk_score", 0)

    # Cap the aggregate
    total_score = max(-4.0, min(4.0, total_score))

    return {
        "score": round(total_score, 3),
        "events": event_details,
        "fomc": fomc,
        "has_warning": fomc.get("warning", False),
        "warnings": [fomc["warning_text"]] if fomc.get("warning") and fomc.get("warning_text") else [],
    }
