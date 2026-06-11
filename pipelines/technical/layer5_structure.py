"""
pipelines/technical/layer5_structure.py — Structure & S/R Engine.

Hsaka's principle: "Only trade maximum confluence. Patience IS the alpha."

This layer answers: WHERE IS PRICE IN RELATION TO KEY LEVELS?
Proximity to S/R, ATR expansion/contraction, BTC dominance filter.

Score range: -1 to +1
"""
import pandas as pd
from ta.volatility import AverageTrueRange
from loguru import logger
from config import ATR_PERIOD, PIVOT_PERIOD


def calculate_pivot_points(df: pd.DataFrame, atr: float = None) -> dict:
    """
    Classic pivot points: P, R1, R2, S1, S2.
    Uses previous day's OHLC.

    Price bouncing off S1 with volume = strong entry signal.
    Price breaking above R1 = momentum continuation.
    """
    if df is None or len(df) < 2:
        return {"score": 0, "level": "NONE", "levels": {}}

    # Use previous candle as reference
    prev = df.iloc[-2]
    high  = prev["high"]
    low   = prev["low"]
    close = prev["close"]

    pivot = (high + low + close) / 3
    r1 = 2 * pivot - low
    r2 = pivot + (high - low)
    s1 = 2 * pivot - high
    s2 = pivot - (high - low)

    current = df["close"].iloc[-1]
    
    # Avoid recalculating ATR if it was passed in
    if atr is None:
        atr = calculate_atr_value(df)

    levels = {"P": pivot, "R1": r1, "R2": r2, "S1": s1, "S2": s2}
    proximity_threshold = atr * 0.3 if atr > 0 else pivot * 0.005

    # Check which level price is closest to
    closest_level = min(levels.keys(), key=lambda k: abs(current - levels[k]))
    closest_distance = abs(current - levels[closest_level])

    near_level = closest_distance <= proximity_threshold
    is_support = closest_level in ["S1", "S2"] and near_level
    is_resistance = closest_level in ["R1", "R2"] and near_level

    if is_support:
        score = 0.5    # Bouncing off support = potential long
        level_label = f"At {closest_level} support"
    elif is_resistance:
        score = -0.3   # At resistance = potential rejection
        level_label = f"At {closest_level} resistance"
    elif current > r1:
        score = 0.4    # Above R1 = strong bull territory
        level_label = "Above R1 (strong)"
    elif current < s1:
        score = -0.4   # Below S1 = weak territory
        level_label = "Below S1 (weak)"
    elif current > pivot:
        score = 0.2    # Above pivot = mild bull
        level_label = "Above pivot"
    else:
        score = -0.2   # Below pivot = mild bear
        level_label = "Below pivot"

    return {
        "score": round(score, 3),
        "level_label": level_label,
        "closest_level": closest_level,
        "near_key_level": near_level,
        "is_support": is_support,
        "is_resistance": is_resistance,
        "levels": {k: round(v, 2) for k, v in levels.items()},
    }


def calculate_atr_value(df: pd.DataFrame) -> float:
    """Calculate current ATR value."""
    if df is None or len(df) < ATR_PERIOD:
        return 0.0
    atr_series = AverageTrueRange(high=df["high"], low=df["low"], close=df["close"], window=ATR_PERIOD).average_true_range()
    if atr_series is None or atr_series.empty:
        return 0.0
    val = atr_series.iloc[-1]
    return float(val) if not pd.isna(val) else 0.0


def analyze_atr_context(df: pd.DataFrame) -> dict:
    """
    ATR expansion/contraction signal.

    ATR expanding = volatility increasing = trend has conviction
    ATR contracting = consolidation = breakout coming
    Extreme ATR spike = possible reversal / exhaustion
    """
    if df is None or len(df) < ATR_PERIOD + 10:
        return {"score": 0, "condition": "UNKNOWN", "expanding": False}

    atr_series = AverageTrueRange(high=df["high"], low=df["low"], close=df["close"], window=ATR_PERIOD).average_true_range()
    if atr_series is None or len(atr_series) < 10:
        return {"score": 0, "condition": "UNKNOWN", "expanding": False}

    current_atr = atr_series.iloc[-1]
    avg_atr_10  = atr_series.iloc[-10:].mean()
    avg_atr_30  = atr_series.iloc[-30:].mean() if len(atr_series) >= 30 else avg_atr_10

    expanding    = current_atr > avg_atr_10 * 1.15
    contracting  = current_atr < avg_atr_10 * 0.85
    extreme_high = current_atr > avg_atr_30 * 2.5

    close = df["close"].iloc[-1]
    current_price = close

    # ATR as % of price
    atr_pct = (current_atr / current_price * 100) if current_price > 0 else 0

    if extreme_high:
        score = -0.3   # Extreme volatility = reduce confidence
        condition = "EXTREME_VOLATILITY"
    elif expanding:
        score = 0.3    # Expanding ATR = trend picking up
        condition = "EXPANDING"
    elif contracting:
        score = 0.1    # Contracting = coil, breakout coming (neutral direction)
        condition = "CONTRACTING"
    else:
        score = 0.0
        condition = "NORMAL"

    return {
        "score": round(score, 3),
        "condition": condition,
        "expanding": expanding,
        "contracting": contracting,
        "extreme": extreme_high,
        "atr": round(current_atr, 2),
        "atr_pct": round(atr_pct, 2),
        "avg_atr": round(avg_atr_10, 2),
    }


