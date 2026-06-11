"""
config.py — Central configuration and constants.

All environment vars, thresholds, and watchlist live here.
Every module imports from this file — zero magic strings elsewhere.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ═══════════════════════════════════════════
# TELEGRAM
# ═══════════════════════════════════════════
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ═══════════════════════════════════════════
# API KEYS
# ═══════════════════════════════════════════
CRYPTOPANIC_API_KEY = os.getenv("CRYPTOPANIC_API_KEY", "")
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY", "")

# ═══════════════════════════════════════════
# WATCHLIST
# ═══════════════════════════════════════════
WATCHLIST_RAW = os.getenv("WATCHLIST", "BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,AVAXUSDT")
WATCHLIST = [s.strip().upper() for s in WATCHLIST_RAW.split(",")]

# Derive base coin symbol from pair (BTCUSDT -> BTC)
def coin_from_symbol(symbol: str) -> str:
    for quote in ["USDT", "BUSD", "BTC", "ETH", "BNB"]:
        if symbol.endswith(quote):
            return symbol[: -len(quote)]
    return symbol

# ═══════════════════════════════════════════
# SIGNAL THRESHOLDS (Hsaka: only max confluence)
# ═══════════════════════════════════════════
LONG_THRESHOLD = float(os.getenv("LONG_THRESHOLD", "5.5"))
SHORT_THRESHOLD = float(os.getenv("SHORT_THRESHOLD", "-5.5"))
MIN_PIPELINE_AGREEMENT = int(os.getenv("MIN_PIPELINE_AGREEMENT", "3"))

# Signal strength labels
SIGNAL_LABELS = {
    (5.5, 6.5): ("MODERATE", "⚡"),
    (6.5, 8.0): ("STRONG", "🔥"),
    (8.0, 10.1): ("HIGH CONVICTION", "💎"),
}

def get_signal_label(score: float) -> tuple:
    abs_score = abs(score)
    for (low, high), (label, emoji) in SIGNAL_LABELS.items():
        if low <= abs_score < high:
            return label, emoji
    return "MODERATE", "⚡"

# ═══════════════════════════════════════════
# PIPELINE WEIGHTS (must sum to 1.0)
# ═══════════════════════════════════════════
PIPELINE_WEIGHTS = {
    "ta":          0.35,   # Technical analysis — most weight
    "correlation": 0.20,   # BTC/DOM/USD macro structure
    "fundamental": 0.15,   # FA, on-chain
    "sentiment":   0.15,   # News, social
    "events":      0.15,   # Macro events, CME gaps, coin events
}

# ═══════════════════════════════════════════
# CACHE TTLs (seconds)
# ═══════════════════════════════════════════
CACHE_OHLCV     = int(os.getenv("CACHE_OHLCV", "900"))     # 15 min
CACHE_NEWS      = int(os.getenv("CACHE_NEWS", "1800"))      # 30 min
CACHE_FA        = int(os.getenv("CACHE_FA", "14400"))       # 4 hours
CACHE_FEAR_GREED = 3600                                     # 1 hour
CACHE_MEMPOOL   = 1800                                      # 30 min

# ═══════════════════════════════════════════
# TECHNICAL ANALYSIS SETTINGS
# ═══════════════════════════════════════════
EMA_FAST  = 21
EMA_MID   = 50
EMA_SLOW  = 200
RSI_PERIOD = 14
MACD_FAST  = 12
MACD_SLOW  = 26
MACD_SIGNAL = 9
ATR_PERIOD = 14
PIVOT_PERIOD = 20

# ═══════════════════════════════════════════
# DERIVATIVES THRESHOLDS
# ═══════════════════════════════════════════
FUNDING_VERY_BULLISH  = -0.05   # Shorts very over-leveraged = contrarian long
FUNDING_BULLISH       = -0.01
FUNDING_BEARISH       = 0.01
FUNDING_VERY_BEARISH  = 0.05    # Longs very over-leveraged = contrarian short

# ═══════════════════════════════════════════
# FEAR & GREED THRESHOLDS
# ═══════════════════════════════════════════
FEAR_EXTREME     = 25   # Contrarian bullish
FEAR             = 45
GREED            = 55
GREED_EXTREME    = 75   # Contrarian bearish

# ═══════════════════════════════════════════
# TIMEFRAMES
# ═══════════════════════════════════════════
TF_15M  = "15m"
TF_1H   = "1h"
TF_4H   = "4h"
TF_1D   = "1d"
TF_1W   = "1w"

# Number of candles to fetch per timeframe
CANDLES_LIMIT = 200

# ═══════════════════════════════════════════
# EXTERNAL URLS
# ═══════════════════════════════════════════
BINANCE_BASE_URL       = "https://api.binance.com"
COINGECKO_BASE_URL     = "https://api.coingecko.com/api/v3"
FEAR_GREED_URL         = "https://api.alternative.me/fng/?limit=2"
MEMPOOL_BASE_URL       = "https://mempool.space/api"
CRYPTOPANIC_BASE_URL   = "https://cryptopanic.com/api/v1"

# Nitter instances (fallback list — some may be down)
NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.42l.fr",
    "https://nitter.cz",
    "https://nitter.1d4.us",
]

# Key Twitter/X accounts to monitor via Nitter RSS
NITTER_ACCOUNTS = [
    "PlanB",       # Stock-to-flow, BTC cycles
    "APompliano",  # Macro BTC perspective
    "woonomic",    # Willy Woo — on-chain
    "RaoulGMI",    # Raoul Pal — macro liquidity
    "CryptoCobie", # Cobie — cycle + momentum
    "Pentosh1",    # Pentoshi — HTF structure
    "Ansemdotio",  # Ansem — volume + accumulation
    "WatcherGuru", # Breaking news
    "lookonchain",  # On-chain whale moves
    "rektcapital",  # Technical analysis
    "TechDev_52",   # BTC cycles
]

# Reddit subreddits to monitor
REDDIT_SUBREDDITS = [
    "cryptocurrency",
    "bitcoin",
    "ethtrader",
    "CryptoMarkets",
]

# YouTube channel IDs for RSS monitoring
YOUTUBE_CHANNELS = {
    "Benjamin Cowen":  "UCRvqjQPSeaWn-uEx-w0XOIg",
    "Coin Bureau":     "UCqK_GSMbpiV8spgD3ZGloSw",
    "InvestAnswers":   "UCFCEuCsyWP0YkP3CZ3Mr01Q",
    "Crypto Banter":   "UCN9Nj4tjXbVTLYWN0EKly_Q",
    "DataDash":        "UCCatR7nWbYrkVXdxXb4cGXtA",
    "Altcoin Daily":   "UCbLhGKVY-bJPcawebgtNfbw",
}

# ═══════════════════════════════════════════
# KEYWORDS FOR NLP OVERRIDE
# ═══════════════════════════════════════════
BEARISH_KEYWORDS = [
    "hack", "exploit", "breach", "sec", "lawsuit", "ban",
    "regulate", "crash", "ponzi", "rug", "scam", "arrested",
    "shutdown", "delist", "ofac", "sanction", "hacked", "stolen",
    "fraud", "manipulation", "flash crash", "exit scam"
]

BULLISH_KEYWORDS = [
    "etf", "approved", "partnership", "launch", "adoption",
    "listing", "binance listing", "integration", "acquisition",
    "upgrade", "mainnet", "halving", "institutional", "etf approved",
    "blackrock", "spot etf", "rate cut", "fed pause", "inflation cooling"
]

# ═══════════════════════════════════════════
# MACRO EVENT IMPACT
# ═══════════════════════════════════════════
# CPI: actual vs expected
CPI_BULL_THRESHOLD  = -0.1   # Actual 0.1% below expected = bullish
CPI_BEAR_THRESHOLD  = 0.1    # Actual 0.1% above expected = bearish

# DXY levels
DXY_VERY_BEARISH = 105       # DXY above this = strong bearish crypto
DXY_VERY_BULLISH = 100       # DXY below this = strong bullish crypto

# ═══════════════════════════════════════════
# CME GAP SETTINGS
# ═══════════════════════════════════════════
CME_GAP_ALERT_PERCENT  = 0.01  # Alert when price within 1% of gap
CME_OPEN_HOUR_CST = 9
CME_CLOSE_HOUR_CST = 16

# ═══════════════════════════════════════════
# HALVING DATES (Unix timestamps)
# ═══════════════════════════════════════════
import datetime
LAST_HALVING_DATE = datetime.datetime(2024, 4, 20, tzinfo=datetime.timezone.utc)

# ═══════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE  = "logs/crypto_bot.log"
LOG_ROTATION = "50 MB"
LOG_RETENTION = "10 days"

# ═══════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════
DB_PATH = "data/signals.db"

# ═══════════════════════════════════════════
# SIGNAL DEDUP WINDOW
# ═══════════════════════════════════════════
# Don't re-fire same directional signal for same coin within this window
SIGNAL_DEDUP_HOURS = 4

# ═══════════════════════════════════════════
# TIMEZONE
# ═══════════════════════════════════════════
TIMEZONE = os.getenv("TIMEZONE", "UTC")

# ═══════════════════════════════════════════
# VALIDATION
# ═══════════════════════════════════════════
def validate_config():
    errors = []
    if not TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN not set")
    if not TELEGRAM_CHAT_ID:
        errors.append("TELEGRAM_CHAT_ID not set")
    if not WATCHLIST:
        errors.append("WATCHLIST is empty")
    return errors
