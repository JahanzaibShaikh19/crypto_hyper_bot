"""
pipelines/correlation/btc_dominance.py — BTC Dominance analysis.

BTC.D is the most important macro indicator in crypto.
It tells you WHERE capital is sitting in the ecosystem.
"""
from loguru import logger


def analyze_btc_dominance(global_data: dict, historical_dom: list = None) -> dict:
    """
    Analyze BTC dominance direction and extremes.

    > 60%: BTC season, capital sitting in BTC
    40-60%: Normal range, mixed
    < 40%: Deep altseason territory (historically rare, blow-off signal)

    Direction matters more than absolute level.
    """
    if not global_data:
        return {"score": 0, "dom": 50, "direction": "NEUTRAL", "label": "UNKNOWN"}

    dom = global_data.get("btc_dominance", 50)
    dom_change = global_data.get("btc_dominance_change_24h", 0)

    # Direction classification
    if dom_change > 1.0:
        direction = "RISING_FAST"
        dir_score = -0.5    # Bad for alts, good for BTC
    elif dom_change > 0.3:
        direction = "RISING"
        dir_score = -0.2
    elif dom_change < -1.0:
        direction = "FALLING_FAST"
        dir_score = 0.5     # Good for alts (altseason signal)
    elif dom_change < -0.3:
        direction = "FALLING"
        dir_score = 0.2
    else:
        direction = "NEUTRAL"
        dir_score = 0.0

    # Level extremes
    if dom > 60:
        level_note = "BTC season territory (>60%)"
        level_score = -0.3   # Alts suffering
    elif dom < 40:
        level_note = "Deep altseason (<40%) — historically near top"
        level_score = -0.3   # Watch for reversal
    elif 45 <= dom <= 55:
        level_note = "Balanced range (45-55%)"
        level_score = 0.1
    else:
        level_note = "Normal range"
        level_score = 0.0

    return {
        "score": round(dir_score + level_score, 3),
        "dom": round(dom, 2),
        "dom_change_24h": round(dom_change, 3),
        "direction": direction,
        "level_note": level_note,
        "dir_score": dir_score,
        "level_score": level_score,
        "altseason_signal": direction in ("FALLING", "FALLING_FAST") and dom < 55,
    }
