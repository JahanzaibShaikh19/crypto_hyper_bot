"""
pipelines/technical/layer3_volume.py — Volume & Accumulation Engine.

Ansem's principle: "Volume and accumulation precede every major move."

This layer answers: IS SMART MONEY BEHIND THIS?
High volume on up moves + low volume on down moves = accumulation.
OBV rising with price = healthy trend.
VWAP above/below = institutional benchmark.

Score range: -1 to +1
"""
import pandas as pd
import numpy as np
import pandas_ta as ta
from loguru import logger


def analyze_obv(df_4h: pd.DataFrame) -> dict:
    """
    On-Balance Volume (OBV) trend.

    OBV rising = more volume on up days than down days = bullish accumulation
    OBV falling = more volume on down days = distribution

    Ansem watches OBV divergence specifically:
    OBV rising while price flat/down = smart money loading = pre-breakout signal
    """
    if df_4h is None or len(df_4h) < 20:
        return {"score": 0, "trend": "NEUTRAL", "divergence": None}

    close  = df_4h["close"]
    volume = df_4h["volume"]

    obv_series = ta.obv(close, volume)
    if obv_series is None:
        return {"score": 0, "trend": "NEUTRAL", "divergence": None}

    # OBV trend: compare recent average to older average
    recent_obv = obv_series.iloc[-10:].mean()
    older_obv  = obv_series.iloc[-20:-10].mean()

    obv_trend_up   = recent_obv > older_obv
    obv_trend_down = recent_obv < older_obv

    # Price trend (parallel comparison)
    recent_price = close.iloc[-10:].mean()
    older_price  = close.iloc[-20:-10].mean()
    price_up   = recent_price > older_price
    price_down = recent_price < older_price

    # OBV divergence (the premium signal Ansem watches)
    # OBV rising, price falling = hidden accumulation = strong bull
    # OBV falling, price rising = distribution = strong bear
    if obv_trend_up and price_down:
        divergence = "BULLISH"   # Smart money loading while retail panic sells
        score = 0.8
    elif obv_trend_down and price_up:
        divergence = "BEARISH"   # Distribution while retail is excited
        score = -0.8
    elif obv_trend_up and price_up:
        divergence = None
        score = 0.5   # Both up = confirmed trend
    elif obv_trend_down and price_down:
        divergence = None
        score = -0.5  # Both down = confirmed downtrend
    else:
        divergence = None
        score = 0.0

    return {
        "score": round(score, 3),
        "trend": "UP" if obv_trend_up else "DOWN",
        "divergence": divergence,
        "obv_current": round(obv_series.iloc[-1], 0),
        "obv_trend_up": obv_trend_up,
    }


def analyze_volume_spike(df_4h: pd.DataFrame) -> dict:
    """
    Volume spike detection.

    Volume > 2x rolling average + direction = strong signal.
    "Volume is the fuel. Price is the car." — Ansem
    """
    if df_4h is None or len(df_4h) < 20:
        return {"score": 0, "spike": False, "ratio": 1.0}

    volume = df_4h["volume"]
    close  = df_4h["close"]

    avg_volume = volume.iloc[-20:-1].mean()  # 20-period average, excluding last candle
    current_volume = volume.iloc[-1]
    current_close  = close.iloc[-1]
    prev_close     = close.iloc[-2]

    ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
    is_spike = ratio > 2.0
    is_moderate = 1.5 <= ratio <= 2.0

    price_direction = "UP" if current_close > prev_close else "DOWN"

    if is_spike:
        if price_direction == "UP":
            score = 1.0   # Huge volume on up move = conviction long
        else:
            score = -0.8  # Huge volume on down move = conviction short (but panic is closer)
    elif is_moderate:
        if price_direction == "UP":
            score = 0.5
        else:
            score = -0.3
    else:
        score = 0.0

    return {
        "score": round(score, 3),
        "spike": is_spike,
        "moderate": is_moderate,
        "ratio": round(ratio, 2),
        "direction": price_direction,
        "current_volume": current_volume,
        "avg_volume": avg_volume,
    }


