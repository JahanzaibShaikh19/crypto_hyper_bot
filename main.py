"""
main.py — Crypto Hyper Bot Orchestrator.

Schedules all 5 pipelines, manages the full scan cycle,
handles graceful degradation when sources fail.

Schedule:
  Every 15 min:  TA + Correlation + Master Engine (full signal scan)
  Every 30 min:  News + Social refreshed
  Every 1 hour:  Events + CME gap check
  Every 4 hours: Fundamental analysis refresh
  Every 24 hours: Economic calendar + halving update
  On startup:    Full scan immediately

Architecture:
  - asyncio.gather for parallel pipeline execution
  - APScheduler for multi-interval scheduling
  - Graceful degradation: 1-2 source failures = bot continues
  - Smart caching prevents API hammering
"""
import asyncio
import datetime
import sys
from pathlib import Path

from loguru import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import WATCHLIST, validate_config, LOG_LEVEL, LOG_FILE, LOG_ROTATION, LOG_RETENTION
from storage.signal_db import init_db, get_recent_signals
from data.binance_fetcher import fetch_all_for_symbol, fetch_ticker_24h
from data.coingecko_fetcher import fetch_global_market
from engine.master_engine import run_master_engine
from notifier.telegram import send_signal, send_startup_message, send_health_report
from notifier.alert_types import check_and_send_special_alerts


# ═══════════════════════════════════════════
# LOGGING SETUP
# ═══════════════════════════════════════════
def setup_logging():
    logger.remove()  # Remove default handler
    logger.add(
        sys.stdout,
        level=LOG_LEVEL,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> | {message}",
        colorize=True,
    )
    Path("logs").mkdir(exist_ok=True)
    logger.add(
        LOG_FILE,
        level="DEBUG",
        rotation=LOG_ROTATION,
        retention=LOG_RETENTION,
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name} | {message}",
    )


# ═══════════════════════════════════════════
# GLOBAL STATE
# ═══════════════════════════════════════════
_last_scan_time: str = "Never"
_scan_count: int = 0
_btc_data_cache: dict = {}
_global_market_cache: dict = {}


# ═══════════════════════════════════════════
# CORE SCAN FUNCTION
# ═══════════════════════════════════════════
async def run_full_scan():
    """
    Run a full signal scan for all coins in the watchlist.
    This is the main function called every 15 minutes.
    """
    global _last_scan_time, _scan_count, _btc_data_cache, _global_market_cache

    start = datetime.datetime.utcnow()
    _scan_count += 1
    logger.info(f"═══ SCAN #{_scan_count} STARTING ({start.strftime('%H:%M UTC')}) ═══")

    # ─── Fetch BTC data (needed for cross-market reference) ───────
    try:
        btc_data = await fetch_all_for_symbol("BTCUSDT")
        _btc_data_cache = btc_data
    except Exception as e:
        logger.warning(f"BTC data fetch failed: {e} — using cached")
        btc_data = _btc_data_cache

    # ─── Fetch global market data once ───────────────────────────
    try:
        global_data = await fetch_global_market()
        if global_data:
            _global_market_cache = global_data
    except Exception as e:
        logger.warning(f"Global market data failed: {e} — using cached")
        global_data = _global_market_cache

    # ─── Scan each symbol ─────────────────────────────────────────
    results = []
    for symbol in WATCHLIST:
        try:
            result = await scan_symbol(symbol, btc_data, global_data)
            if result:
                results.append(result)
        except Exception as e:
            logger.error(f"Error scanning {symbol}: {e}")
            continue

    # ─── Check special alerts ────────────────────────────────────
    if results:
        best_result = max(results, key=lambda r: abs(r.get("master_score", 0)))
        events_result = best_result.get("events", {})
        try:
            await check_and_send_special_alerts(best_result, events_result, global_data or {})
        except Exception as e:
            logger.debug(f"Special alerts error: {e}")

    elapsed = (datetime.datetime.utcnow() - start).total_seconds()
    _last_scan_time = start.strftime("%Y-%m-%d %H:%M UTC")

    fired = sum(1 for r in results if r.get("fires", False))
    logger.info(
        f"═══ SCAN #{_scan_count} COMPLETE [{elapsed:.1f}s] | "
        f"Symbols: {len(results)} | Signals fired: {fired} ═══"
    )