def analyze_btc_dominance_filter(btc_dom_data: dict, symbol: str) -> dict:
    """
    BTC Dominance filter for altcoins.

    When BTC.D is rising, capital is flowing INTO BTC FROM alts.
    Longing alts when BTC.D is rising = fighting the flow = bad trade.

    For BTC itself, rising BTC.D = bullish.
    For alts, rising BTC.D = avoid longs.
    """
    if not btc_dom_data:
        return {"score": 0, "modifier": 1.0, "label": "UNKNOWN"}

    is_btc = symbol.startswith("BTC")
    btc_dom = btc_dom_data.get("btc_dominance", 50)
    dom_direction = btc_dom_data.get("dom_direction", "NEUTRAL")  # RISING, FALLING, NEUTRAL

    if is_btc:
        # For BTC: rising dominance = capital coming in = bullish
        if dom_direction == "RISING":
            return {"score": 0.3, "modifier": 1.0, "label": "BTC_DOMINANCE_RISING_FOR_BTC"}
        elif dom_direction == "FALLING":
            return {"score": -0.2, "modifier": 0.9, "label": "BTC_DOMINANCE_FALLING"}
        else:
            return {"score": 0.0, "modifier": 1.0, "label": "BTC_DOMINANCE_NEUTRAL"}
    else:
        # For alts: falling dominance = capital rotating to alts = bullish
        if dom_direction == "RISING":
            return {"score": -0.5, "modifier": 0.7, "label": "BAD_FOR_ALTS"}
        elif dom_direction == "FALLING":
            return {"score": 0.4, "modifier": 1.2, "label": "ALTSEASON_FLOW"}
        else:
            return {"score": 0.0, "modifier": 1.0, "label": "NEUTRAL"}


def score_layer5(df_4h: pd.DataFrame, btc_dom_data: dict, symbol: str) -> dict:
    """Combine Layer 5 structure scores."""
    if df_4h is None:
        return {"score": 0.0, "components": {}, "error": "No 4H data"}

    atr     = analyze_atr_context(df_4h)
    pivots  = calculate_pivot_points(df_4h, atr=atr.get("atr", None))
    dom_filter = analyze_btc_dominance_filter(btc_dom_data, symbol)

    raw_score = (
        pivots["score"]     * 0.45 +
        atr["score"]        * 0.25 +
        dom_filter["score"] * 0.30
    )

    final = max(-1.0, min(1.0, raw_score))

    return {
        "score": round(final, 3),
        "pivots": pivots,
        "atr": atr,
        "dominance_filter": dom_filter,
        "summary": _build_l5_summary(pivots, atr, dom_filter),
    }


def _build_l5_summary(pivots, atr, dom) -> list:
    lines = []

    piv_emoji = "✅" if pivots["score"] > 0 else "❌" if pivots["score"] < 0 else "⚪"
    lines.append(f"{piv_emoji} S/R: {pivots['level_label']}")

    if atr["condition"] == "EXPANDING":
        lines.append("✅ ATR expanding — trend conviction")
    elif atr["condition"] == "CONTRACTING":
        lines.append("⚡ ATR contracting — breakout imminent")
    elif atr["condition"] == "EXTREME_VOLATILITY":
        lines.append("⚠️ Extreme ATR — reduce size")
    else:
        lines.append(f"⚪ ATR: normal ({atr['atr_pct']:.1f}% of price)")

    dom_emoji = "✅" if dom["score"] > 0 else "❌" if dom["score"] < 0 else "⚪"
    lines.append(f"{dom_emoji} BTC.D filter: {dom['label']}")

    return lines
