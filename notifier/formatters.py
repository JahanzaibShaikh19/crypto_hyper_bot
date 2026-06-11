"""
notifier/formatters.py — Telegram message formatters.

The signal message is the product. It must be:
1. Information dense but scannable
2. Actionable (has invalidation conditions)
3. Educational (explains WHY, not just what)
4. Honest (shows confidence, not just direction)
"""
import datetime
from config import PIPELINE_WEIGHTS


def format_signal(result: dict) -> str:
    """
    Format the full signal message exactly as designed in the spec.
    Returns a ready-to-send Telegram message (Markdown).
    """
    symbol   = result["symbol"]
    direction = result["direction"]
    score    = result["master_score"]
    strength = result["strength"]
    emoji    = result["strength_emoji"]
    confidence = result["confidence"]
    pipelines  = result["pipelines_agreeing"]
    price      = result["price"]
    ts         = result.get("timestamp_utc", datetime.datetime.utcnow().isoformat())[:16]

    ta_score   = result["pipeline_scores"].get("ta", 0)
    corr_score = result["pipeline_scores"].get("correlation", 0)
    fa_score   = result["pipeline_scores"].get("fundamental", 0)
    sent_score = result["pipeline_scores"].get("sentiment", 0)
    evt_score  = result["pipeline_scores"].get("events", 0)

    direction_emoji = "🟢" if direction == "LONG" else "🔴" if direction == "SHORT" else "⚪"
    pipelines_display = "✅" if pipelines >= 4 else "⚠️" if pipelines == 3 else "❌"

    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"{direction_emoji} *{direction} SIGNAL — {symbol}*",
        f"{emoji} *{strength}*",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📊 *Master Score:* {score:+.1f} / 10",
        f"🎯 *Confidence:* {confidence:.0f}% | *Pipelines:* {pipelines}/5 {pipelines_display}",
        f"💰 *Price:* ${price:,.2f}",
        "",
    ]

    # ─── TECHNICAL ────────────────────────────────────────────────
    ta = result.get("ta", {})
    ta_color = "🟢" if ta_score > 0 else "🔴" if ta_score < 0 else "⚪"
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"📈 *TECHNICAL [{ta_color} {ta_score:+.1f}/10]*")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    for line in ta.get("summary", [])[:8]:
        lines.append(line)

    lines.append("")

    # ─── CORRELATION ──────────────────────────────────────────────
    corr = result.get("correlation", {})
    corr_color = "🟢" if corr_score > 0 else "🔴" if corr_score < 0 else "⚪"
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🔗 *BTC/DOMINANCE/USD [{corr_color} {corr_score:+.1f}/10]*")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    for line in corr.get("summary", [])[:6]:
        lines.append(line)

    # Altseason signal
    if corr.get("altseason_signal") and not symbol.startswith("BTC"):
        lines.append("🌊 *Altseason signal forming* — BTC.D falling fast")

    lines.append("")

    # ─── FUNDAMENTALS ─────────────────────────────────────────────
    fa = result.get("fundamental", {})
    fa_color = "🟢" if fa_score > 0 else "🔴" if fa_score < 0 else "⚪"
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🏛️ *FUNDAMENTALS [{fa_color} {fa_score:+.1f}/10]*")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    for line in fa.get("summary", [])[:5]:
        lines.append(line)

    lines.append("")

    # ─── NEWS + SOCIAL ─────────────────────────────────────────────
    sent = result.get("sentiment", {})
    sent_color = "🟢" if sent_score > 0 else "🔴" if sent_score < 0 else "⚪"
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"📰 *NEWS + SOCIAL [{sent_color} {sent_score:+.1f}/10]*")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    for line in sent.get("summary", [])[:8]:
        lines.append(line)

    lines.append("")

    # ─── EVENTS + MACRO ────────────────────────────────────────────
    events = result.get("events", {})
    evt_color = "🟢" if evt_score > 0 else "🔴" if evt_score < 0 else "⚪"
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"📅 *EVENTS + MACRO [{evt_color} {evt_score:+.1f}/10]*")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    for line in events.get("summary", [])[:8]:
        lines.append(line)

    lines.append("")

    # ─── MARKET CONTEXT ────────────────────────────────────────────
    ctx = result.get("context", {})
    fg_value = ctx.get("fear_greed", 50)
    funding  = ctx.get("funding_rate", 0)

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("📋 *24H MARKET CONTEXT*")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"- Fear & Greed: {fg_value}")
    lines.append(f"- Funding rate: {funding*100:+.4f}%")
    lines.append(f"- Market scenario: {ctx.get('btc_scenario', 'Unknown')}")

    for news in ctx.get("top_news", [])[:2]:
        lines.append(f"- {news[:70]}")

    # Session
    liq = events.get("liquidity", {})
    session = liq.get("session", "UNKNOWN")
    liq_level = liq.get("liquidity", "UNKNOWN")
    lines.append(f"- Session: {session} | Liquidity: {liq_level}")

    lines.append("")

    # ─── INVALIDATION ─────────────────────────────────────────────
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("⛔ *INVALIDATION CONDITIONS*")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    for inv in result.get("invalidations", []):
        lines.append(f"- {inv}")

    # ─── WARNINGS ─────────────────────────────────────────────────
    all_warnings = ctx.get("all_warnings", [])
    if all_warnings:
        lines.append("")
        for w in all_warnings[:3]:
            lines.append(str(w))

    # ─── FOOTER ────────────────────────────────────────────────────
    lines.append("")
    lines.append(f"🕐 *Signal:* {ts} UTC")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("⚠️ _FOR EDUCATIONAL PURPOSES ONLY — DYOR_")

    return "\n".join(lines)


