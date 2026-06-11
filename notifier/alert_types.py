"""
notifier/alert_types.py — Special alert type handlers.

Handles the 5 special alert types defined in the spec:
1. Pre-event warnings (24h before major macro events)
2. CME gap approaching alerts
3. Whale/influencer post alerts
4. Black swan emergency
5. Altseason signal
"""
import asyncio
from loguru import logger
from notifier.telegram import send_message
from notifier.formatters import (
    format_pre_event_warning,
    format_cme_gap_alert,
    format_whale_alert,
    format_black_swan,
    format_altseason_alert,
)
from storage.signal_db import is_event_cached, cache_event


async def maybe_send_pre_event_warning(
    event_name: str,
    hours_away: float,
    current_direction: str,
    event_id: str,
) -> bool:
    """
    Send a warning 24h before a major macro event.
    Uses event cache to prevent duplicate alerts.
    """
    cache_key = f"pre_event:{event_id}"
    if is_event_cached(cache_key):
        return False  # Already warned about this event

    if not (20 <= hours_away <= 26):  # ~24h window
        return False

    msg = format_pre_event_warning(event_name, hours_away, current_direction)
    success = await send_message(msg)

    if success:
        cache_event(cache_key, "PRE_EVENT_WARNING", {
            "event": event_name,
            "hours": hours_away,
        })
        logger.info(f"Pre-event warning sent: {event_name}")

    return success


async def maybe_send_cme_gap_alert(
    gap_price: float,
    gap_type: str,
    distance_pct: float,
    gap_date: str,
    gap_id: int,
) -> bool:
    """
    Send CME gap fill alert when price gets within 1%.
    Caches to prevent repeated alerts for same gap.
    """
    cache_key = f"cme_gap_alert:{gap_id}"
    if is_event_cached(cache_key):
        return False

    msg = format_cme_gap_alert(gap_price, gap_type, distance_pct, gap_date)
    success = await send_message(msg)

    if success:
        cache_event(cache_key, "CME_GAP_ALERT", {
            "gap_price": gap_price,
            "distance_pct": distance_pct,
        })
        logger.info(f"CME gap alert sent: ${gap_price:,.0f}")

    return success


async def maybe_send_altseason_alert(
    btc_dom_before: float,
    btc_dom_after: float,
    total2_change: float,
    alert_id: str,
) -> bool:
    """
    Send altseason signal when BTC.D drops >3% in 48h
    while TOTAL2 rises >5%.
    """
    dom_drop = btc_dom_before - btc_dom_after

    # Only trigger on significant moves
    if dom_drop < 3.0 or total2_change < 5.0:
        return False

    cache_key = f"altseason:{alert_id}"
    if is_event_cached(cache_key):
        return False

    msg = format_altseason_alert(btc_dom_before, btc_dom_after, total2_change)
    success = await send_message(msg)

    if success:
        cache_event(cache_key, "ALTSEASON_ALERT", {
            "dom_drop": dom_drop,
            "total2_change": total2_change,
        })
        logger.info(f"Altseason alert sent: BTC.D -{dom_drop:.1f}%")

    return success


async def send_black_swan_alert(change_pct: float, top_news: list) -> bool:
    """Immediately send black swan emergency — no caching."""
    msg = format_black_swan(change_pct, top_news)
    logger.critical(f"BLACK SWAN: BTC {change_pct:.1f}% — sending emergency alert")
    return await send_message(msg)


async def check_and_send_special_alerts(
    result: dict,
    events_result: dict,
    global_data: dict,
) -> None:
    """
    Check all conditions for special alerts and fire them asynchronously.
    Called after every main scan cycle.
    """
    tasks = []

    # ─── CME Gap alerts ───────────────────────────────────────────
    cme = events_result.get("cme", {})
    nearest = cme.get("nearest_gap")
    if nearest and nearest.get("distance_pct", 100) <= 1.0:
        tasks.append(maybe_send_cme_gap_alert(
            gap_price=nearest["price"],
            gap_type=nearest.get("type", "UNKNOWN"),
            distance_pct=nearest["distance_pct"],
            gap_date="recent",
            gap_id=hash(nearest["price"]),
        ))

    # ─── Altseason alert ─────────────────────────────────────────
    if global_data:
        dom = global_data.get("btc_dominance", 50)
        # We'd need historical dom; using change as proxy
        dom_change_24h = global_data.get("btc_dominance_change_24h", 0)
        total2_change  = global_data.get("total2_change_24h", 0)

        if dom_change_24h < -1.5 and total2_change > 3.0:
            import datetime
            alert_id = datetime.datetime.utcnow().strftime("%Y%m%d")
            tasks.append(maybe_send_altseason_alert(
                btc_dom_before=dom - dom_change_24h,
                btc_dom_after=dom,
                total2_change=total2_change,
                alert_id=alert_id,
            ))

    # ─── Pre-event warnings ───────────────────────────────────────
    macro = events_result.get("macro", {})
    for event in macro.get("events", []):
        # Check if event is ~24h away (crude check from summary)
        pass  # Implemented via macro_calendar module separately

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
