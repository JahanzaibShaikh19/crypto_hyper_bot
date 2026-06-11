"""
pipelines/technical/layer1_trend.py — HTF Trend Structure Engine.

Pentoshi's principle: "HTF structure is king. Never fight the 4H trend."

This layer answers: WHAT IS THE TREND?
Uses 4H as primary timeframe, 1D as macro filter.
EMA stack alignment + Market Structure (BOS/CHoCH) + Price patterns.

Score range: -1.5 to +1.5
"""
import pandas as pd
from ta.trend import EMAIndicator
from loguru import logger
from config import EMA_FAST, EMA_MID, EMA_SLOW


def analyze_ema_stack(df: pd.DataFrame) -> dict:
    """
    EMA 21/50/200 alignment.

    Bull stack: 21>50>200 AND price>21 = trend is up, pullbacks are buys.
    Bear stack: 21<50<200 AND price<21 = trend is down, rallies are sells.
    Mixed: choppy, avoid.

    Pentoshi never fades the 4H EMA 200 direction.
    """
    if df is None or len(df) < EMA_SLOW:
        return {"score": 0, "label": "INSUFFICIENT_DATA", "ema_21": 0, "ema_50": 0, "ema_200": 0}

    close = df["close"]
    ema_21  = EMAIndicator(close=close, window=EMA_FAST).ema_indicator().iloc[-1]
    ema_50  = EMAIndicator(close=close, window=EMA_MID).ema_indicator().iloc[-1]
    ema_200 = EMAIndicator(close=close, window=EMA_SLOW).ema_indicator().iloc[-1]
    current_price = close.iloc[-1]

    if pd.isna(ema_21) or pd.isna(ema_50) or pd.isna(ema_200):
        return {"score": 0, "label": "INSUFFICIENT_DATA"}

    is_bull_stack = ema_21 > ema_50 > ema_200 and current_price > ema_21
    is_bear_stack = ema_21 < ema_50 < ema_200 and current_price < ema_21

    if is_bull_stack:
        score = 1
        label = "BULL_STACK"
    elif is_bear_stack:
        score = -1
        label = "BEAR_STACK"
    else:
        score = 0
        label = "MIXED"

    return {
        "score": score,
        "label": label,
        "ema_21": round(ema_21, 2),
        "ema_50": round(ema_50, 2),
        "ema_200": round(ema_200, 2),
        "price": round(current_price, 2),
        "above_ema_21": current_price > ema_21,
        "above_ema_200": current_price > ema_200,
    }


