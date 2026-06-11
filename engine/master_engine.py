"""
engine/master_engine.py — Master Scoring Engine.

The brain of the entire bot. Combines all 5 pipelines,
applies Hsaka's principle of "minimum 3/5 pipeline agreement",
and decides: LONG, SHORT, or NO TRADE.

This is where all the work becomes a decision.
"""
import asyncio
import datetime
import pandas as pd
from loguru import logger

from engine.ta_scorer          import run_ta_pipeline
from engine.correlation_scorer import run_correlation_pipeline
from engine.fa_scorer          import run_fa_pipeline
from engine.sentiment_scorer   import run_sentiment_pipeline
from engine.events_scorer      import run_events_pipeline
from engine.override_rules     import apply_overrides
from config import (
    PIPELINE_WEIGHTS, LONG_THRESHOLD, SHORT_THRESHOLD,
    MIN_PIPELINE_AGREEMENT, get_signal_label
)
from storage.signal_db import was_signal_recently_fired, save_signal
from storage.signal_logger import log_signal_csv


async def run_master_engine(
    symbol: str,
    binance_data: dict,
    btc_data: dict = None,           # BTC data for cross-market reference
    global_market_data: dict = None, # Pre-fetched to avoid duplicate calls
) -> dict:
    """
    Run all 5 pipelines and produce final signal.

    This is async and runs pipelines with maximum parallelism.
    Even on a 1GB VPS this is fast enough.
    """
    start_time = datetime.datetime.utcnow()

    # Unpack binance data
    df_15m = binance_data.get("ohlcv_15m")
    df_1h  = binance_data.get("ohlcv_1h")
    df_4h  = binance_data.get("ohlcv_4h")
    df_1d  = binance_data.get("ohlcv_1d")
    funding = binance_data.get("funding", {})
    oi      = binance_data.get("oi", {})
    liq     = binance_data.get("liquidations", {})
    ticker  = binance_data.get("ticker", {})

    btc_df_1h = btc_data.get("ohlcv_1h") if btc_data else None
    current_price = float(ticker.get("price", 0)) if ticker else 0
    btc_change_24h = float(btc_data.get("ticker", {}).get("change_pct", 0)) if btc_data else 0

    # Build BTC dominance data for layer 5
    btc_dom_data = None
    if global_market_data:
        btc_dom_data = {
            "btc_dominance": global_market_data.get("btc_dominance", 50),
            "dom_direction": _infer_dom_direction(global_market_data),
        }

    logger.info(f"Running master engine for {symbol} @ ${current_price:,.2f}")

    # ─── RUN ALL 5 PIPELINES IN PARALLEL ─────────────────────────
    results = await asyncio.gather(
        _run_ta(df_15m, df_1h, df_4h, df_1d, funding, oi, liq, ticker, btc_dom_data, symbol),
        run_correlation_pipeline(symbol, btc_change_24h),
        run_fa_pipeline(symbol),
        run_sentiment_pipeline(symbol),
        run_events_pipeline(symbol, df_1h, current_price),
        return_exceptions=True,
    )

    # Unpack with fallback defaults
    def safe_result(r, pipeline_name):
        if isinstance(r, Exception):
            logger.error(f"{pipeline_name} pipeline error: {r}")
            return {"score": 0.0, "is_bullish": False, "summary": [f"Error: {r}"], "pipeline": pipeline_name}
        return r

    ta_result      = safe_result(results[0], "TECHNICAL")
    corr_result    = safe_result(results[1], "CORRELATION")
    fa_result      = safe_result(results[2], "FUNDAMENTAL")
    sent_result    = safe_result(results[3], "SENTIMENT")
    events_result  = safe_result(results[4], "EVENTS")

    pipeline_scores = {
        "ta":          ta_result["score"],
        "correlation": corr_result["score"],
        "fundamental": fa_result["score"],
        "sentiment":   sent_result["score"],
        "events":      events_result["score"],
    }

    # ─── MASTER SCORE (weighted sum) ─────────────────────────────
    master_score = sum(
        pipeline_scores[k] * PIPELINE_WEIGHTS[k]
        for k in pipeline_scores
    )
    master_score = round(master_score, 3)

    # ─── PIPELINE AGREEMENT CHECK (Hsaka's principle) ────────────
    # Count how many pipelines are bullish (score > 0)
    bullish_pipelines = sum(1 for s in pipeline_scores.values() if s > 0)
    bearish_pipelines = sum(1 for s in pipeline_scores.values() if s < 0)
    pipelines_aligned = max(bullish_pipelines, bearish_pipelines)

    # ─── APPLY OVERRIDES ─────────────────────────────────────────
    override_result = apply_overrides(
        master_score, symbol, ta_result, sent_result, btc_df_1h
    )

    if override_result["suspended"]:
        return {
            "symbol": symbol,
            "direction": "SUSPENDED",
            "master_score": 0.0,
            "pipeline_scores": pipeline_scores,
            "message": override_result.get("emergency_message", ""),
            "suspended": True,
        }

    final_score = override_result["modified_score"]
    force_direction = override_result.get("force_direction")

    # ─── DETERMINE SIGNAL DIRECTION ──────────────────────────────
    if force_direction:
        direction = force_direction
        fires = True
    elif pipelines_aligned < MIN_PIPELINE_AGREEMENT:
        # Hsaka rule: not enough consensus
        direction = "NO_TRADE"
        fires = False
        reason_no_trade = f"Only {pipelines_aligned}/5 pipelines agree (need {MIN_PIPELINE_AGREEMENT})"
    elif final_score >= LONG_THRESHOLD:
        direction = "LONG"
        fires = True
    elif final_score <= SHORT_THRESHOLD:
        direction = "SHORT"
        fires = True
    else:
        direction = "NO_TRADE"
        fires = False
        reason_no_trade = f"Score {final_score:.1f} below threshold ({LONG_THRESHOLD}/{SHORT_THRESHOLD})"

    # ─── DEDUP CHECK ─────────────────────────────────────────────
    if fires and direction in ("LONG", "SHORT"):
        if was_signal_recently_fired(symbol, direction):
            logger.info(f"Dedup: {symbol} {direction} already fired recently")
            fires = False
            direction = "NO_TRADE"

    # ─── CONFIDENCE & STRENGTH ───────────────────────────────────
    confidence = min(100, max(0, (abs(final_score) / 10) * 100))
    strength_label, strength_emoji = get_signal_label(final_score)

    # Apply liquidity confidence modifier
    liq_mod = events_result.get("confidence_modifier", 1.0)
    confidence *= liq_mod

    # ─── CALCULATE INVALIDATION CONDITIONS ───────────────────────
    invalidations = _build_invalidation_levels(df_4h, funding, ta_result, symbol)

    # ─── BUILD CONTEXT FOR SIGNAL ────────────────────────────────
    context = {
        "price": current_price,
        "direction": direction,
        "fear_greed": sent_result.get("fear_greed", {}).get("value", 50),
        "funding_rate": funding.get("funding_rate", 0),
        "btc_scenario": corr_result.get("scenario", {}).get("label", "Unknown"),
        "top_news": sent_result.get("news", {}).get("summary", [])[:3],
        "all_warnings": events_result.get("all_warnings", []) + override_result.get("overrides", []),
    }

    elapsed_ms = (datetime.datetime.utcnow() - start_time).total_seconds() * 1000
    logger.info(
        f"{'🟢 LONG' if direction == 'LONG' else '🔴 SHORT' if direction == 'SHORT' else '⚪ NO TRADE'} "
        f"{symbol} | Score: {final_score:+.1f} | "
        f"Pipelines: {bullish_pipelines}B/{bearish_pipelines}S | "
        f"[{elapsed_ms:.0f}ms]"
    )

    # ─── PERSIST SIGNAL ──────────────────────────────────────────
    if fires:
        save_signal(symbol, direction, final_score, strength_label, pipeline_scores, context)
        log_signal_csv(
            symbol=symbol,
            direction=direction,
            master_score=final_score,
            strength=strength_label,
            pipeline_scores=pipeline_scores,
            pipelines_agreeing=pipelines_aligned,
            fear_greed=context["fear_greed"],
            funding_rate=context["funding_rate"],
            price=current_price,
            context_summary=context["btc_scenario"],
        )

    return {
        "symbol": symbol,
        "direction": direction,
        "fires": fires,
        "master_score": final_score,
        "confidence": round(confidence, 1),
        "strength": strength_label,
        "strength_emoji": strength_emoji,
        "pipeline_scores": pipeline_scores,
        "pipelines_agreeing": pipelines_aligned,
        "bullish_pipelines": bullish_pipelines,
        "bearish_pipelines": bearish_pipelines,
        "context": context,
        "invalidations": invalidations,

        # Full pipeline results for Telegram formatting
        "ta":         ta_result,
        "correlation": corr_result,
        "fundamental": fa_result,
        "sentiment":   sent_result,
        "events":      events_result,

        "overrides": override_result,
        "timestamp_utc": start_time.isoformat(),
        "price": current_price,
    }


