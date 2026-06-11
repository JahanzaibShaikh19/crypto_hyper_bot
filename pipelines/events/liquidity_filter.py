"""
pipelines/events/liquidity_filter.py — Market session and liquidity scoring.

Low liquidity periods = signals less reliable = reduce confidence.
Extreme volatility = reduce size warnings.
"""
import pandas as pd
from utils.timezone_handler import get_market_session


def analyze_liquidity(df_1h: pd.DataFrame = None) -> dict:
    """
    Returns liquidity context and confidence modifier.
    Also checks for extreme volatility.
    """
    session = get_market_session()
    confidence_mod = session["confidence_modifier"]
    volatility_warning = None

    # ATR-based volatility check
    if df_1h is not None and len(df_1h) >= 20:
        try:
            import pandas_ta as ta
            atr_series = ta.atr(df_1h["high"], df_1h["low"], df_1h["close"], length=14)
            if atr_series is not None and len(atr_series) >= 20:
                current_atr = atr_series.iloc[-1]
                avg_atr = atr_series.iloc[-20:].mean()
                if current_atr > avg_atr * 2.5:
                    volatility_warning = "⚠️ Extreme volatility detected — reduce size"
                    confidence_mod *= 0.80
        except Exception:
            pass

    return {
        "session": session["session"],
        "liquidity": session["liquidity"],
        "confidence_modifier": round(confidence_mod, 3),
        "is_weekend": session["is_weekend"],
        "is_cme_open": session["is_cme_open"],
        "session_warning": session.get("warning"),
        "volatility_warning": volatility_warning,
        "timestamp_et": session["timestamp_et"],
        "all_warnings": [
            w for w in [session.get("warning"), volatility_warning] if w
        ],
    }
