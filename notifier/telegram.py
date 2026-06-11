"""
notifier/telegram.py — Telegram signal delivery.

Uses python-telegram-bot v20+ async API.
Handles message chunking (Telegram limit: 4096 chars).
Retries on rate limit (429 errors).
"""
import asyncio
import datetime
from loguru import logger
from telegram import Bot
from telegram.error import TelegramError, RetryAfter

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from notifier.formatters import (
    format_signal, format_no_trade, format_black_swan,
    format_pre_event_warning, format_cme_gap_alert,
    format_altseason_alert,
)

MAX_MESSAGE_LENGTH = 4000  # Telegram limit is 4096; leave buffer
_bot: Bot | None = None


def get_bot() -> Bot:
    global _bot
    if _bot is None:
        _bot = Bot(token=TELEGRAM_BOT_TOKEN)
    return _bot


async def send_message(text: str, parse_mode: str = "Markdown") -> bool:
    """
    Send a message to the configured chat.
    Handles chunking and retry-after.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured — message not sent")
        return False

    bot = get_bot()
    chunks = _chunk_message(text)

    for i, chunk in enumerate(chunks):
        for attempt in range(3):
            try:
                await bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=chunk,
                    parse_mode=parse_mode,
                    disable_web_page_preview=True,
                )
                if len(chunks) > 1 and i < len(chunks) - 1:
                    await asyncio.sleep(0.5)  # Brief pause between chunks
                break
            except RetryAfter as e:
                wait = e.retry_after + 1
                logger.warning(f"Telegram rate limit — waiting {wait}s")
                await asyncio.sleep(wait)
            except TelegramError as e:
                logger.error(f"Telegram error (attempt {attempt+1}): {e}")
                if attempt == 2:
                    return False
                await asyncio.sleep(2)

    return True


def _chunk_message(text: str) -> list[str]:
    """Split message into chunks ≤ MAX_MESSAGE_LENGTH."""
    if len(text) <= MAX_MESSAGE_LENGTH:
        return [text]

    chunks = []
    lines = text.split("\n")
    current = []
    current_len = 0

    for line in lines:
        line_len = len(line) + 1  # +1 for newline
        if current_len + line_len > MAX_MESSAGE_LENGTH and current:
            chunks.append("\n".join(current))
            current = [line]
            current_len = line_len
        else:
            current.append(line)
            current_len += line_len

    if current:
        chunks.append("\n".join(current))

    return chunks


async def send_signal(result: dict) -> bool:
    """Send a full signal message."""
    try:
        if result.get("suspended"):
            msg = result.get("message", "🚨 ALL SIGNALS SUSPENDED — Black swan detected")
            return await send_message(msg)

        if not result.get("fires"):
            # Optionally send NO_TRADE (comment out if too noisy)
            # msg = format_no_trade(...)
            # await send_message(msg)
            return True

        msg = format_signal(result)
        success = await send_message(msg)
        if success:
            logger.info(
                f"✅ Signal sent: {result['symbol']} {result['direction']} "
                f"score={result['master_score']:+.1f}"
            )
        return success

    except Exception as e:
        logger.error(f"Signal send error: {e}")
        return False


async def send_emergency_alert(message: str) -> bool:
    """Send an emergency alert (override, black swan, etc.)."""
    return await send_message(f"🚨 *EMERGENCY ALERT*\n\n{message}")


async def send_startup_message() -> bool:
    """Send startup notification."""
    msg = (
        "🤖 *CRYPTO HYPER BOT STARTED*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n"
        "📊 5 Pipelines active:\n"
        "  1. Technical Analysis (every 15m)\n"
        "  2. BTC/DOM/USD Correlation (every 15m)\n"
        "  3. Fundamentals (every 4h)\n"
        "  4. News + Social (every 30m)\n"
        "  5. Events + Macro (every 1h)\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ _FOR EDUCATIONAL PURPOSES ONLY_"
    )
    return await send_message(msg)


async def send_health_report(watchlist: list, last_scan: str, signals_24h: int) -> bool:
    """Periodic health check message."""
    coins = ", ".join(watchlist)
    msg = (
        f"💊 *HEALTH CHECK*\n"
        f"Status: ✅ Running\n"
        f"Watching: {coins}\n"
        f"Last scan: {last_scan}\n"
        f"Signals fired (24h): {signals_24h}\n"
    )
    return await send_message(msg)
