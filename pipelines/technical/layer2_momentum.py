"""
pipelines/technical/layer2_momentum.py — Momentum Analysis Engine.

Cobie's principle: "Cycle position + momentum = entry timing."

This layer answers: IS MOMENTUM BEHIND THE MOVE?
Uses RSI + MACD on 1H, EMA cross on 15m as trigger.
Divergences are the most powerful pattern in crypto momentum.

Score range: -1.5 to +1.5
"""
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, MACD
from loguru import logger
from config import RSI_PERIOD, MACD_FAST, MACD_SLOW, MACD_SIGNAL


def analyze_rsi(df_1h: pd.DataFrame) -> dict:
    """
    RSI 14 on 1H timeframe.

    45-65 trending up = +1 (healthy momentum)
    35-55 trending down = -1
    Above 75 = penalize longs (overbought)
    Below 25 = penalize shorts (oversold)
    Divergence = most powerful signal (+/- 0.5)
    """
    if df_1h is None or len(df_1h) < RSI_PERIOD + 5:
        return {"score": 0, "rsi": 50, "divergence": None}

    close = df_1h["close"]
    rsi_series = RSIIndicator(close=close, window=RSI_PERIOD).rsi()

    if rsi_series is None or rsi_series.isna().all():
        return {"score": 0, "rsi": 50, "divergence": None}

    current_rsi = rsi_series.iloc[-1]
    prev_rsi    = rsi_series.iloc[-3]  # 3 candles ago for trend

    if pd.isna(current_rsi):
        return {"score": 0, "rsi": 50, "divergence": None}

    rsi_trend_up   = current_rsi > prev_rsi
    rsi_trend_down = current_rsi < prev_rsi

    # Momentum zones
    if 45 <= current_rsi <= 65 and rsi_trend_up:
        base_score = 1.0   # Sweet spot: trending up in healthy range
    elif 35 <= current_rsi <= 55 and rsi_trend_down:
        base_score = -1.0  # Trending down
    elif current_rsi > 75:
        base_score = -0.5  # Overbought — penalize longs
    elif current_rsi < 25:
        base_score = 0.5   # Oversold — penalize shorts (not a buy signal alone)
    elif 55 <= current_rsi <= 75 and rsi_trend_up:
        base_score = 0.5   # Strong momentum but getting extended
    elif current_rsi >= 65 and rsi_trend_up:
        base_score = 0.3
    else:
        base_score = 0.0

    # Divergence detection (powerful)
    divergence = detect_rsi_divergence(df_1h, rsi_series)
    div_score = 0.0
    if divergence == "BULLISH":
        div_score = 0.5
    elif divergence == "BEARISH":
        div_score = -0.5

    final_score = max(-1.5, min(1.5, base_score + div_score))

    return {
        "score": round(final_score, 3),
        "rsi": round(current_rsi, 1),
        "rsi_prev": round(prev_rsi, 1),
        "rsi_trend": "UP" if rsi_trend_up else "DOWN" if rsi_trend_down else "FLAT",
        "divergence": divergence,
        "overbought": current_rsi > 70,
        "oversold": current_rsi < 30,
    }


def detect_rsi_divergence(df: pd.DataFrame, rsi_series: pd.Series, lookback: int = 20) -> str | None:
    """
    Divergence detection: price makes new high/low but RSI doesn't.
    This is the precursor to many major reversals.

    Bullish divergence: price makes lower low, RSI makes higher low
    Bearish divergence: price makes higher high, RSI makes lower high
    """
    if len(df) < lookback:
        return None

    try:
        price_recent = df["close"].iloc[-lookback:]
        rsi_recent   = rsi_series.iloc[-lookback:]

        # Find local extremes in the last lookback candles
        price_min_idx = price_recent.idxmin()
        price_max_idx = price_recent.idxmax()

        # Compare with earlier portion
        half = lookback // 2
        price_first_half = df["close"].iloc[-lookback:-half]
        rsi_first_half   = rsi_series.iloc[-lookback:-half]

        if price_first_half.empty or rsi_first_half.empty:
            return None

        price_earlier_low = price_first_half.min()
        rsi_earlier_low   = rsi_first_half.min()
        price_current_low = df["close"].iloc[-half:].min()
        rsi_current_low   = rsi_series.iloc[-half:].min()

        price_earlier_high = price_first_half.max()
        rsi_earlier_high   = rsi_first_half.max()
        price_current_high = df["close"].iloc[-half:].max()
        rsi_current_high   = rsi_series.iloc[-half:].max()

        # Bullish divergence: price lower low, RSI higher low
        if (price_current_low < price_earlier_low * 0.999 and
                rsi_current_low > rsi_earlier_low + 2):
            return "BULLISH"

        # Bearish divergence: price higher high, RSI lower high
        if (price_current_high > price_earlier_high * 1.001 and
                rsi_current_high < rsi_earlier_high - 2):
            return "BEARISH"

    except Exception as e:
        logger.debug(f"Divergence detection error: {e}")

    return None


