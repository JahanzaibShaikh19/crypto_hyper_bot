"""
pipelines/technical/layer4_derivatives.py — Derivatives Engine.

Arthur Hayes' principle: "Derivatives and macro liquidity never lie."

Funding rate reveals who is OVER-LEVERAGED.
When everyone is long, funding is expensive — longs get rekt.
When everyone is short, funding is negative — shorts get rekt.
Open Interest tells us if the trend has conviction behind it.

Score range: -1 to +1
"""
import pandas as pd
from loguru import logger
from config import (
    FUNDING_VERY_BULLISH, FUNDING_BULLISH,
    FUNDING_BEARISH, FUNDING_VERY_BEARISH
)


def analyze_funding_rate(funding_data: dict) -> dict:
    """
    Interpret funding rate as a contrarian signal.

    >+0.05% = Longs very overcrowded → contrarian SHORT (-1)
    +0.01 to +0.05% = Mild long bias → mild bearish (-0.5)
    -0.01 to +0.01% = Neutral (0)
    -0.01 to -0.05% = Mild short bias → mild bullish (+0.5)
    <-0.05% = Shorts very overcrowded → contrarian LONG (+1)

    Logic: funding is paid every 8h. If rate is high, longs are
    paying shorts. This keeps happening until longs get liquidated.
    High positive funding = the market is one-sided = dangerous.
    """
    if not funding_data:
        return {"score": 0, "rate": 0, "label": "UNKNOWN"}

    rate = funding_data.get("funding_rate", 0.0)

    if rate <= FUNDING_VERY_BULLISH:   # < -0.05
        score = 1.0
        label = "VERY_OVERSOLD_SHORTS"
        interpretation = "Shorts severely over-leveraged — squeeze risk HIGH"
    elif rate <= FUNDING_BULLISH:      # -0.05 to -0.01
        score = 0.5
        label = "MILD_SHORT_BIAS"
        interpretation = "Mild short bias — slight bullish edge"
    elif rate < FUNDING_BEARISH:       # -0.01 to +0.01
        score = 0.0
        label = "NEUTRAL"
        interpretation = "Funding neutral — no leverage edge"
    elif rate < FUNDING_VERY_BEARISH:  # +0.01 to +0.05
        score = -0.5
        label = "MILD_LONG_BIAS"
        interpretation = "Longs paying premium — slight bearish edge"
    else:                               # > +0.05
        score = -1.0
        label = "VERY_OVERLEVERAGED_LONGS"
        interpretation = "Longs severely over-leveraged — liquidation risk HIGH"

    return {
        "score": round(score, 3),
        "rate": rate,
        "rate_pct": round(rate * 100, 4),
        "label": label,
        "interpretation": interpretation,
        "mark_price": funding_data.get("mark_price", 0),
    }


def analyze_open_interest(oi_data: dict, ticker_data: dict) -> dict:
    """
    OI + Price direction confirmation.

    Rising OI + Rising price = trend has conviction (bulls opening positions)
    Rising OI + Falling price = bears opening shorts (downtrend conviction)
    Falling OI + Rising price = short covering (weak rally — possible fade)
    Falling OI + Falling price = longs exiting (trend exhaustion)
    """
    if not oi_data:
        return {"score": 0, "label": "UNKNOWN", "oi_change_pct": 0}

    oi_change_pct = oi_data.get("oi_change_pct", 0)
    price_change  = ticker_data.get("change_pct", 0) if ticker_data else 0

    oi_rising  = oi_change_pct > 2     # >2% OI increase
    oi_falling = oi_change_pct < -2    # >2% OI decrease
    price_up   = price_change > 0.5    # >0.5% price increase
    price_down = price_change < -0.5   # >0.5% price decrease

    if oi_rising and price_up:
        score = 0.6
        label = "BULL_CONVICTION"
        explanation = "New money flowing in on up move — trend is real"
    elif oi_rising and price_down:
        score = -0.6
        label = "BEAR_CONVICTION"
        explanation = "New shorts opening on down move — downtrend is real"
    elif oi_falling and price_up:
        score = 0.1
        label = "SHORT_COVERING"
        explanation = "Rally driven by short covering — not new buyers"
    elif oi_falling and price_down:
        score = -0.3
        label = "LONG_LIQUIDATION"
        explanation = "Longs exiting — trend exhaustion possible"
    else:
        score = 0.0
        label = "NEUTRAL"
        explanation = "OI stable — no directional conviction"

    return {
        "score": round(score, 3),
        "label": label,
        "explanation": explanation,
        "oi_change_pct": round(oi_change_pct, 2),
        "price_change_pct": round(price_change, 2),
        "oi_rising": oi_rising,
        "oi_falling": oi_falling,
    }