def analyze_market_structure(df: pd.DataFrame, lookback: int = 10) -> dict:
    """
    Break of Structure (BOS) and Change of Character (CHoCH) detection.

    Higher Highs + Higher Lows = uptrend
    Lower Highs + Lower Lows = downtrend
    BOS above previous swing high = bullish structural shift (+0.5)
    CHoCH = first bullish BOS after downtrend = potential reversal

    This is the Smart Money Concept (SMC) that Pentoshi and Hsaka use.
    """
    if df is None or len(df) < lookback + 2:
        return {"score": 0, "trend": "UNKNOWN", "bos": False, "choch": False}

    highs = df["high"].values
    lows  = df["low"].values

    # Find swing highs and lows using local maxima/minima
    window = 3  # Candles each side to qualify as swing point
    swing_highs = []
    swing_lows  = []

    for i in range(window, len(highs) - window):
        if all(highs[i] >= highs[j] for j in range(i - window, i + window + 1) if j != i):
            swing_highs.append((i, highs[i]))
        if all(lows[i] <= lows[j] for j in range(i - window, i + window + 1) if j != i):
            swing_lows.append((i, lows[i]))

    # Need at least 2 of each to determine structure
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return {"score": 0, "trend": "UNKNOWN", "bos": False, "choch": False}

    # Last few swing points
    recent_highs = swing_highs[-lookback:]
    recent_lows  = swing_lows[-lookback:]

    # Check for HH/HL (uptrend) or LH/LL (downtrend)
    hh = all(recent_highs[i][1] > recent_highs[i-1][1] for i in range(1, len(recent_highs)))
    hl = all(recent_lows[i][1]  > recent_lows[i-1][1]  for i in range(1, len(recent_lows)))
    lh = all(recent_highs[i][1] < recent_highs[i-1][1] for i in range(1, len(recent_highs)))
    ll = all(recent_lows[i][1]  < recent_lows[i-1][1]  for i in range(1, len(recent_lows)))

    current_price = df["close"].iloc[-1]
    last_swing_high = swing_highs[-1][1] if swing_highs else 0
    last_swing_low  = swing_lows[-1][1]  if swing_lows  else 0

    # Break of Structure: price closes above last swing high = bullish BOS
    bos_bullish = current_price > last_swing_high
    bos_bearish = current_price < last_swing_low

    # CHoCH = BOS after a downtrend (potential reversal)
    is_downtrend_before = lh and ll
    choch_bullish = bos_bullish and is_downtrend_before

    if (hh and hl) or (bos_bullish and not bos_bearish):
        trend = "UPTREND"
        score = 1.0 if (hh and hl) else 0.5
        if bos_bullish:
            score = min(1.0, score + 0.5)
    elif (lh and ll) or (bos_bearish and not bos_bullish):
        trend = "DOWNTREND"
        score = -1.0 if (lh and ll) else -0.5
        if bos_bearish:
            score = max(-1.0, score - 0.5)
    else:
        trend = "SIDEWAYS"
        score = 0.0

    # CHoCH is extra bullish signal
    if choch_bullish:
        score = min(1.5, score + 0.3)

    return {
        "score": max(-1.5, min(1.5, score)),
        "trend": trend,
        "bos_bullish": bos_bullish,
        "bos_bearish": bos_bearish,
        "choch": choch_bullish,
        "last_swing_high": round(last_swing_high, 2),
        "last_swing_low":  round(last_swing_low, 2),
        "hh_hl": hh and hl,
        "lh_ll": lh and ll,
    }


def analyze_candlestick_patterns(df: pd.DataFrame) -> dict:
    """
    Detect key candlestick patterns on the most recent candles.

    Bullish Engulfing 4H = +0.5
    Bearish Engulfing 4H = -0.5
    Doji at key level = reduce confidence
    """
    if df is None or len(df) < 3:
        return {"score": 0, "patterns": []}

    patterns_found = []
    score = 0.0

    last_candle = df.iloc[-1]
    prev_candle = df.iloc[-2]

    open_last  = last_candle["open"]
    close_last = last_candle["close"]
    high_last  = last_candle["high"]
    low_last   = last_candle["low"]
    body_last  = abs(close_last - open_last)
    range_last = high_last - low_last

    open_prev  = prev_candle["open"]
    close_prev = prev_candle["close"]
    body_prev  = abs(close_prev - open_prev)

    # Bullish Engulfing: current green candle body > previous red candle body
    bullish_engulf = (
        close_last > open_last and              # Current is green
        close_prev < open_prev and              # Prev was red
        close_last > open_prev and              # Engulfs the open
        open_last < close_prev                  # And close of prev
    )

    # Bearish Engulfing: current red > previous green
    bearish_engulf = (
        close_last < open_last and
        close_prev > open_prev and
        close_last < open_prev and
        open_last > close_prev
    )

    # Doji: body is <20% of range = indecision
    is_doji = range_last > 0 and (body_last / range_last) < 0.20

    # ATR compression (3 consecutive candles with shrinking range)
    if len(df) >= 4:
        ranges = [df["high"].iloc[-i] - df["low"].iloc[-i] for i in range(1, 4)]
        atr_compression = ranges[0] < ranges[1] < ranges[2]
    else:
        atr_compression = False

    # Range breakout: close outside 20-period high/low
    period = min(20, len(df))
    period_high = df["high"].iloc[-period:-1].max()
    period_low  = df["low"].iloc[-period:-1].min()
    range_breakout_up   = close_last > period_high
    range_breakout_down = close_last < period_low

    if bullish_engulf:
        score += 0.5
        patterns_found.append("Bullish Engulfing")
    if bearish_engulf:
        score -= 0.5
        patterns_found.append("Bearish Engulfing")
    if is_doji:
        score *= 0.9  # Reduce conviction on doji
        patterns_found.append("Doji (indecision)")
    if atr_compression:
        patterns_found.append("ATR compression (breakout imminent)")
    if range_breakout_up:
        score += 0.5
        patterns_found.append("Range breakout UP")
    if range_breakout_down:
        score -= 0.5
        patterns_found.append("Range breakout DOWN")

    return {
        "score": max(-1.0, min(1.0, score)),
        "patterns": patterns_found,
        "is_doji": is_doji,
        "atr_compression": atr_compression,
    }