async def scan_symbol(symbol: str, btc_data: dict, global_data: dict) -> dict | None:
    """
    Full scan for a single symbol.
    Returns result dict (even if NO_TRADE).
    """
    logger.debug(f"Scanning {symbol}...")

    # Fetch this symbol's data
    try:
        binance_data = await fetch_all_for_symbol(symbol)
    except Exception as e:
        logger.warning(f"Binance data fetch failed for {symbol}: {e}")
        return None

    if not binance_data.get("ohlcv_4h") is not None:
        logger.debug(f"Insufficient data for {symbol}, skipping")
        return None

    # Run master engine
    result = await run_master_engine(
        symbol=symbol,
        binance_data=binance_data,
        btc_data=btc_data if symbol != "BTCUSDT" else None,
        global_market_data=global_data,
    )

    # Handle suspended state (black swan)
    if result.get("suspended"):
        logger.critical(f"BLACK SWAN detected — sending emergency alert")
        await send_signal(result)
        return result

    # Send signal if it fires
    if result.get("fires"):
        await send_signal(result)
    else:
        direction = result.get("direction", "NO_TRADE")
        score = result.get("master_score", 0)
        pipelines = result.get("pipelines_agreeing", 0)
        logger.debug(
            f"  {symbol}: {direction} | score={score:+.1f} | pipelines={pipelines}/5"
        )

    return result


# ═══════════════════════════════════════════
# SCHEDULED JOBS
# ═══════════════════════════════════════════

async def refresh_news_social():
    """
    Refresh news and social data every 30 minutes.
    The cache handles dedup — this just warms the cache.
    """
    logger.debug("Refreshing news/social cache...")
    from data.news_fetcher  import fetch_cryptopanic, fetch_binance_announcements
    from data.social_fetcher import fetch_all_nitter, fetch_all_reddit

    try:
        await asyncio.gather(
            fetch_cryptopanic(),
            fetch_binance_announcements(),
            fetch_all_nitter(),
            fetch_all_reddit(),
            return_exceptions=True,
        )
        logger.debug("News/social cache refreshed")
    except Exception as e:
        logger.debug(f"News/social refresh error: {e}")


async def refresh_fundamentals():
    """Refresh FA data every 4 hours."""
    logger.debug("Refreshing fundamentals cache...")
    from data.coingecko_fetcher import fetch_coin_data, fetch_trending, fetch_global_market
    from data.mempool_fetcher import fetch_all_mempool

    tasks = [fetch_global_market(), fetch_all_mempool(), fetch_trending()]
    tasks += [fetch_coin_data(sym) for sym in WATCHLIST]

    try:
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.debug("Fundamentals cache refreshed")
    except Exception as e:
        logger.debug(f"FA refresh error: {e}")


async def refresh_events_calendar():
    """Refresh events and macro calendar every hour."""
    logger.debug("Refreshing events calendar...")
    from data.macro_calendar import parse_recent_macro_events
    from data.events_fetcher import fetch_coinmarketcal_rss

    try:
        await asyncio.gather(
            parse_recent_macro_events(),
            fetch_coinmarketcal_rss(),
            return_exceptions=True,
        )
        logger.debug("Events calendar refreshed")
    except Exception as e:
        logger.debug(f"Events refresh error: {e}")


async def send_daily_health_report():
    """Send daily health check to Telegram."""
    recent_signals = get_recent_signals(hours=24)
    await send_health_report(
        watchlist=WATCHLIST,
        last_scan=_last_scan_time,
        signals_24h=len(recent_signals),
    )