def analyze_liquidations(liq_data: dict) -> dict:
    """
    Liquidation cascade detection.

    When a large cascade hits (>$10M), it often marks:
    - Long cascade: short-term bottom (longs rekt = selling pressure done)
    - Short cascade: short-term top (shorts rekt = buying pressure done)

    Post-cascade reversals are some of the cleanest setups in crypto.
    """
    if not liq_data:
        return {"score": 0, "cascade": False}

    cascade = liq_data.get("cascade_detected", False)
    long_liq  = liq_data.get("long_liq_value", 0)
    short_liq = liq_data.get("short_liq_value", 0)
    dominant  = liq_data.get("dominant_side", "NEUTRAL")

    if not cascade:
        return {
            "score": 0.0,
            "cascade": False,
            "long_liq_m": round(long_liq / 1e6, 2),
            "short_liq_m": round(short_liq / 1e6, 2),
        }

    # Post-cascade: expect reversal
    # Long cascade = longs wiped = less selling pressure = mild bullish
    # Short cascade = shorts wiped = less buying pressure = mild bearish
    if dominant == "LONGS" and long_liq > short_liq * 2:
        score = 0.4   # Long cascade = oversold bounce likely
        label = "LONG_CASCADE_BOUNCE"
    elif dominant == "SHORTS" and short_liq > long_liq * 2:
        score = -0.4  # Short cascade = overbought pullback likely
        label = "SHORT_CASCADE_REVERSAL"
    else:
        score = 0.0
        label = "MIXED_CASCADE"

    return {
        "score": round(score, 3),
        "cascade": True,
        "label": label,
        "long_liq_m": round(long_liq / 1e6, 2),
        "short_liq_m": round(short_liq / 1e6, 2),
        "dominant": dominant,
    }


def score_layer4(funding_data: dict, oi_data: dict, liq_data: dict, ticker_data: dict) -> dict:
    """Combine Layer 4 derivatives scores."""
    funding = analyze_funding_rate(funding_data)
    oi      = analyze_open_interest(oi_data, ticker_data)
    liq     = analyze_liquidations(liq_data)

    # Funding is the primary signal — it's real cost of being leveraged
    # OI confirms the funding signal
    # Liquidations are event-driven signals
    raw_score = (
        funding["score"] * 0.55 +
        oi["score"]      * 0.30 +
        liq["score"]     * 0.15
    )

    final = max(-1.0, min(1.0, raw_score))

    return {
        "score": round(final, 3),
        "funding": funding,
        "open_interest": oi,
        "liquidations": liq,
        "summary": _build_l4_summary(funding, oi, liq),
    }


def _build_l4_summary(funding, oi, liq) -> list:
    lines = []

    rate_pct = funding.get("rate_pct", 0)
    if abs(rate_pct) < 0.01:
        emoji = "⚪"
    elif funding["score"] > 0:
        emoji = "✅"
    else:
        emoji = "❌"
    lines.append(f"{emoji} Funding: {rate_pct:+.4f}% ({funding['label']})")

    oi_emoji = "✅" if oi["score"] > 0 else "❌" if oi["score"] < 0 else "⚪"
    lines.append(
        f"{oi_emoji} OI: {oi['oi_change_pct']:+.1f}% | {oi['label']}"
    )

    if liq["cascade"]:
        lines.append(
            f"⚡ Liquidation cascade: "
            f"${liq['long_liq_m']:.1f}M longs / ${liq['short_liq_m']:.1f}M shorts"
        )

    return lines
