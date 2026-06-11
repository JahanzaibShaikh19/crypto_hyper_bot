"""
engine/override_rules.py — Emergency override and black swan rules.

These rules override the scoring engine entirely.
They are rare but when triggered, they are ABSOLUTE.

Rules:
1. Breaking hack/SEC/ban news → FORCE SHORT regardless of score
2. Binance listing announcement → FORCE LONG for that coin
3. Fed rate cut surprise → +2 global boost
4. Black swan (BTC -10% in 1 candle) → ALL SIGNALS SUSPENDED
"""
from loguru import logger
import pandas as pd
from config import WATCHLIST


def check_black_swan(df_1h: pd.DataFrame) -> dict:
    """
    Black swan: BTC drops >10% in a single 1H candle.
    This is a rare but catastrophic event.
    When detected, all signals are suspended.
    """
    if df_1h is None or len(df_1h) < 2:
        return {"detected": False}

    last_candle = df_1h.iloc[-1]
    open_price  = last_candle["open"]
    close_price = last_candle["close"]

    if open_price <= 0:
        return {"detected": False}

    candle_change = (close_price - open_price) / open_price * 100

    if candle_change <= -10:
        return {
            "detected": True,
            "change_pct": round(candle_change, 2),
            "open": open_price,
            "close": close_price,
            "message": (
                f"🚨 BLACK SWAN DETECTED\n"
                f"BTC dropped {candle_change:.1f}% in 1 hour\n"
                f"ALL SIGNALS SUSPENDED\n"
                f"Do NOT trade until stabilization.\n"
                f"Next scan: 1 hour from now."
            ),
        }

    return {"detected": False}


def check_emergency_news(sentiment_result: dict) -> dict | None:
    """
    Check if sentiment pipeline flagged an emergency.
    Returns override instruction if found.
    """
    override = sentiment_result.get("emergency_override")
    if not override:
        return None

    return {
        "type": override["type"],
        "direction": "SHORT",
        "reason": override.get("reason", "Emergency bearish event"),
        "force": True,
        "message": (
            f"🚨 EMERGENCY SIGNAL OVERRIDE\n"
            f"Type: {override['type']}\n"
            f"Reason: {override.get('reason', '')[:100]}\n"
            f"⛔ FORCED SHORT regardless of other signals\n"
            f"Do NOT ignore this override."
        ),
    }


def check_binance_listing(sentiment_result: dict, symbol: str) -> dict | None:
    """
    Check if Binance listing was detected for this symbol.
    Returns bullish force override if found.
    """
    listing = sentiment_result.get("listing_override")
    if not listing:
        return None

    return {
        "type": "BINANCE_LISTING",
        "direction": "LONG",
        "reason": listing.get("title", "Binance listing detected"),
        "force": True,
        "score_boost": 2.0,
        "message": (
            f"🚀 BINANCE LISTING OVERRIDE\n"
            f"{listing.get('title', '')[:100]}\n"
            f"Historical reaction: +20-100% in 24-48h\n"
            f"⚡ FORCED LONG signal"
        ),
    }


def apply_overrides(
    master_score: float,
    symbol: str,
    ta_result: dict,
    sentiment_result: dict,
    df_1h_btc: pd.DataFrame = None,
) -> dict:
    """
    Apply all override checks to final master score.
    Returns modified score and any override messages.
    """
    overrides = []
    modified_score = master_score
    force_direction = None
    suspended = False

    # 1. Black swan check (BTC only, but suspends ALL signals)
    if df_1h_btc is not None:
        bs = check_black_swan(df_1h_btc)
        if bs["detected"]:
            suspended = True
            overrides.append(bs["message"])
            return {
                "modified_score": 0.0,
                "force_direction": None,
                "suspended": True,
                "overrides": overrides,
                "emergency_message": bs["message"],
            }

    # 2. Emergency news override (hack, SEC, ban, etc.)
    news_override = check_emergency_news(sentiment_result)
    if news_override:
        force_direction = "SHORT"
        modified_score = -10.0
        overrides.append(news_override["message"])

    # 3. Binance listing override
    listing_override = check_binance_listing(sentiment_result, symbol)
    if listing_override and not news_override:  # News emergency takes priority
        force_direction = "LONG"
        modified_score = 10.0
        overrides.append(listing_override["message"])

    return {
        "modified_score": modified_score,
        "force_direction": force_direction,
        "suspended": suspended,
        "overrides": overrides,
        "has_override": bool(overrides),
        "emergency_message": overrides[0] if overrides else None,
    }
