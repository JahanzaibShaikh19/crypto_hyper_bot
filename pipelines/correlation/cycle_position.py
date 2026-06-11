"""
pipelines/correlation/cycle_position.py — Market Cycle Position.

Plan B's principle: "Bitcoin cycles are predictable via stock-to-flow logic."
Raoul Pal: "Macro liquidity cycle drives all crypto moves."

Two cycle analyses:
1. Halving cycle: where are we relative to last halving?
2. Market cap cycle: where are we relative to the ATH/bottom?
"""
import datetime
from loguru import logger
from config import LAST_HALVING_DATE


def analyze_halving_cycle() -> dict:
    """
    Bitcoin halving cycle position scoring.

    Historical patterns (approximate):
      0-12 months post-halving:  Accumulation / slow grind up (+1)
      12-18 months post-halving: Bull run acceleration (+0.5)
      18-24 months post-halving: Blow-off top risk (-0.5)
      24+ months post-halving:   Bear market / reset (-1)

    Last halving: April 20, 2024.
    Next halving: ~April 2028.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    days_since = (now - LAST_HALVING_DATE).days
    months_since = days_since / 30.44

    if months_since < 0:
        phase = "PRE_HALVING"
        score = 0.5
        label = "Pre-halving (historically bullish)"
    elif months_since <= 12:
        phase = "ACCUMULATION"
        score = 1.0
        label = f"Accumulation phase ({months_since:.0f}mo post-halving)"
    elif months_since <= 18:
        phase = "BULL_RUN"
        score = 0.5
        label = f"Bull run phase ({months_since:.0f}mo post-halving)"
    elif months_since <= 24:
        phase = "BLOW_OFF_RISK"
        score = -0.5
        label = f"Blow-off top risk ({months_since:.0f}mo post-halving)"
    else:
        phase = "BEAR_MARKET"
        score = -1.0
        label = f"Bear market phase ({months_since:.0f}mo post-halving)"

    return {
        "score": round(score, 3),
        "phase": phase,
        "label": label,
        "days_since_halving": days_since,
        "months_since_halving": round(months_since, 1),
        "last_halving": LAST_HALVING_DATE.strftime("%b %d, %Y"),
    }


def analyze_market_cap_cycle(market_cap_history: list) -> dict:
    """
    Where are we in the market cap cycle?

    Compares current total crypto market cap to:
    - 90-day high (cycle context)
    - 90-day low (distance from bottom)

    Bottom zone (<30% of 90d high) = strong accumulation = +1
    Mid zone (30-70% of 90d high) = trending = neutral
    Top zone (>85% of 90d high) = distribution risk = -1
    """
    if not market_cap_history or len(market_cap_history) < 2:
        return {"score": 0, "position": "UNKNOWN", "pct_of_high": 50}

    current = market_cap_history[-1]
    high_90d = max(market_cap_history[-90:]) if len(market_cap_history) >= 90 else max(market_cap_history)
    low_90d  = min(market_cap_history[-90:]) if len(market_cap_history) >= 90 else min(market_cap_history)
    high_30d = max(market_cap_history[-30:]) if len(market_cap_history) >= 30 else high_90d

    if high_90d <= 0:
        return {"score": 0, "position": "UNKNOWN", "pct_of_high": 50}

    pct_of_high = (current / high_90d) * 100
    cycle_range = high_90d - low_90d
    pct_of_range = ((current - low_90d) / cycle_range * 100) if cycle_range > 0 else 50

    if pct_of_high < 30:
        position = "BOTTOM_ZONE"
        score = 1.0
        note = "Near cycle low — strong accumulation zone"
    elif pct_of_high < 60:
        position = "MID_ZONE_LOWER"
        score = 0.3
        note = "Mid-cycle (lower half) — trending"
    elif pct_of_high < 80:
        position = "MID_ZONE_UPPER"
        score = 0.0
        note = "Mid-cycle (upper half) — neutral"
    elif pct_of_high < 90:
        position = "NEAR_TOP"
        score = -0.5
        note = "Near cycle high — caution, possible distribution"
    else:
        position = "TOP_ZONE"
        score = -1.0
        note = "At cycle high — strong distribution risk"

    return {
        "score": round(score, 3),
        "position": position,
        "pct_of_high": round(pct_of_high, 1),
        "pct_of_range": round(pct_of_range, 1),
        "current_mcap_b": round(current / 1e9, 1),
        "high_90d_b": round(high_90d / 1e9, 1),
        "note": note,
    }
