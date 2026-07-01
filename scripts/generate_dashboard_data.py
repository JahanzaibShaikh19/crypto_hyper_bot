from __future__ import annotations

import json
import os
import statistics
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SPOT = "https://api.binance.com"
FUTURES = "https://fapi.binance.com"
FNG = "https://api.alternative.me/fng/"
OUT = Path("frontend/public/data/dashboard.json")
WATCHLIST = [s.strip().upper() for s in os.getenv("WATCHLIST", "BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,AVAXUSDT").split(",") if s.strip()]


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def get_json(url, params=None):
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "crypto-hyper-bot-dashboard"})
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            return json.loads(res.read().decode("utf-8"))
    except Exception as exc:
        print("request failed", url, exc)
        return None


def fnum(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def money(value):
    value = fnum(value)
    if value >= 1000:
        return f"${value:,.2f}"
    if value >= 1:
        return f"${value:,.4f}"
    return f"${value:,.6f}"


def pct(value):
    return f"{fnum(value):+.2f}%"


def tone(value, dead=0.15):
    value = fnum(value)
    if value > dead:
        return "up"
    if value < -dead:
        return "down"
    return "flat"


def sma(values, window):
    if not values:
        return 0.0
    if len(values) < window:
        return statistics.mean(values)
    return statistics.mean(values[-window:])


def rsi(values, window=14):
    if len(values) <= window:
        return 50.0
    gains, losses = [], []
    for prev, curr in zip(values[-window - 1:-1], values[-window:]):
        change = curr - prev
        gains.append(max(change, 0))
        losses.append(abs(min(change, 0)))
    avg_gain = statistics.mean(gains) if gains else 0
    avg_loss = statistics.mean(losses) if losses else 0
    if avg_loss == 0:
        return 100.0
    return 100 - (100 / (1 + (avg_gain / avg_loss)))


def clamp(value, low, high):
    return max(low, min(high, value))


def fetch_symbol(symbol):
    ticker = get_json(f"{SPOT}/api/v3/ticker/24hr", {"symbol": symbol}) or {}
    klines = get_json(f"{SPOT}/api/v3/klines", {"symbol": symbol, "interval": "1h", "limit": 80}) or []
    funding = get_json(f"{FUTURES}/fapi/v1/premiumIndex", {"symbol": symbol}) or {}
    closes = [fnum(k[4]) for k in klines if len(k) > 4]
    highs = [fnum(k[2]) for k in klines if len(k) > 4]
    lows = [fnum(k[3]) for k in klines if len(k) > 4]
    price = fnum(ticker.get("lastPrice")) or (closes[-1] if closes else 0)
    atr = statistics.mean([(h - l) for h, l in zip(highs[-14:], lows[-14:])]) if highs and lows else price * 0.015
    return {
        "symbol": symbol,
        "price": price,
        "change": fnum(ticker.get("priceChangePercent")),
        "volume": fnum(ticker.get("quoteVolume")),
        "funding": fnum(funding.get("lastFundingRate")) * 100,
        "closes": closes,
        "sma20": sma(closes, 20),
        "sma50": sma(closes, 50),
        "rsi": rsi(closes),
        "atr": atr,
    }


def fear_greed():
    data = get_json(FNG, {"limit": 1}) or {}
    row = (data.get("data") or [{}])[0]
    return {"value": int(fnum(row.get("value"), 50)), "label": row.get("value_classification") or "Neutral"}


def score(data, btc_change, fg):
    technical = 0
    technical += 2.2 if data["price"] > data["sma20"] else -1.8
    technical += 2.0 if data["sma20"] > data["sma50"] else -1.5
    technical += 1.4 if 48 <= data["rsi"] <= 70 else -1.0
    technical += clamp(data["change"] / 2.5, -2, 2)
    correlation = clamp((btc_change + data["change"]) / 2, -8, 8)
    fundamental = 2.0 if data["volume"] > 1_000_000_000 else 1.0 if data["volume"] > 200_000_000 else -0.5
    sentiment = (fg["value"] - 50) / 8
    events = -1.5 if data["funding"] > 0.08 else 1.0 if data["funding"] < -0.03 else 0.5
    master = technical * 0.40 + correlation * 0.20 + fundamental * 0.15 + sentiment * 0.10 + events * 0.15
    values = [technical, correlation, fundamental, sentiment, events]
    aligned = max(sum(v > 0 for v in values), sum(v < 0 for v in values))
    if master >= 5.5 and aligned >= 3:
        direction, t = "LONG", "up"
    elif master <= -5.5 and aligned >= 3:
        direction, t = "SHORT", "down"
    elif master >= 3.2:
        direction, t = "LONG WATCH", "up"
    elif master <= -3.2:
        direction, t = "SHORT WATCH", "down"
    else:
        direction, t = "WAIT", "flat"
    return {
        "symbol": data["symbol"],
        "direction": direction,
        "score": f"{master:+.1f}",
        "scoreRaw": round(master, 3),
        "confidence": f"{clamp(abs(master) / 8 * 100, 18, 96):.0f}%",
        "price": money(data["price"]),
        "priceRaw": data["price"],
        "change": pct(data["change"]),
        "tone": t,
        "reason": f"SMA20 {'above' if data['sma20'] > data['sma50'] else 'below'} SMA50, RSI {data['rsi']:.0f}, funding {data['funding']:+.3f}%",
        "pipelines": {
            "Technical": round(technical, 2),
            "Correlation": round(correlation, 2),
            "Fundamental": round(fundamental, 2),
            "Sentiment": round(sentiment, 2),
            "Events": round(events, 2),
        }
    }


def chart_points(closes):
    sample = closes[-28:] or [1]
    lo, hi = min(sample), max(sample)
    if hi == lo:
        return [70 for _ in sample]
    return [int(38 + ((v - lo) / (hi - lo)) * 92) for v in sample]


def risk(best, data):
    price, atr = data.get("price", 0), data.get("atr", 0) or data.get("price", 0) * 0.015
    if "LONG" in best["direction"]:
        return {"entryZone": f"{money(price - atr * .25)} — {money(price + atr * .12)}", "stopLoss": money(price - atr * 1.15), "targets": f"{money(price + atr * 1.65)} / {money(price + atr * 2.65)}", "rr": "1:2.30", "note": "Educational risk plan only."}
    if "SHORT" in best["direction"]:
        return {"entryZone": f"{money(price - atr * .12)} — {money(price + atr * .25)}", "stopLoss": money(price + atr * 1.15), "targets": f"{money(price - atr * 1.65)} / {money(price - atr * 2.65)}", "rr": "1:2.30", "note": "Educational risk plan only."}
    return {"entryZone": "No trade zone", "stopLoss": "Wait for confluence", "targets": "—", "rr": "—", "note": "Market does not meet signal threshold."}


def main():
    fg = fear_greed()
    raw = {}
    for symbol in WATCHLIST:
        raw[symbol] = fetch_symbol(symbol)
        time.sleep(0.12)
    btc_change = raw.get("BTCUSDT", {}).get("change", 0)
    signals = [score(item, btc_change, fg) for item in raw.values() if item.get("price")]
    signals.sort(key=lambda x: abs(x["scoreRaw"]), reverse=True)
    best = signals[0] if signals else {"symbol": "BTCUSDT", "direction": "WAIT", "scoreRaw": 0, "pipelines": {}, "tone": "flat"}
    best_raw = raw.get(best["symbol"], {})
    dash = {
        "generatedAt": now_iso(),
        "source": "github-actions-hourly-snapshot",
        "status": {"mode": "live", "message": "Latest public market snapshot generated successfully."},
        "marketStats": [
            {"label": s, "value": money(raw.get(s, {}).get("price", 0)), "change": pct(raw.get(s, {}).get("change", 0)), "tone": tone(raw.get(s, {}).get("change", 0))}
            for s in ["BTCUSDT", "ETHUSDT"]
        ] + [{"label": "BTC.D", "value": "Proxy", "change": "live soon", "tone": "flat"}, {"label": "Fear & Greed", "value": str(fg["value"]), "change": fg["label"], "tone": "warn"}],
        "signals": signals[:6],
        "watchlist": [[x["symbol"].replace("USDT", ""), x["score"], x["direction"]] for x in signals[:8]],
        "pipelines": [{"name": k, "score": round(abs(v), 1), "tone": tone(v, .3)} for k, v in best.get("pipelines", {}).items()],
        "chart": {"symbol": best["symbol"], "timeframe": "1H", "points": chart_points(best_raw.get("closes", []))},
        "riskPlan": risk(best, best_raw),
        "performance": {"winRate": "Live soon", "tracked": "0", "avgMove": "Live soon", "bestPair": best["symbol"].replace("USDT", "")},
        "system": {"lastWorkflow": now_iso(), "nextUpdate": "Hourly GitHub Actions", "dataFreshness": "fresh", "symbolsScanned": len(signals)}
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(dash, indent=2), encoding="utf-8")
    print("dashboard snapshot written", OUT)


if __name__ == "__main__":
    main()
