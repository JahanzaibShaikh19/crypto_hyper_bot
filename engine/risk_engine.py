"""
engine/risk_engine.py — ATR-based risk planner.

This module does not place trades. It turns a fired LONG/SHORT signal into a
clear execution plan: entry zone, stop loss, take profits, R/R, sizing, and
leverage guidance. This keeps the bot disciplined instead of becoming a noisy
signal spammer.
"""
from __future__ import annotations

from typing import Any

import pandas as pd
from ta.volatility import AverageTrueRange


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _atr(df_4h: pd.DataFrame | None, fallback_price: float) -> float:
    if df_4h is None or len(df_4h) < 20:
        return max(fallback_price * 0.015, 1.0)
    try:
        atr_series = AverageTrueRange(
            high=df_4h["high"],
            low=df_4h["low"],
            close=df_4h["close"],
            window=14,
        ).average_true_range()
        value = _safe_float(atr_series.iloc[-1])
        return value if value > 0 else max(fallback_price * 0.015, 1.0)
    except Exception:
        return max(fallback_price * 0.015, 1.0)


def _recent_swings(df: pd.DataFrame | None, lookback: int = 24) -> tuple[float, float]:
    if df is None or len(df) < 3:
        return 0.0, 0.0
    recent = df.iloc[-lookback:]
    return _safe_float(recent["low"].min()), _safe_float(recent["high"].max())


def _round_price(price: float) -> float:
    if price >= 10_000:
        return round(price, 0)
    if price >= 100:
        return round(price, 2)
    if price >= 1:
        return round(price, 4)
    return round(price, 6)


def build_risk_plan(
    symbol: str,
    direction: str,
    price: float,
    df_1h: pd.DataFrame | None,
    df_4h: pd.DataFrame | None,
    ta_result: dict,
    confidence: float = 0.0,
) -> dict:
    """Build a non-executing risk plan for a fired LONG/SHORT signal."""
    if direction not in ("LONG", "SHORT") or price <= 0:
        return {
            "enabled": False,
            "reason": "Risk plan only generated for fired LONG/SHORT signals.",
        }

    atr = _atr(df_4h, price)
    swing_low_4h, swing_high_4h = _recent_swings(df_4h)
    swing_low_1h, swing_high_1h = _recent_swings(df_1h)

    l1 = ta_result.get("layers", {}).get("l1_trend", {})
    ema = l1.get("ema", {})
    ema_50 = _safe_float(ema.get("ema_50"))
    ema_200 = _safe_float(ema.get("ema_200"))

    if confidence >= 80:
        risk_percent = 1.0
    elif confidence >= 65:
        risk_percent = 0.75
    else:
        risk_percent = 0.50

    notes = [
        "Educational risk plan only — not financial advice.",
        "Avoid chasing if price has already moved outside the entry zone.",
    ]

    if direction == "LONG":
        entry_low = price - atr * 0.25
        entry_high = price + atr * 0.10
        supports = [x for x in [swing_low_4h, swing_low_1h, ema_50, ema_200] if 0 < x < price]
        structural_stop = max(supports, default=price - atr)
        stop_loss = min(price - atr * 0.8, structural_stop - atr * 0.25)
        risk_per_unit = max(price - stop_loss, atr * 0.5)
        tp1 = price + risk_per_unit * 1.5
        tp2 = price + risk_per_unit * 2.5
        invalidation = "4H close below stop/support invalidates the long setup."
    else:
        entry_low = price - atr * 0.10
        entry_high = price + atr * 0.25
        resistances = [x for x in [swing_high_4h, swing_high_1h, ema_50, ema_200] if x > price]
        structural_stop = min(resistances, default=price + atr)
        stop_loss = max(price + atr * 0.8, structural_stop + atr * 0.25)
        risk_per_unit = max(stop_loss - price, atr * 0.5)
        tp1 = price - risk_per_unit * 1.5
        tp2 = price - risk_per_unit * 2.5
        invalidation = "4H close above stop/resistance invalidates the short setup."

    rr_to_tp2 = abs(tp2 - price) / max(abs(price - stop_loss), 1e-9)
    atr_pct = (atr / price) * 100

    if atr_pct >= 4 or confidence < 65:
        max_leverage = 2
    elif atr_pct >= 2.5:
        max_leverage = 3
    else:
        max_leverage = 5

    return {
        "enabled": True,
        "symbol": symbol,
        "direction": direction,
        "entry_low": _round_price(min(entry_low, entry_high)),
        "entry_high": _round_price(max(entry_low, entry_high)),
        "stop_loss": _round_price(stop_loss),
        "tp1": _round_price(tp1),
        "tp2": _round_price(tp2),
        "rr_to_tp2": round(rr_to_tp2, 2),
        "atr": _round_price(atr),
        "atr_pct": round(atr_pct, 2),
        "risk_percent": risk_percent,
        "max_leverage": max_leverage,
        "invalidation": invalidation,
        "notes": notes,
    }