# ═══════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════
async def startup_health_check() -> bool:
    """
    Verify all critical APIs are responding before starting.
    Graceful degradation: warns but doesn't block startup.
    """
    logger.info("Running startup health check...")
    checks = {
        "Binance API": False,
        "CoinGecko API": False,
        "Fear & Greed": False,
        "Telegram Bot": False,
    }

    # Binance
    try:
        from data.binance_fetcher import fetch_ticker_24h
        r = await fetch_ticker_24h("BTCUSDT")
        checks["Binance API"] = r is not None and r.get("price", 0) > 0
    except Exception as e:
        logger.warning(f"Binance health check: {e}")

    # CoinGecko
    try:
        g = await fetch_global_market()
        checks["CoinGecko API"] = g is not None
    except Exception as e:
        logger.warning(f"CoinGecko health check: {e}")

    # Fear & Greed
    try:
        from data.fear_greed_fetcher import fetch_fear_greed
        fg = await fetch_fear_greed()
        checks["Fear & Greed"] = fg.get("value", 0) > 0
    except Exception as e:
        logger.warning(f"Fear & Greed health check: {e}")

    # Telegram
    try:
        from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
        checks["Telegram Bot"] = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)
    except Exception:
        pass

    for name, status in checks.items():
        status_str = "✅" if status else "⚠️"
        logger.info(f"  {status_str} {name}")

    all_ok = all(checks.values())
    if not all_ok:
        logger.warning(
            "Some APIs unavailable — bot will run with degraded data. "
            "Signals may be less accurate."
        )

    return True  # Always start — graceful degradation


# ═══════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════
async def main():
    setup_logging()
    logger.info("═══ CRYPTO HYPER BOT STARTING ═══")

    # Validate config
    errors = validate_config()
    if errors:
        for err in errors:
            logger.error(f"Config error: {err}")
        logger.error("Fix .env config and restart. Exiting.")
        sys.exit(1)

    # Initialize database
    init_db()
    logger.info("Database initialized")

    # Health check
    await startup_health_check()

    # Send startup message to Telegram
    await send_startup_message()

    # Run immediate full scan on startup
    logger.info("Running initial full scan...")
    await run_full_scan()

    # ─── SETUP SCHEDULER ─────────────────────────────────────────
    scheduler = AsyncIOScheduler(timezone="UTC")

    # Full signal scan every 15 minutes
    scheduler.add_job(
        run_full_scan,
        trigger=IntervalTrigger(minutes=15),
        id="full_scan",
        name="Full Signal Scan",
        max_instances=1,
        misfire_grace_time=60,
        coalesce=True,
    )

    # News/social refresh every 30 minutes
    scheduler.add_job(
        refresh_news_social,
        trigger=IntervalTrigger(minutes=30),
        id="news_refresh",
        name="News & Social Refresh",
        max_instances=1,
    )

    # Events calendar every hour
    scheduler.add_job(
        refresh_events_calendar,
        trigger=IntervalTrigger(hours=1),
        id="events_refresh",
        name="Events Calendar Refresh",
        max_instances=1,
    )

    # Fundamentals every 4 hours
    scheduler.add_job(
        refresh_fundamentals,
        trigger=IntervalTrigger(hours=4),
        id="fa_refresh",
        name="Fundamentals Refresh",
        max_instances=1,
    )

    # Daily health report
    scheduler.add_job(
        send_daily_health_report,
        trigger=IntervalTrigger(hours=24),
        id="health_report",
        name="Daily Health Report",
        max_instances=1,
    )

    scheduler.start()
    logger.info("Scheduler started — all jobs active")
    logger.info(
        f"Watching: {', '.join(WATCHLIST)}\n"
        f"Next full scan in ~15 minutes"
    )

    # Keep alive
    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown requested")
        scheduler.shutdown(wait=False)
        logger.info("Bot stopped cleanly")


if __name__ == "__main__":
    asyncio.run(main())
