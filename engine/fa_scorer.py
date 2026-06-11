"""
engine/fa_scorer.py — Fundamental Analysis Pipeline Scorer (Pipeline 3).
Weighted at 15% of master score.
"""
import asyncio
from loguru import logger

from data.coingecko_fetcher import fetch_coin_data, fetch_global_market
from data.mempool_fetcher   import fetch_all_mempool
from config import coin_from_symbol


async def run_fa_pipeline(symbol: str) -> dict:
    """
    Run fundamentals pipeline. Returns -10 to +10 score.
    """
    coin_data, global_data, mempool = await asyncio.gather(
        fetch_coin_data(symbol),
        fetch_global_market(),
        fetch_all_mempool(),
        return_exceptions=True,
    )

    if isinstance(coin_data, Exception): coin_data = None
    if isinstance(global_data, Exception): global_data = {}
    if isinstance(mempool, Exception): mempool = {}

    scores = []
    summary = []

    # ─── GLOBAL MARKET DOMINANCE ────────────────────────────────
    if global_data:
        mcap_change = global_data.get("market_cap_24h_change", 0)
        if mcap_change >= 5:
            dom_score = 1.0
            summary.append("✅ Total market cap +5% — strong bull signal")
        elif mcap_change >= 2:
            dom_score = 0.5
            summary.append(f"✅ Total market cap +{mcap_change:.1f}%")
        elif mcap_change <= -5:
            dom_score = -1.0
            summary.append("❌ Total market cap -5% — strong bear signal")
        elif mcap_change <= -2:
            dom_score = -0.5
            summary.append(f"❌ Total market cap {mcap_change:.1f}%")
        else:
            dom_score = 0.0
            summary.append(f"⚪ Total market cap {mcap_change:+.1f}%")
        scores.append(("market_dom", dom_score, 0.3))

    # ─── COIN FUNDAMENTALS ──────────────────────────────────────
    if coin_data:
        coin_score = 0.0

        # Volume: above 7d average = bullish demand
        vol_7d_approx = coin_data.get("volume_24h", 0)
        vol_change = coin_data.get("price_7d_change", 0)
        if vol_change and vol_change > 10:
            coin_score += 0.4
            summary.append(f"✅ 7d price change: +{vol_change:.1f}%")
        elif vol_change and vol_change < -10:
            coin_score -= 0.4
            summary.append(f"❌ 7d price change: {vol_change:.1f}%")

        # Developer activity
        dev_score_val = coin_data.get("dev_score", 50)
        if dev_score_val >= 70:
            coin_score += 0.3
            summary.append(f"✅ Dev activity: High ({dev_score_val:.0f}/100)")
        elif dev_score_val >= 40:
            summary.append(f"⚪ Dev activity: Moderate ({dev_score_val:.0f}/100)")
        else:
            coin_score -= 0.2
            summary.append(f"⚠️ Dev activity: Low ({dev_score_val:.0f}/100)")

        # ATH distance — far from ATH = more upside potential
        ath_dist = coin_data.get("ath_distance_pct", 0)
        if ath_dist > 70:
            summary.append(f"⚪ ATH distance: {ath_dist:.0f}% below ATH (deep value)")
            coin_score += 0.1
        elif ath_dist < 10:
            summary.append(f"⚠️ Near ATH: only {ath_dist:.0f}% away")
            coin_score -= 0.2
        else:
            summary.append(f"⚪ ATH distance: {ath_dist:.0f}% below ATH")

        # Market cap rank trend (crude proxy)
        rank = coin_data.get("market_cap_rank", 999)
        if rank <= 10:
            coin_score += 0.2
        elif rank > 100:
            coin_score -= 0.1

        scores.append(("coin_fa", coin_score, 0.5))

    # ─── BITCOIN ON-CHAIN (Mempool) ──────────────────────────────
    # Only applies to BTC; for others, use as market health proxy
    if mempool and mempool.get("stats"):
        stats = mempool["stats"]
        mempool_score = stats.get("total_score", 0)

        if symbol.startswith("BTC"):
            weight = 0.3
        else:
            weight = 0.1   # For alts, BTC network health is a light signal

        if mempool_score > 0:
            summary.append(f"✅ Mempool: {stats.get('congestion', 'OK')} — {stats.get('fee_signal', '')}")
        elif mempool_score < 0:
            summary.append(f"⚪ Mempool: {stats.get('congestion', 'OK')} (low activity)")
        else:
            summary.append(f"⚪ Mempool: Normal")

        scores.append(("onchain", mempool_score, weight))

    if not scores:
        return {"score": 0.0, "summary": ["No FA data available"], "is_bullish": False, "pipeline": "FUNDAMENTAL"}

    # Normalize weights to sum to 1
    total_weight = sum(w for _, _, w in scores)
    if total_weight > 0:
        raw_score = sum(s * (w / total_weight) for _, s, w in scores)
    else:
        raw_score = 0.0

    # FA raw range is approximately -1 to +1 → normalize to -10..+10
    normalized = max(-10.0, min(10.0, raw_score * 10))

    return {
        "score": round(normalized, 3),
        "summary": summary,
        "is_bullish": normalized > 0,
        "pipeline": "FUNDAMENTAL",
        "coin_data": coin_data,
        "mempool_stats": mempool.get("stats", {}),
    }
