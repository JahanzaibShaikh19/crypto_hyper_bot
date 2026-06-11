"""
engine/sentiment_scorer.py — News + Social Sentiment Pipeline Scorer (Pipeline 4).
Weighted at 15% of master score.
"""
import asyncio
from loguru import logger

from data.fear_greed_fetcher import fetch_fear_greed
from data.news_fetcher       import fetch_cryptopanic, fetch_binance_announcements, aggregate_news_score
from data.social_fetcher     import fetch_all_nitter, fetch_all_reddit, fetch_all_youtube, aggregate_social_score
from config import coin_from_symbol


async def run_sentiment_pipeline(symbol: str) -> dict:
    """
    Run full sentiment pipeline. Returns -10 to +10 score.
    Emergency bearish overrides if hack/SEC/ban detected.
    """
    coin_short = coin_from_symbol(symbol)

    # Fetch all sources in parallel
    results = await asyncio.gather(
        fetch_fear_greed(),
        fetch_cryptopanic(symbol),
        fetch_cryptopanic(None),          # General market news
        fetch_binance_announcements(),
        fetch_all_nitter(),
        fetch_all_reddit(),
        fetch_all_youtube(),
        return_exceptions=True,
    )

    def safe(r, default):
        return default if isinstance(r, Exception) else (r or default)

    fg       = safe(results[0], {"value": 50, "signal_score": 0, "label": "Neutral"})
    coin_news = safe(results[1], [])
    mkt_news  = safe(results[2], [])
    binance_rss = safe(results[3], [])
    tweets    = safe(results[4], [])
    reddit    = safe(results[5], [])
    youtube   = safe(results[6], [])

    summary = []
    component_scores = {}
    emergency_override = None

    # ─── 1. FEAR & GREED ─────────────────────────────────────────
    fg_score = fg.get("signal_score", 0)
    component_scores["fear_greed"] = fg_score

    fg_emoji = "😱" if fg["value"] <= 25 else "😨" if fg["value"] <= 45 else \
               "😊" if fg["value"] <= 55 else "😁" if fg["value"] <= 75 else "🤑"
    summary.append(
        f"{fg_emoji} Fear & Greed: {fg['value']} → {fg.get('label', 'Neutral')}"
        + (" (contrarian bullish)" if fg_score > 0.5 else
           " (contrarian bearish)" if fg_score < -0.5 else "")
    )
    if fg.get("momentum_shift"):
        summary.append(f"⚡ F&G momentum shift: {fg.get('shift_direction', '')}")

    # ─── 2. NEWS SENTIMENT ───────────────────────────────────────
    all_news  = coin_news + mkt_news
    news_agg  = aggregate_news_score(all_news)
    news_score = news_agg.get("score", 0)
    component_scores["news"] = news_score

    if news_agg.get("emergency"):
        emergency_override = {
            "type": "BEARISH_NEWS",
            "reason": news_agg.get("emergency_reason", "Breaking bearish news"),
            "keywords": news_agg.get("emergency_keywords", []),
        }
        summary.append(f"🚨 EMERGENCY: {news_agg['emergency_reason'][:80]}")
    elif news_score > 1:
        summary.append(f"✅ CryptoPanic: {news_agg.get('avg_vote_ratio', 0.5)*100:.0f}% bullish votes")
    elif news_score < -1:
        summary.append(f"❌ CryptoPanic: Negative news flow")
    else:
        summary.append("⚪ CryptoPanic: Mixed news")

    # Top headlines
    for headline in news_agg.get("summary", [])[:2]:
        summary.append(f"  📰 {headline[:70]}")

    # ─── 3. BINANCE ANNOUNCEMENTS ────────────────────────────────
    listing_override = None
    for item in binance_rss:
        if item.get("signal_type") == "LISTING":
            # Check if it's for our symbol
            if coin_short.lower() in item.get("title", "").lower():
                listing_override = {
                    "type": "BINANCE_LISTING",
                    "title": item["title"],
                    "score_override": 2.0,
                }
                summary.append(f"🚀 Binance listing: {item['title'][:60]}")
        elif item.get("signal_type") == "DELISTING":
            if coin_short.lower() in item.get("title", "").lower():
                emergency_override = {
                    "type": "DELISTING",
                    "reason": item["title"],
                }
                summary.append(f"🚨 Delisting notice: {item['title'][:60]}")

    if binance_rss and not listing_override:
        summary.append("📢 Binance RSS: No critical announcements")

    # ─── 4. SOCIAL SENTIMENT ─────────────────────────────────────
    social_agg = aggregate_social_score(tweets, reddit, youtube)
    social_score = social_agg.get("score", 0)
    component_scores["social"] = social_score

    # Macro oracle override
    if social_agg.get("macro_override"):
        mo = social_agg["macro_override"]
        summary.append(
            f"⚠️ MACRO ORACLE @{mo['account']}: "
            f"'{mo['text'][:60]}' (score impact: {mo['score_impact']:+.1f})"
        )
        social_score += mo["score_impact"]

    # Influencer bullish highlights
    for inf in social_agg.get("influencer_bullish", [])[:1]:
        summary.append(f"✅ @{inf['account']}: '{inf['text'][:60]}'")

    social_emoji = "✅" if social_score > 0.5 else "❌" if social_score < -0.5 else "⚪"
    summary.append(
        f"{social_emoji} Social: {social_agg['tweet_count']} tweets, "
        f"{social_agg['reddit_count']} reddit, {social_agg['yt_count']} YT"
    )

    # ─── AGGREGATE ───────────────────────────────────────────────
    # Emergency override = instant bearish
    if emergency_override:
        final_raw = -4.0
    elif listing_override:
        final_raw = 4.0
    else:
        # Weighted: F&G is contrarian, news is direct, social is amplifier
        final_raw = (
            fg_score    * 3.0 * 0.35 +   # Scaled from -1..+1 to -3..+3
            news_score  * 0.30 +
            social_score * 0.25 +
            0.0 * 0.10  # Room for more sources
        )

    # Normalize to -10..+10
    normalized = max(-10.0, min(10.0, final_raw * 2.5))

    return {
        "score": round(normalized, 3),
        "fear_greed": fg,
        "news": news_agg,
        "social": social_agg,
        "component_scores": component_scores,
        "emergency_override": emergency_override,
        "listing_override": listing_override,
        "summary": summary,
        "is_bullish": normalized > 0,
        "pipeline": "SENTIMENT",
    }