def analyze_macro_filter(df_1d: pd.DataFrame) -> dict:
    """
    1D EMA 200 macro filter.

    "Above 1D EMA 200 = macro bullish. Full stop." — Pentoshi
    Below 1D EMA 200 = macro bearish, reduce score -1.
    """
    if df_1d is None or len(df_1d) < EMA_SLOW:
        return {"score": 0, "above_ema_200": None, "label": "UNKNOWN"}

    close = df_1d["close"]
    ema_200 = EMAIndicator(close=close, window=EMA_SLOW).ema_indicator().iloc[-1]
    current = close.iloc[-1]

    if pd.isna(ema_200):
        return {"score": 0, "above_ema_200": None, "label": "UNKNOWN"}

    above = current > ema_200

    return {
        "score": 0.0 if above else -1.0,  # No bonus for above, just penalty for below
        "above_ema_200": above,
        "label": "MACRO_BULL" if above else "MACRO_BEAR",
        "ema_200": round(ema_200, 2),
        "price": round(current, 2),
        "distance_pct": round((current - ema_200) / ema_200 * 100, 2),
    }


def score_layer1(df_4h: pd.DataFrame, df_1d: pd.DataFrame) -> dict:
    """
    Combine all Layer 1 sub-scores.

    Range: -1.5 to +1.5 (but can be lower with macro filter)
    """
    if df_4h is None:
        return {"score": 0.0, "components": {}, "error": "No 4H data"}

    ema    = analyze_ema_stack(df_4h)
    struct = analyze_market_structure(df_4h)
    candle = analyze_candlestick_patterns(df_4h)
    macro  = analyze_macro_filter(df_1d)

    # Weighted combination
    # EMA stack is most important (Pentoshi core principle)
    # Market structure confirms direction
    # Patterns are secondary signals
    raw_score = (
        ema["score"]    * 0.5 +   # Most weight: EMA alignment
        struct["score"] * 0.35 +  # Market structure
        candle["score"] * 0.15    # Pattern confirmation
    )

    # Apply macro filter penalty
    raw_score += macro["score"]

    final = max(-2.5, min(1.5, raw_score))

    return {
        "score": round(final, 3),
        "ema": ema,
        "structure": struct,
        "candle": candle,
        "macro_filter": macro,
        "summary": _build_l1_summary(ema, struct, candle, macro),
    }


def _build_l1_summary(ema, struct, candle, macro) -> list:
    lines = []
    if ema["label"] == "BULL_STACK":
        lines.append(f"✅ EMA: 21>50>200 aligned, price above 21 EMA")
    elif ema["label"] == "BEAR_STACK":
        lines.append(f"❌ EMA: 21<50<200 bearish stack")
    else:
        lines.append(f"⚪ EMA: Mixed stack (choppy)")

    if struct["hh_hl"]:
        lines.append(f"✅ Structure: HH/HL uptrend confirmed")
    elif struct["lh_ll"]:
        lines.append(f"❌ Structure: LH/LL downtrend confirmed")

    if struct["bos_bullish"]:
        lines.append(f"⚡ BOS: Bullish break above swing high")
    if struct["choch"]:
        lines.append(f"🔄 CHoCH: Change of character — potential reversal")

    if candle["patterns"]:
        for p in candle["patterns"]:
            prefix = "✅" if "Bull" in p or "UP" in p else "❌" if "Bear" in p or "DOWN" in p else "⚠️"
            lines.append(f"{prefix} Pattern: {p}")

    if not macro["above_ema_200"]:
        lines.append(f"❌ 1D EMA 200: BELOW macro support (bearish context)")
    else:
        lines.append(f"✅ 1D EMA 200: Above macro support")

    return lines