def analyze_vwap(df_1h: pd.DataFrame) -> dict:
    """
    VWAP (Volume Weighted Average Price) on 1H.

    Institutional traders use VWAP as their benchmark.
    Above VWAP = institutions are profitable = likely to hold/add
    Below VWAP = institutions at a loss = may sell to cut losses
    """
    if df_1h is None or len(df_1h) < 2:
        return {"score": 0, "above_vwap": None, "vwap": 0}

    # Calculate VWAP manually (session-based is ideal, daily reset is common)
    df_copy = df_1h.copy()
    df_copy["typical_price"] = (df_copy["high"] + df_copy["low"] + df_copy["close"]) / 3
    df_copy["tp_vol"] = df_copy["typical_price"] * df_copy["volume"]

    # Use last 24 candles (~24 hours on 1H) as the VWAP window
    window = min(24, len(df_copy))
    window_df = df_copy.iloc[-window:]

    vwap = window_df["tp_vol"].sum() / window_df["volume"].sum() if window_df["volume"].sum() > 0 else 0
    current_price = df_1h["close"].iloc[-1]

    above_vwap = current_price > vwap
    distance_pct = (current_price - vwap) / vwap * 100 if vwap > 0 else 0

    # Far above VWAP can mean overextended
    if above_vwap:
        if abs(distance_pct) > 5:
            score = 0.3   # Overextended above
        else:
            score = 0.5   # Healthy above
    else:
        if abs(distance_pct) > 5:
            score = -0.5  # Overextended below
        else:
            score = -0.3  # Slightly below

    return {
        "score": round(score, 3),
        "above_vwap": above_vwap,
        "vwap": round(vwap, 2),
        "distance_pct": round(distance_pct, 2),
        "current_price": round(current_price, 2),
    }


def score_layer3(df_4h: pd.DataFrame, df_1h: pd.DataFrame) -> dict:
    """Combine Layer 3 volume scores."""
    if df_4h is None:
        return {"score": 0.0, "components": {}, "error": "No 4H data"}

    obv    = analyze_obv(df_4h)
    spike  = analyze_volume_spike(df_4h)
    vwap   = analyze_vwap(df_1h)

    # OBV is the foundational signal (long-term accumulation)
    # Volume spike confirms short-term intent
    # VWAP is institutional benchmark
    raw_score = (
        obv["score"]   * 0.45 +
        spike["score"] * 0.35 +
        vwap["score"]  * 0.20
    )

    final = max(-1.0, min(1.0, raw_score))

    return {
        "score": round(final, 3),
        "obv": obv,
        "volume_spike": spike,
        "vwap": vwap,
        "summary": _build_l3_summary(obv, spike, vwap),
    }


def _build_l3_summary(obv, spike, vwap) -> list:
    lines = []

    obv_emoji = "✅" if obv["score"] > 0 else "❌" if obv["score"] < 0 else "⚪"
    lines.append(f"{obv_emoji} OBV: {obv['trend']} trend")

    if obv["divergence"]:
        lines.append(f"🔍 OBV {obv['divergence']} divergence (smart money signal)")

    if spike["spike"]:
        dir_emoji = "🟢" if spike["direction"] == "UP" else "🔴"
        lines.append(f"{dir_emoji} Volume spike: {spike['ratio']:.1f}x average")
    elif spike["moderate"]:
        lines.append(f"📊 Volume elevated: {spike['ratio']:.1f}x average")
    else:
        lines.append(f"⚪ Volume: normal ({spike['ratio']:.1f}x avg)")

    vwap_emoji = "✅" if vwap["above_vwap"] else "❌"
    lines.append(
        f"{vwap_emoji} VWAP: {'above' if vwap['above_vwap'] else 'below'} "
        f"(${vwap['vwap']:,.0f}, {vwap['distance_pct']:+.1f}%)"
    )

    return lines