def format_pre_event_warning(event_name: str, hours_away: float, current_direction: str) -> str:
    return (
        f"⚠️ *HIGH IMPACT EVENT ALERT*\n"
        f"{event_name} in ~{hours_away:.0f} hours\n"
        f"Historical crypto reaction: ±4-8% volatile\n"
        f"📌 Recommendation: Reduce position sizes\n"
        f"Current signal: {current_direction} — *wait for event confirmation*"
    )


def format_cme_gap_alert(gap_price: float, gap_type: str, distance_pct: float, gap_date: str) -> str:
    direction = "above" if gap_type == "UP" else "below"
    return (
        f"🎯 *CME GAP FILL APPROACHING*\n"
        f"Gap level: ${gap_price:,.0f} ({direction} current price)\n"
        f"Distance: {distance_pct:.2f}%\n"
        f"Gap from: {gap_date}\n"
        f"Historical fill rate: ~78%\n"
        f"Watch for price reaction at this level"
    )


def format_whale_alert(account: str, text: str, sentiment: float, score_boost: float) -> str:
    emoji = "🟢" if sentiment > 0 else "🔴"
    return (
        f"🐋 *KEY ACCOUNT POST DETECTED*\n"
        f"Account: @{account}\n"
        f"Posted: '{text[:120]}'\n"
        f"{emoji} Sentiment: {'Bullish' if sentiment > 0 else 'Bearish'}\n"
        f"Signal impact: {score_boost:+.1f} added to score"
    )


def format_altseason_alert(btc_dom_before: float, btc_dom_after: float, total2_change: float) -> str:
    dom_change = btc_dom_after - btc_dom_before
    return (
        f"🌊 *ALTSEASON INDICATOR TRIGGERED*\n"
        f"BTC.D: {btc_dom_before:.1f}% → {btc_dom_after:.1f}% ({dom_change:+.1f}%)\n"
        f"Total alt market cap: {total2_change:+.1f}% in 48h\n"
        f"Historical pattern: Altseason typically follows within 2-4 weeks\n"
        f"📌 Recommended: Shift focus to quality alts"
    )


def format_black_swan(change_pct: float, top_news: list) -> str:
    news_str = top_news[0][:80] if top_news else "Unknown cause"
    return (
        f"🚨 *BLACK SWAN DETECTED*\n"
        f"BTC dropped {change_pct:.1f}% in 1 hour\n"
        f"*ALL SIGNALS SUSPENDED*\n"
        f"Likely cause: {news_str}\n"
        f"Action: DO NOT TRADE until stabilization\n"
        f"Next scan: 1 hour from now"
    )


def format_no_trade(symbol: str, score: float, pipelines: int, reason: str) -> str:
    return (
        f"⚪ *NO TRADE — {symbol}*\n"
        f"Score: {score:+.1f}/10 | Pipelines: {pipelines}/5\n"
        f"Reason: {reason}\n"
        f"_Hsaka: Patience IS the alpha. Wait for confluence._"
    )
