from __future__ import annotations

import asyncio
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loguru import logger

from config import WATCHLIST
from data.binance_fetcher import fetch_all_for_symbol
from data.coingecko_fetcher import fetch_global_market
from main import scan_symbol, setup_logging
from storage.signal_db import init_db

OUT = ROOT / "frontend/public/data/original-bot-scan.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def direction_tone(direction: str) -> str:
    if direction == "LONG":
        return "up"
    if direction == "SHORT":
        return "down"
    if direction == "SUSPENDED":
        return "down"
    return "flat"


def money(value: Any) -> str:
    price = as_number(value)
    if price >= 1000:
        return f"${price:,.2f}"
    if price >= 1:
        return f"${price:,.4f}"
    return f"${price:,.6f}"


def compact_signal(result: dict[str, Any]) -> dict[str, Any]:
    context = result.get("context") or {}
    pipeline_scores = result.get("pipeline_scores") or {}
    direction = result.get("direction", "NO_TRADE")
    score = as_number(result.get("master_score"))
    price = result.get("price") or context.get("price") or 0
    warnings = context.get("all_warnings") or []
    reason_bits = [
        "Original master engine output",
        f"{result.get('pipelines_agreeing', 0)}/5 pipelines aligned",
        f"BTC scenario: {context.get('btc_scenario', 'Unknown')}",
    ]
    if warnings:
        reason_bits.append(f"Warnings: {', '.join(map(str, warnings[:2]))}")
    return {
        "symbol": result.get("symbol", "UNKNOWN"),
        "direction": direction,
        "fires": bool(result.get("fires", False)),
        "score": f"{score:+.1f}",
        "scoreRaw": round(score, 3),
        "confidence": f"{as_number(result.get('confidence')):.0f}%",
        "strength": result.get("strength", "—"),
        "price": money(price),
        "priceRaw": as_number(price),
        "tone": direction_tone(direction),
        "reason": " • ".join(reason_bits),
        "pipelinesAgreeing": result.get("pipelines_agreeing", 0),
        "bullishPipelines": result.get("bullish_pipelines", 0),
        "bearishPipelines": result.get("bearish_pipelines", 0),
        "pipelineScores": pipeline_scores,
        "invalidations": result.get("invalidations", {}),
        "timestampUtc": result.get("timestamp_utc") or now_iso(),
    }


def pipeline_rows(best: dict[str, Any] | None) -> list[dict[str, Any]]:
    scores = (best or {}).get("pipelineScores") or {}
    labels = {
        "ta": "Technical",
        "correlation": "Correlation",
        "fundamental": "Fundamental",
        "sentiment": "Sentiment",
        "events": "Events",
    }
    rows = []
    for key, label in labels.items():
        score = as_number(scores.get(key))
        rows.append({"name": label, "score": round(abs(score), 1), "rawScore": round(score, 3), "tone": direction_tone("LONG" if score > 0 else "SHORT" if score < 0 else "NO_TRADE")})
    return rows


def write_payload(payload: dict[str, Any]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info(f"Original bot scan JSON written: {OUT}")


def failure_payload(message: str) -> dict[str, Any]:
    return {
        "generatedAt": now_iso(),
        "source": "original-python-master-engine",
        "status": {"mode": "failed", "message": f"Original bot scan failed: {message}"},
        "summary": {"watchlist": WATCHLIST, "symbolsScanned": 0, "signalsFired": 0, "bestSymbol": "—", "bestDirection": "NO_TRADE", "bestScore": "+0.0", "errors": [{"error": message}]},
        "latestSignal": None,
        "signals": [],
        "pipelines": pipeline_rows(None),
        "system": {"runner": "github-actions-one-shot", "nextStep": "Check workflow logs."},
    }


async def run_once() -> dict[str, Any]:
    setup_logging()
    init_db()
    started = now_iso()
    logger.info("Starting one-shot original bot scan")

    try:
        btc_data = await fetch_all_for_symbol("BTCUSDT")
    except Exception as exc:
        logger.warning(f"BTC data unavailable: {exc}")
        btc_data = {}

    try:
        global_data = await fetch_global_market()
    except Exception as exc:
        logger.warning(f"Global market unavailable: {exc}")
        global_data = {}

    results = []
    errors = []
    for symbol in WATCHLIST:
        try:
            result = await scan_symbol(symbol, btc_data, global_data or {})
            if result:
                results.append(result)
        except Exception as exc:
            logger.exception(f"Original scan failed for {symbol}: {exc}")
            errors.append({"symbol": symbol, "error": str(exc)})

    compact = [compact_signal(r) for r in results]
    compact.sort(key=lambda item: abs(item.get("scoreRaw", 0)), reverse=True)
    latest = compact[0] if compact else None
    fired = [item for item in compact if item.get("fires")]

    payload = {
        "generatedAt": now_iso(),
        "startedAt": started,
        "source": "original-python-master-engine",
        "status": {
            "mode": "complete" if compact else "degraded",
            "message": "Original Python bot scan completed." if compact else "Original bot scan completed but produced no symbol results.",
        },
        "summary": {
            "watchlist": WATCHLIST,
            "symbolsScanned": len(compact),
            "signalsFired": len(fired),
            "bestSymbol": latest.get("symbol") if latest else "—",
            "bestDirection": latest.get("direction") if latest else "NO_TRADE",
            "bestScore": latest.get("score") if latest else "+0.0",
            "errors": errors,
        },
        "latestSignal": latest,
        "signals": compact,
        "pipelines": pipeline_rows(latest),
        "system": {
            "runner": "github-actions-one-shot",
            "nextStep": "Review latest signal and risk/invalidation context.",
        },
    }
    write_payload(payload)
    return payload


async def main() -> None:
    try:
        await run_once()
    except Exception as exc:
        traceback.print_exc()
        write_payload(failure_payload(str(exc)))
        raise


if __name__ == "__main__":
    asyncio.run(main())
