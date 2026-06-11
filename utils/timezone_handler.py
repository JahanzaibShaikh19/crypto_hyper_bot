"""
utils/timezone_handler.py — Timezone utilities for market sessions.

Markets have different liquidity profiles by session.
This module determines current session and liquidity level.
"""
import datetime
import pytz
from loguru import logger


UTC     = pytz.UTC
ET      = pytz.timezone("America/New_York")   # US Eastern
CST     = pytz.timezone("America/Chicago")    # CME is CST
ASIA    = pytz.timezone("Asia/Tokyo")


def now_utc() -> datetime.datetime:
    return datetime.datetime.now(UTC)


def now_et() -> datetime.datetime:
    return datetime.datetime.now(ET)


def now_cst() -> datetime.datetime:
    return datetime.datetime.now(CST)


def get_market_session() -> dict:
    """
    Returns current market session and liquidity profile.

    Sessions and their crypto liquidity quality:
    - US session (9 AM - 4 PM ET): HIGHEST — most volume, most reliable signals
    - EU session (3 AM - 9 AM ET): HIGH — second most liquid
    - Asia session (8 PM - 4 AM ET): MEDIUM
    - Weekend: LOW — manipulable, less reliable
    - CME closed (Fri 4PM - Sun 6PM ET): signals less reliable
    """
    now = now_et()
    weekday = now.weekday()  # 0=Mon, 6=Sun
    hour = now.hour + now.minute / 60

    is_weekend = weekday >= 5  # Saturday or Sunday

    # CME futures schedule
    is_cme_open = (
        weekday < 5 and  # Mon-Fri
        9 <= hour < 16   # 9 AM - 4 PM CST (approx ET +1h)
    )

    # US stock market session
    is_us_session = not is_weekend and 9.5 <= hour < 16

    # European session
    is_eu_session = not is_weekend and 3 <= hour < 9.5

    # Asian session
    is_asia_session = hour >= 20 or hour < 4

    if is_weekend:
        session = "WEEKEND"
        liquidity = "LOW"
        confidence_modifier = 0.85  # Reduce confidence 15%
    elif is_us_session:
        session = "US"
        liquidity = "HIGH"
        confidence_modifier = 1.0
    elif is_eu_session:
        session = "EU"
        liquidity = "HIGH"
        confidence_modifier = 0.95
    elif is_asia_session:
        session = "ASIA"
        liquidity = "MEDIUM"
        confidence_modifier = 0.90
    else:
        session = "OFF_HOURS"
        liquidity = "LOW"
        confidence_modifier = 0.88

    return {
        "session": session,
        "liquidity": liquidity,
        "confidence_modifier": confidence_modifier,
        "is_weekend": is_weekend,
        "is_cme_open": is_cme_open,
        "timestamp_et": now.strftime("%H:%M ET"),
        "warning": (
            "⚠️ Low liquidity period — signals less reliable"
            if confidence_modifier < 0.90 else None
        ),
    }


def get_cme_close_time() -> datetime.datetime:
    """Returns the most recent CME close (Friday 4PM CST)."""
    now = now_cst()
    days_since_friday = (now.weekday() - 4) % 7
    last_friday = now - datetime.timedelta(days=days_since_friday)
    cme_close = last_friday.replace(hour=16, minute=0, second=0, microsecond=0)
    if cme_close > now:
        cme_close -= datetime.timedelta(weeks=1)
    return cme_close.astimezone(UTC)


def get_next_cme_open() -> datetime.datetime:
    """Returns next CME open (Monday 9AM CST)."""
    now = now_cst()
    days_until_monday = (7 - now.weekday()) % 7
    if days_until_monday == 0 and now.hour >= 9:
        days_until_monday = 7
    next_monday = now + datetime.timedelta(days=days_until_monday)
    cme_open = next_monday.replace(hour=9, minute=0, second=0, microsecond=0)
    return cme_open.astimezone(UTC)


def hours_until(dt: datetime.datetime) -> float:
    """Hours until a future datetime."""
    now = now_utc()
    if dt.tzinfo is None:
        dt = UTC.localize(dt)
    delta = dt - now
    return max(0, delta.total_seconds() / 3600)
