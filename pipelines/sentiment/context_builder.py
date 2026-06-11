"""
pipelines/sentiment/context_builder.py — Context Window Builder.

Before every signal, compile the full 24h market context.
This gives the trader the "why" behind the signal.

Context includes:
- Top 3 news headlines
- Price action (high, low, key levels)
- Notable social posts
- Emergency flags
- Current market narrative
"""
import datetime
import pandas as pd
from loguru import logger


def build_context_window(
    symbol: str,
    df_1h: pd.DataFrame,
    fear_greed: dict,
    news_items: list,
    tweets: list,
    funding_data: dict,
    ticker_data: dict,
    scenario: dict,
) -> dict:
    """
    Builds the full context window for a signal.
    Returns a structured dict and a human-readable summary.
    """
    context = {
        "symbol": symbol,
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "price_context": {},
        "sentiment_context": {},
        "news_context": {},
        "social_context": {},
        "narrative": "",
        "emergency_flags": [],
    }

    # ─── PRICE CONTEXT ────────────────────────────────────────────
    if df_1h is not None and len(df_1h) >= 24:
        last_24h = df_1h.iloc[-24:]
        context["price_context"] = {
            "current":    round(float(df_1h["close"].iloc[-1]), 2),
            "high_24h":   round(float(last_24h["high"].max()), 2),
            "low_24h":    round(float(last_24h["low"].min()), 2),
            "change_pct": round(float(ticker_data.get("change_pct", 0)), 2) if ticker_data else 0,
            "volume_24h": round(float(last_24h["volume"].sum()), 0),
        }

    # ─── SENTIMENT CONTEXT ────────────────────────────────────────
    context["sentiment_context"] = {
        "fear_greed_value": fear_greed.get("value", 50),
        "fear_greed_label": fear_greed.get("label", "Neutral"),
        "fear_greed_24h_change": fear_greed.get("change_24h", 0),
        "funding_rate": funding_data.get("funding_rate", 0) if funding_data else 0,
        "market_scenario": scenario.get("label", "Unknown") if scenario else "Unknown",
    }

    # ─── NEWS CONTEXT ─────────────────────────────────────────────
    # Top 3 recent news by recency weight
    sorted_news = sorted(
        news_items,
        key=lambda x: x.get("recency_weight", 1.0),
        reverse=True,
    )[:3]

    context["news_context"] = {
        "top_headlines": [n.get("title", "")[:80] for n in sorted_news],
        "avg_sentiment": (
            sum(n.get("sentiment", 0) for n in sorted_news) / len(sorted_news)
            if sorted_news else 0
        ),
        "emergency_flags": [
            n.get("title", "")
            for n in news_items
            if n.get("has_emergency", False)
        ],
    }

    # ─── SOCIAL CONTEXT ───────────────────────────────────────────
    high_impact_tweets = [
        t for t in tweets
        if t.get("is_high_influence") or t.get("is_macro_oracle")
    ]
    sorted_tweets = sorted(
        high_impact_tweets,
        key=lambda x: abs(x.get("sentiment", 0)),
        reverse=True,
    )[:2]

    context["social_context"] = {
        "notable_posts": [
            {
                "account": t.get("account", ""),
                "text": t.get("text", "")[:100],
                "sentiment": t.get("sentiment", 0),
            }
            for t in sorted_tweets
        ],
    }

    # ─── EMERGENCY FLAGS ─────────────────────────────────────────
    context["emergency_flags"] = context["news_context"]["emergency_flags"]

    # ─── NARRATIVE ────────────────────────────────────────────────
    context["narrative"] = _build_narrative(
        fear_greed, scenario, context["price_context"]
    )

    return context


def _build_narrative(fear_greed: dict, scenario: dict, price: dict) -> str:
    """Build a short natural language market narrative."""
    parts = []

    fg_val = fear_greed.get("value", 50)
    if fg_val <= 25:
        parts.append("Market is in extreme fear — contrarian opportunity")
    elif fg_val >= 75:
        parts.append("Market is in extreme greed — be cautious")
    elif fg_val <= 45:
        parts.append("Fearful market conditions — mild opportunity bias")
    elif fg_val >= 55:
        parts.append("Greedy market conditions — mild caution bias")
    else:
        parts.append("Market sentiment is neutral")

    if scenario:
        parts.append(scenario.get("description", ""))

    change = price.get("change_pct", 0)
    if abs(change) > 3:
        dir_word = "up" if change > 0 else "down"
        parts.append(f"Price moved {change:+.1f}% in 24h — trending {dir_word}")

    return " | ".join(filter(None, parts))
