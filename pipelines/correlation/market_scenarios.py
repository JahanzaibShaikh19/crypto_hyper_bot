"""
pipelines/correlation/market_scenarios.py — Market Scenario Matrix.

The 6-scenario framework that separates good traders from great ones.
You must know WHICH scenario you're in before taking any trade.

Scenario A: Bitcoin Season  → BTC up, alts bleed
Scenario B: Altseason       → BTC flat, alts pump
Scenario C: Bull (all up)   → Everything pumping
Scenario D: Bear/Risk-off   → Everything bleeding
Scenario E: DOM Squeeze     → BTC flat, BTC.D rising fast, alts dump
Scenario F: Distribution    → BTC near ATH, volume declining
"""
from loguru import logger


def detect_scenario(global_data: dict, btc_change_24h: float) -> dict:
    """
    Takes global market data and returns the current scenario.

    Inputs from CoinGecko global:
      btc_dominance: float (percentage)
      total_market_cap: float
      market_cap_24h_change: float
      total2: float (total minus BTC cap)
      previous btc_dominance for direction
    """
    if not global_data:
        return {"scenario": "UNKNOWN", "score_modifier": 0, "description": "No market data"}

    btc_dom       = global_data.get("btc_dominance", 50)
    dom_change     = global_data.get("btc_dominance_change_24h", 0)  # pct point change
    market_cap_chg = global_data.get("market_cap_24h_change", 0)
    total2_chg     = global_data.get("total2_change_24h", 0)

    # Direction signals
    btc_rising   = btc_change_24h > 1.0
    btc_falling  = btc_change_24h < -1.0
    btc_flat     = not btc_rising and not btc_falling

    dom_rising   = dom_change > 0.3    # BTC.D gaining > 0.3 percentage points
    dom_falling  = dom_change < -0.3   # BTC.D losing > 0.3 percentage points
    dom_stable   = not dom_rising and not dom_falling

    total2_up    = total2_chg > 2.0
    total2_down  = total2_chg < -2.0
    market_up    = market_cap_chg > 2.0
    market_down  = market_cap_chg < -2.0

    # ─── SCENARIO DETECTION ────────────────────────────────────────
    # Priority order matters — some scenarios overlap

    # Scenario D: Bear / Risk-off (highest priority — capital preservation)
    if btc_falling and market_down and (total2_down or dom_falling):
        return {
            "scenario": "D_BEAR",
            "label": "BEAR / RISK-OFF",
            "emoji": "🔴",
            "description": "Everything bleeding. Risk-off. Smart money in cash/stables.",
            "btc_modifier": -2.0,
            "alt_modifier": -2.0,
            "global_modifier": -2.0,
            "action": "SHORT or NO TRADE. Capital preservation mode.",
        }

    # Scenario F: Distribution (BTC near ATH + declining volume)
    if btc_rising and dom_falling and market_cap_chg < btc_change_24h:
        # BTC up but total market cap not keeping pace = top-heavy distribution
        if btc_change_24h > 5:
            return {
                "scenario": "F_DISTRIBUTION",
                "label": "DISTRIBUTION",
                "emoji": "🟡",
                "description": "BTC near highs, alts not following. Smart money distributing.",
                "btc_modifier": -0.5,
                "alt_modifier": -1.5,
                "global_modifier": -0.5,
                "action": "Reduce longs. Watch for reversal. Tighten stops.",
            }

    # Scenario A: Bitcoin Season
    if btc_rising and dom_rising and not total2_up:
        return {
            "scenario": "A_BTC_SEASON",
            "label": "BITCOIN SEASON",
            "emoji": "🟠",
            "description": "Capital rotating INTO BTC. Alts bleeding. BTC.D rising.",
            "btc_modifier": 2.0,
            "alt_modifier": -2.0,
            "global_modifier": 1.0,
            "action": "STRONG LONG BTC. AVOID alt longs.",
        }

    # Scenario E: BTC Dominance Squeeze
    if btc_flat and dom_rising and (total2_down or not total2_up):
        return {
            "scenario": "E_DOM_SQUEEZE",
            "label": "DOMINANCE SQUEEZE",
            "emoji": "🟤",
            "description": "BTC flat but dominance rising fast. Alts getting squeezed.",
            "btc_modifier": 1.0,
            "alt_modifier": -1.5,
            "global_modifier": 0.5,
            "action": "Short alts. Long BTC only.",
        }

    # Scenario B: Altseason
    if (btc_flat or btc_rising) and dom_falling and total2_up:
        return {
            "scenario": "B_ALTSEASON",
            "label": "ALTSEASON",
            "emoji": "🌊",
            "description": "Capital rotating OUT of BTC into alts. BTC.D falling.",
            "btc_modifier": 0.0,
            "alt_modifier": 2.0,
            "global_modifier": 1.5,
            "action": "STRONG LONG alts. BTC underperforms.",
        }

    # Scenario C: Bull Market (everything up)
    if btc_rising and market_up and total2_up and dom_stable:
        return {
            "scenario": "C_BULL_ALL",
            "label": "BULL MARKET",
            "emoji": "🟢",
            "description": "Everything pumping. Risk-on, high confidence. BTC.D stable.",
            "btc_modifier": 1.5,
            "alt_modifier": 1.5,
            "global_modifier": 1.5,
            "action": "LONG everything with high confidence.",
        }

    # Default: uncertain
    return {
        "scenario": "X_UNCERTAIN",
        "label": "UNCERTAIN",
        "emoji": "⚪",
        "description": "Mixed signals. No clear scenario. Reduce position sizing.",
        "btc_modifier": 0.0,
        "alt_modifier": 0.0,
        "global_modifier": 0.0,
        "action": "Wait for clarity. No trade is a valid trade.",
    }


def get_scenario_modifier(scenario_data: dict, symbol: str) -> float:
    """
    Returns the score modifier to apply to signals for this symbol
    based on current scenario.
    """
    if not scenario_data:
        return 0.0

    is_btc = symbol.upper().startswith("BTC")

    if is_btc:
        return scenario_data.get("btc_modifier", 0.0)
    else:
        return scenario_data.get("alt_modifier", 0.0)
