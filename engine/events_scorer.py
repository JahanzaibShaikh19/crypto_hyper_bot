"""
engine/events_scorer.py — Events + Macro Pipeline Scorer (Pipeline 5).
Weighted at 15% of master score.
"""
import asyncio
from loguru import logger

from pipelines.events.macro_events    import score_macro_events
from pipelines.events.cme_gap         import detect_new_cme_gap, analyze_cme_gaps
from pipelines.events.coin_events     import score_coin_events
from pipelines.events.liquidity_filter import analyze_liquidity
from pipelines.correlation.cycle_position import analyze_halving_cycle
import pandas as pd


async def run_events_pipeline(symbol: str, df_1h: pd.DataFrame = None, current_price: float = 0) -> dict:
    """
    Run full events pipeline. Returns -10 to +10 score.
    """
    macro_result, coin_events_result = await asyncio.gather(
        score_macro_events(),
        score_coin_events(symbol),
        return_exceptions=True,
    )

    if isinstance(macro_result, Exception): macro_result = {"score": 0, "events": [], "fomc": {}, "warnings": []}
    if isinstance(coin_events_result, Exception): coin_events_result = {"score": 0, "events": []}

    # CME gaps (BTC only, sync analysis from DB)
    cme_result = {"score": 0, "alert": None, "summary": "N/A"}
    if symbol.startswith("BTC") and df_1h is not None and current_price > 0:
        try:
            detect_new_cme_gap(df_1h)  # Update DB with any new gaps
            cme_result = analyze_cme_gaps(current_price)
        except Exception as e:
            logger.debug(f"CME gap error: {e}")

    # Halving cycle
    halving = analyze_halving_cycle()

    # Liquidity filter
    liquidity = analyze_liquidity(df_1h)
    confidence_mod = liquidity.get("confidence_modifier", 1.0)

    # Combine scores
    raw_score = (
        macro_result["score"]       * 0.40 +   # Macro events are the biggest driver
        cme_result["score"]         * 0.20 +   # CME gaps are BTC-specific
        coin_events_result["score"] * 0.25 +   # Coin-specific events
        halving["score"]            * 0.15     # Cycle position
    )

    # Apply liquidity confidence modifier
    raw_score *= confidence_mod

    # Normalize to -10..+10
    # Raw range is approximately -4 to +4
    normalized = max(-10.0, min(10.0, raw_score * 2.5))

    # Build summary
    summary = []

    # Macro events
    for evt in macro_result.get("events", [])[:2]:
        score_emoji = "✅" if evt["score"] > 0 else "❌"
        summary.append(f"{score_emoji} {evt['type']}: {evt['summary'][:60]}")

    # FOMC warning
    fomc = macro_result.get("fomc", {})
    if fomc.get("warning"):
        summary.append(fomc.get("warning_text", ""))
    else:
        days_away = fomc.get("days_away", 999)
        if days_away < 999:
            summary.append(f"✅ Next FOMC: {fomc.get('date', '?')} ({days_away}d away)")

    # CME gaps
    if symbol.startswith("BTC"):
        summary.append(f"📊 CME: {cme_result.get('summary', 'No gaps')}")
        if cme_result.get("alert"):
            summary.append(cme_result["alert"])

    # Coin events
    for evt in coin_events_result.get("events", [])[:2]:
        phase_info = f"({evt.get('phase', '')})" if evt.get("phase") != "UNKNOWN" else ""
        score_emoji = "✅" if evt["score"] > 0 else "❌"
        summary.append(f"{score_emoji} {evt['type'].replace('_', ' ').title()} {phase_info}: {evt['description'][:50]}")

    # Halving
    summary.append(
        f"{'✅' if halving['score'] > 0 else '⚠️'} "
        f"Halving cycle: {halving['label']}"
    )

    # Liquidity warnings
    for warning in liquidity.get("all_warnings", []):
        summary.append(warning)

    # Collect all warnings
    all_warnings = list(macro_result.get("warnings", []))
    all_warnings.extend(liquidity.get("all_warnings", []))
    if cme_result.get("alert"):
        all_warnings.append(cme_result["alert"])

    return {
        "score": round(normalized, 3),
        "macro": macro_result,
        "cme": cme_result,
        "coin_events": coin_events_result,
        "halving": halving,
        "liquidity": liquidity,
        "summary": summary,
        "is_bullish": normalized > 0,
        "pipeline": "EVENTS",
        "all_warnings": all_warnings,
        "confidence_modifier": confidence_mod,
    }
