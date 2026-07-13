from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

OUT = Path("frontend/public/data/dashboard.json")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fallback_dashboard() -> dict:
    return {
        "generatedAt": now_iso(),
        "source": "github-actions-fallback-snapshot",
        "status": {
            "mode": "fallback",
            "message": "Workflow completed with fallback data. Live dashboard uses /api/market on Vercel.",
        },
        "marketStats": [
            {"label": "BTCUSDT", "value": "Live API", "change": "refresh", "tone": "flat"},
            {"label": "ETHUSDT", "value": "Live API", "change": "refresh", "tone": "flat"},
            {"label": "BTC.D", "value": "Proxy", "change": "live soon", "tone": "flat"},
            {"label": "Source", "value": "Fallback", "change": "GitHub Actions", "tone": "warn"},
        ],
        "signals": [],
        "watchlist": [],
        "pipelines": [],
        "chart": {"symbol": "BTCUSDT", "timeframe": "fallback", "points": [55, 60, 58, 66, 70, 64, 78, 82]},
        "riskPlan": {
            "entryZone": "Use live dashboard",
            "stopLoss": "—",
            "targets": "—",
            "rr": "—",
            "note": "Fallback snapshot only. Vercel live API calculates real prices/signals.",
        },
        "performance": {"winRate": "—", "tracked": "0", "avgMove": "—", "bestPair": "—"},
        "system": {
            "lastWorkflow": now_iso(),
            "nextUpdate": "Live API on every refresh",
            "dataFreshness": "fallback",
            "symbolsScanned": 0,
        },
    }


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    should_write = True
    if OUT.exists():
        try:
            data = json.loads(OUT.read_text(encoding="utf-8"))
            should_write = not bool(data.get("generatedAt"))
        except Exception:
            should_write = True
    if should_write:
        OUT.write_text(json.dumps(fallback_dashboard(), indent=2), encoding="utf-8")
        print("fallback dashboard snapshot written")
    else:
        print("dashboard snapshot already exists")


if __name__ == "__main__":
    main()