async def _run_ta(df_15m, df_1h, df_4h, df_1d, funding, oi, liq, ticker, btc_dom, symbol):
    """Thin async wrapper around synchronous TA pipeline."""
    return run_ta_pipeline(df_15m, df_1h, df_4h, df_1d, funding, oi, liq, ticker, btc_dom, symbol)


def _infer_dom_direction(global_data: dict) -> str:
    """Infer BTC.D direction from available data."""
    change = global_data.get("btc_dominance_change_24h", 0)
    if change > 0.5:
        return "RISING"
    elif change < -0.5:
        return "FALLING"
    return "NEUTRAL"


def _build_invalidation_levels(df_4h, funding, ta_result, symbol) -> list:
    """Build human-readable invalidation conditions."""
    levels = []

    # EMA 50 as key structural level
    l1 = ta_result.get("layers", {}).get("l1_trend", {})
    ema = l1.get("ema", {})
    ema_50  = ema.get("ema_50", 0)
    ema_200 = ema.get("ema_200", 0)

    if ema_50:
        levels.append(f"4H close below ${ema_50:,.0f} (EMA 50)")
    if ema_200:
        levels.append(f"4H close below ${ema_200:,.0f} (EMA 200)")

    # Funding spike
    funding_rate = funding.get("funding_rate", 0) if funding else 0
    if funding_rate < 0.05:
        levels.append("Funding rate spike above +0.05%")

    # Generic
    levels.append("Any breaking negative regulatory news")
    levels.append("BTC -5% in 1H without recovery")

    return levels[:4]
