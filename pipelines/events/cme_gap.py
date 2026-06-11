"""
pipelines/events/cme_gap.py — CME Bitcoin Futures Gap Engine.

CME gaps are one of the most reliable signals in BTC trading.
Historical fill rate: ~78-80% within 2 weeks.

CME trades Mon-Fri 9AM-4PM CST.
Weekend price action creates gaps that act as price magnets.

This pipeline:
1. Detects new CME gaps from weekend price action
2. Tracks all unfilled gaps in SQLite
3. Alerts when price approaches a gap fill level
"""
import datetime
import pandas as pd
from loguru import logger
from utils.timezone_handler import get_cme_close_time, now_utc, CST
from storage.signal_db import save_cme_gap, get_open_cme_gaps, mark_cme_gap_filled
from config import CME_GAP_ALERT_PERCENT


def detect_new_cme_gap(df_1h: pd.DataFrame) -> dict | None:
    """
    Detect a CME gap from the most recent weekend.

    Algorithm:
    1. Find Friday ~4PM CST close price (CME last close)
    2. Find Monday ~9AM CST open price (CME first open)
    3. If gap > 0.5% = significant gap, save to DB

    Returns gap info if new gap detected, None otherwise.
    """
    if df_1h is None or len(df_1h) < 72:
        return None

    try:
        now = now_utc()

        # Walk back through candles to find Friday close and Monday open
        friday_close  = None
        monday_open   = None
        friday_close_price  = None
        monday_open_price   = None

        for i in range(len(df_1h) - 1, max(len(df_1h) - 168, -1), -1):  # Look back up to 1 week
            candle = df_1h.iloc[i]
            ts = df_1h.index[i]

            # Convert to CST
            ts_cst = ts.astimezone(CST)
            weekday = ts_cst.weekday()
            hour = ts_cst.hour

            # Friday 4PM CST = CME close
            if weekday == 4 and 15 <= hour <= 17 and friday_close is None:
                friday_close = ts_cst
                friday_close_price = float(candle["close"])

            # Monday 9AM CST = CME open
            if weekday == 0 and 8 <= hour <= 10 and monday_open is None:
                monday_open = ts_cst
                monday_open_price = float(candle["open"])

            if friday_close and monday_open:
                break

        if not friday_close_price or not monday_open_price:
            return None

        gap_size = monday_open_price - friday_close_price
        gap_pct  = abs(gap_size) / friday_close_price * 100

        if gap_pct < 0.5:  # Ignore tiny gaps
            return None

        gap_type  = "UP"   if gap_size > 0 else "DOWN"
        gap_price = friday_close_price if gap_type == "UP" else friday_close_price

        # Save to DB (deduplicates automatically)
        # Convert to naive datetime string to avoid SQLite type issues
        gap_date_str = friday_close.strftime("%Y-%m-%d %H:%M:%S")
        import datetime as _dt
        gap_date = _dt.datetime.strptime(gap_date_str, "%Y-%m-%d %H:%M:%S")
        save_cme_gap(gap_price, gap_type, gap_date)

        logger.info(
            f"CME gap detected: {gap_type} at ${gap_price:,.0f} "
            f"(+{gap_pct:.2f}%) — {friday_close.strftime('%b %d')}"
        )

        return {
            "detected": True,
            "gap_type": gap_type,
            "gap_price": gap_price,
            "gap_pct": round(gap_pct, 2),
            "gap_date": friday_close.strftime("%b %d, %Y"),
            "fill_target": friday_close_price,
        }

    except Exception as e:
        logger.debug(f"CME gap detection error: {e}")
        return None


def analyze_cme_gaps(current_price: float) -> dict:
    """
    Analyze all open CME gaps relative to current price.

    Returns:
    - Score (gaps above current price = bearish magnet, below = bullish)
    - Nearest gap (most immediate threat/opportunity)
    - Alert if price within 1% of gap fill
    """
    open_gaps = get_open_cme_gaps()

    if not open_gaps:
        return {
            "score": 0.0,
            "gaps_above": 0,
            "gaps_below": 0,
            "nearest_gap": None,
            "alert": None,
            "summary": "No open CME gaps",
        }

    gaps_above = [g for g in open_gaps if g["gap_price"] > current_price]
    gaps_below = [g for g in open_gaps if g["gap_price"] < current_price]

    # Score: gaps below = bullish magnet (price should go up to fill)
    # gaps above = bearish magnet (price should come down to fill)
    gap_score = (len(gaps_below) * 0.5 - len(gaps_above) * 0.5)
    gap_score = max(-2.0, min(2.0, gap_score))

    # Find nearest gap
    all_gaps_with_dist = [
        {**g, "distance_pct": abs(g["gap_price"] - current_price) / current_price * 100}
        for g in open_gaps
    ]
    nearest = min(all_gaps_with_dist, key=lambda x: x["distance_pct"])

    # Alert if within 1% of gap fill
    alert = None
    if nearest["distance_pct"] <= CME_GAP_ALERT_PERCENT * 100:
        direction = "above" if nearest["gap_price"] > current_price else "below"
        alert = (
            f"🎯 CME GAP FILL APPROACHING\n"
            f"Gap level: ${nearest['gap_price']:,.0f} ({direction}, "
            f"{nearest['distance_pct']:.2f}% away)\n"
            f"From: {nearest.get('gap_date', 'unknown')[:10]}\n"
            f"Historical fill rate: ~78%"
        )
        # Mark as filled if price passed through
        if nearest["distance_pct"] < 0.1:
            mark_cme_gap_filled(nearest["id"])
            alert = f"✅ CME GAP FILLED: ${nearest['gap_price']:,.0f}"

    # Check if nearest gap is a downside magnet (bearish)
    nearest_is_above = nearest["gap_price"] > current_price
    if nearest_is_above and nearest["distance_pct"] <= 3:
        gap_score -= 0.5   # Nearby gap above = likely to pull price down to fill

    return {
        "score": round(gap_score, 3),
        "gaps_above": len(gaps_above),
        "gaps_below": len(gaps_below),
        "total_open_gaps": len(open_gaps),
        "nearest_gap": {
            "price": nearest["gap_price"],
            "type": nearest["gap_type"],
            "distance_pct": round(nearest["distance_pct"], 2),
            "above_price": nearest_is_above,
        },
        "alert": alert,
        "summary": _build_gap_summary(gaps_above, gaps_below, nearest, current_price),
    }


def _build_gap_summary(gaps_above, gaps_below, nearest, current_price) -> str:
    parts = []
    if gaps_below:
        nearest_below = min(gaps_below, key=lambda g: abs(g["gap_price"] - current_price))
        parts.append(f"↑ Gap below at ${nearest_below['gap_price']:,.0f}")
    if gaps_above:
        nearest_above = min(gaps_above, key=lambda g: abs(g["gap_price"] - current_price))
        parts.append(f"↓ Gap above at ${nearest_above['gap_price']:,.0f}")
    if not parts:
        parts.append("No nearby CME gaps")
    return " | ".join(parts)