def analyze_macd(df_1h: pd.DataFrame) -> dict:
    """
    MACD 12/26/9 on 1H.

    Histogram turning positive = bullish momentum building
    Histogram turning negative = bearish momentum building
    Signal line cross = directional confirmation
    """
    if df_1h is None or len(df_1h) < MACD_SLOW + MACD_SIGNAL + 5:
        return {"score": 0, "histogram": 0, "signal": "NEUTRAL"}

    close = df_1h["close"]
    macd_ind = MACD(close=close, window_slow=MACD_SLOW, window_fast=MACD_FAST, window_sign=MACD_SIGNAL)
    
    macd_diff = macd_ind.macd_diff()
    macd_line_series = macd_ind.macd()
    macd_signal_series = macd_ind.macd_signal()

    if macd_diff is None or macd_diff.isna().all():
        return {"score": 0, "histogram": 0, "signal": "NEUTRAL"}

    hist_current = macd_diff.iloc[-1]
    hist_prev    = macd_diff.iloc[-3]
    macd_line    = macd_line_series.iloc[-1]
    signal_line  = macd_signal_series.iloc[-1]

    if pd.isna(hist_current) or pd.isna(hist_prev):
        return {"score": 0, "histogram": 0, "signal": "NEUTRAL"}

    hist_turning_pos = hist_prev < 0 and hist_current > hist_prev  # Bottoming
    hist_turning_neg = hist_prev > 0 and hist_current < hist_prev  # Topping

    # MACD line vs signal line cross
    macd_bullish_cross = macd_line > signal_line
    macd_bearish_cross = macd_line < signal_line

    if hist_current > 0 and hist_turning_pos:
        score = 0.8
        signal = "STRONGLY_BULLISH"
    elif hist_current > 0 and macd_bullish_cross:
        score = 0.5
        signal = "BULLISH"
    elif hist_current > 0:
        score = 0.3
        signal = "MILD_BULLISH"
    elif hist_current < 0 and hist_turning_neg:
        score = -0.8
        signal = "STRONGLY_BEARISH"
    elif hist_current < 0 and macd_bearish_cross:
        score = -0.5
        signal = "BEARISH"
    elif hist_current < 0:
        score = -0.3
        signal = "MILD_BEARISH"
    else:
        score = 0.0
        signal = "NEUTRAL"

    return {
        "score": round(score, 3),
        "histogram": round(hist_current, 4),
        "histogram_prev": round(hist_prev, 4),
        "signal": signal,
        "histogram_turning_bullish": hist_turning_pos,
        "histogram_turning_bearish": hist_turning_neg,
    }


def analyze_entry_trigger(df_15m: pd.DataFrame) -> dict:
    """
    15m EMA 9/21 crossover for precise entry timing.
    Cobie times entries on the lower timeframe after HTF confirms direction.

    EMA 9 cross above EMA 21 = long trigger
    EMA 9 cross below EMA 21 = short trigger
    """
    if df_15m is None or len(df_15m) < 25:
        return {"score": 0, "signal": "NEUTRAL", "ema_9": 0, "ema_21": 0}

    close = df_15m["close"]
    ema_9  = EMAIndicator(close=close, window=9).ema_indicator()
    ema_21 = EMAIndicator(close=close, window=21).ema_indicator()

    if ema_9 is None or ema_21 is None:
        return {"score": 0, "signal": "NEUTRAL"}

    current_9  = ema_9.iloc[-1]
    current_21 = ema_21.iloc[-1]
    prev_9     = ema_9.iloc[-2]
    prev_21    = ema_21.iloc[-2]

    # Detect fresh cross
    bullish_cross = prev_9 <= prev_21 and current_9 > current_21
    bearish_cross = prev_9 >= prev_21 and current_9 < current_21

    # Currently aligned
    bullish_aligned = current_9 > current_21
    bearish_aligned = current_9 < current_21

    if bullish_cross:
        score  = 0.5
        signal = "LONG_TRIGGER_FRESH"
    elif bearish_cross:
        score  = -0.5
        signal = "SHORT_TRIGGER_FRESH"
    elif bullish_aligned:
        score  = 0.3
        signal = "LONG_ALIGNED"
    elif bearish_aligned:
        score  = -0.3
        signal = "SHORT_ALIGNED"
    else:
        score  = 0.0
        signal = "NEUTRAL"

    return {
        "score": round(score, 3),
        "signal": signal,
        "ema_9":  round(current_9,  2),
        "ema_21": round(current_21, 2),
        "fresh_cross": bullish_cross or bearish_cross,
    }


def score_layer2(df_1h: pd.DataFrame, df_15m: pd.DataFrame) -> dict:
    """Combine Layer 2 momentum scores."""
    if df_1h is None:
        return {"score": 0.0, "components": {}, "error": "No 1H data"}

    rsi    = analyze_rsi(df_1h)
    macd   = analyze_macd(df_1h)
    trigger = analyze_entry_trigger(df_15m)

    # Weighted: RSI = primary, MACD = confirmation, 15m = timing
    raw_score = (
        rsi["score"]     * 0.50 +
        macd["score"]    * 0.35 +
        trigger["score"] * 0.15
    )

    final = max(-1.5, min(1.5, raw_score))

    return {
        "score": round(final, 3),
        "rsi": rsi,
        "macd": macd,
        "trigger": trigger,
        "summary": _build_l2_summary(rsi, macd, trigger),
    }


def _build_l2_summary(rsi, macd, trigger) -> list:
    lines = []
    rsi_emoji = "✅" if rsi["score"] > 0 else "❌" if rsi["score"] < 0 else "⚪"
    lines.append(
        f"{rsi_emoji} RSI: {rsi['rsi']} ({'↑' if rsi['rsi_trend'] == 'UP' else '↓'})"
    )
    if rsi["divergence"]:
        lines.append(f"⚡ RSI {rsi['divergence']} Divergence detected")
    if rsi["overbought"]:
        lines.append(f"⚠️ RSI overbought — longs penalized")
    if rsi["oversold"]:
        lines.append(f"⚠️ RSI oversold")

    macd_emoji = "✅" if macd["score"] > 0 else "❌" if macd["score"] < 0 else "⚪"
    lines.append(f"{macd_emoji} MACD: histogram {macd['signal']}")

    if trigger["fresh_cross"]:
        trig_dir = "🟢" if "LONG" in trigger["signal"] else "🔴"
        lines.append(f"{trig_dir} 15m Entry trigger: {trigger['signal']}")

    return lines
