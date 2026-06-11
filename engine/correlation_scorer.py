"""
engine/correlation_scorer.py — BTC/DOM/USD/Alts Correlation Pipeline Scorer.

Pipeline 2, weighted at 20% of master score.
Answers: WHAT IS THE MACRO CRYPTO ENVIRONMENT?
"""
import asyncio
from loguru import logger

from pipelines.correlation.btc_dominance  import analyze_btc_dominance
from pipelines.correlation.usd_strength   import fetch_dxy_proxy
from pipelines.correlation.market_scenarios import detect_scenario, get_scenario_modifier
from pipelines.correlation.cycle_position  import analyze_halving_cycle, analyze_market_cap_cycle
from data.coingecko_fetcher                import fetch_global_market, fetch_market_history


async def run_correlation_pipeline(symbol: str, btc_change_24h: float = 0) -> dict:
    """
    Run full correlation pipeline.
    Returns -10 to +10 normalized score.
    """
    global_data, market_history, dxy = await asyncio.gather(
        fetch_global_market(),
        fetch_market_history("bitcoin", days=90),
        fetch_dxy_proxy(),
        return_exceptions=True,
    )

    # Handle exceptions
    if isinstance(global_data, Exception) or global_data is None:
        global_data = {}
    if isinstance(market_history, Exception):
        market_history = []
    if isinstance(dxy, Exception) or dxy is None:
        dxy = {"score": 0, "level": "UNKNOWN", "note": "Unavailable"}

    # Add dominance change (we'd need historical for this; approximate with 0)
    global_data["btc_dominance_change_24h"] = global_data.get("btc_dominance_change_24h", 0)
    global_data["total2_change_24h"]         = global_data.get("total2_change_24h", global_data.get("market_cap_24h_change", 0))

    # Run sub-analyses
    dom_analysis    = analyze_btc_dominance(global_data)
    scenario        = detect_scenario(global_data, btc_change_24h)
    halving         = analyze_halving_cycle()
    mcap_cycle      = analyze_market_cap_cycle(market_history if isinstance(market_history, list) else [])

    # Get symbol-specific scenario modifier
    scenario_mod = get_scenario_modifier(scenario, symbol)

    # Combine scores
    # DOM direction + Scenario + DXY + Cycle position
    raw_score = (
        dom_analysis["score"] * 0.25 +
        (scenario_mod / 5)    * 0.35 +   # Normalize scenario modifier (-2..+2) to roughly -1..+1
        dxy["score"]          * 0.20 +
        halving["score"]      * 0.10 +
        mcap_cycle["score"]   * 0.10
    )

    # Natural range approximation
    min_poss = -1.0 * (0.25 + 0.35 + 0.20 + 0.10 + 0.10)
    max_poss =  1.0 * (0.25 + 0.35 + 0.20 + 0.10 + 0.10)

    normalized = (raw_score / max_poss) * 10 if max_poss != 0 else 0
    normalized = max(-10.0, min(10.0, normalized))

    # Build summary
    summary = []
    summary.append(f"{scenario['emoji']} Scenario: {scenario['label']}")
    summary.append(f"   {scenario['description']}")
    summary.append(
        f"{'✅' if dom_analysis['score'] > 0 else '❌' if dom_analysis['score'] < 0 else '⚪'} "
        f"BTC.D: {dom_analysis['dom']:.1f}% {dom_analysis['direction']}"
    )
    summary.append(f"⚪ DXY: {dxy.get('note', 'Unknown')}")
    summary.append(
        f"{'✅' if halving['score'] > 0 else '⚠️'} "
        f"Halving cycle: {halving['label']}"
    )
    if mcap_cycle.get("note"):
        summary.append(
            f"{'✅' if mcap_cycle['score'] > 0 else '❌'} "
            f"Market cycle: {mcap_cycle['note']}"
        )

    return {
        "score": round(normalized, 3),
        "dominance": dom_analysis,
        "scenario": scenario,
        "scenario_modifier": scenario_mod,
        "dxy": dxy,
        "halving": halving,
        "market_cycle": mcap_cycle,
        "summary": summary,
        "is_bullish": normalized > 0,
        "pipeline": "CORRELATION",
        "altseason_signal": dom_analysis.get("altseason_signal", False),
    }
