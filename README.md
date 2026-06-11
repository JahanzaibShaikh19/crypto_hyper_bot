# 🤖 Crypto Hyper Bot

The most advanced free Python crypto signal bot — 5 parallel pipelines,
zero cost APIs, Telegram delivery. Built on the principles of the best
traders in crypto.

## Trader Principles Embedded

| Pipeline | Trader | Principle |
|---|---|---|
| Technical (L1) | **Pentoshi** | HTF structure is king |
| Technical (L2) | **Cobie** | Cycle position + momentum |
| Technical (L3) | **Ansem** | Volume precedes every move |
| Technical (L4) | **Arthur Hayes** | Derivatives never lie |
| Technical (L5) | **Hsaka** | Max confluence = alpha |
| Correlation | **Raoul Pal** | Macro liquidity drives everything |
| On-Chain | **Willy Woo** | On-chain reveals what price hides |
| Cycle | **Plan B** | Bitcoin cycles are predictable |

---

## Architecture

```
5 Parallel Pipelines → Master Scoring Engine → Telegram Signal

Pipeline 1: Technical Analysis         (every 15 min)
Pipeline 2: BTC/DOM/USD Correlation    (every 15 min)
Pipeline 3: Fundamental Analysis       (every 4 hours)
Pipeline 4: News + Social Sentiment    (every 30 min)
Pipeline 5: Events + Macro Calendar    (every 1 hour)

Signal fires ONLY when ≥3/5 pipelines agree (Hsaka rule)
Master score ≥+5.5 = LONG | ≤-5.5 = SHORT | else NO TRADE
```

---

## Quick Start (< 10 minutes)

### 1. Get a VPS
Any $5/month Ubuntu 22.04 VPS works (DigitalOcean, Hetzner, Vultr).
Minimum: 1 vCPU, 1GB RAM, 10GB disk.

### 2. Install Python 3.11+
```bash
sudo apt update && sudo apt install -y python3.11 python3.11-venv python3-pip
```

### 3. Clone / Upload the Bot
```bash
mkdir ~/crypto_hyper_bot && cd ~/crypto_hyper_bot
# Upload all files here
```

### 4. Create Virtual Environment
```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m textblob.download_corpora  # Download NLP data
```

### 5. Create Telegram Bot
1. Open Telegram, search for `@BotFather`
2. Send `/newbot` → give it a name
3. Copy the **API token**
4. Start a chat with your new bot
5. Go to `https://api.telegram.org/bot<TOKEN>/getUpdates`
6. Send any message to your bot
7. Copy the `chat_id` from the response

### 6. Configure Environment
```bash
cp .env.example .env
nano .env
```

Fill in:
```
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
WATCHLIST=BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT
```

Optional (for better news coverage):
```
CRYPTOPANIC_API_KEY=your_free_key_from_cryptopanic.com
```

### 7. Test Run
```bash
python main.py
```

You should see startup logs and receive a Telegram message.

### 8. Run 24/7 with systemd
```bash
sudo nano /etc/systemd/system/cryptobot.service
```

```ini
[Unit]
Description=Crypto Hyper Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/crypto_hyper_bot
Environment=PATH=/home/ubuntu/crypto_hyper_bot/venv/bin
ExecStart=/home/ubuntu/crypto_hyper_bot/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=append:/home/ubuntu/crypto_hyper_bot/logs/systemd.log
StandardError=append:/home/ubuntu/crypto_hyper_bot/logs/systemd_error.log

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable cryptobot
sudo systemctl start cryptobot
sudo systemctl status cryptobot

# Watch live logs
journalctl -u cryptobot -f
```

---

## Free APIs Used (Zero Cost)

| Source | Data | Rate Limit |
|---|---|---|
| Binance Public | OHLCV, Funding, OI | 1200 req/min |
| CoinGecko Free | Market cap, FA | 30 req/min |
| Alternative.me | Fear & Greed Index | No limit |
| CryptoPanic Free | News + votes | 5 req/min |
| Nitter RSS | X/Twitter posts | No auth |
| Reddit JSON | Hot posts | No auth |
| YouTube RSS | Video titles | No auth |
| Mempool.space | BTC on-chain | No limit |
| TradingEconomics RSS | DXY, macro | No auth |
| CoinMarketCal RSS | Coin events | No auth |
| Binance RSS | Announcements | No auth |

---

## Signal Format

```
🟢 LONG SIGNAL — BTCUSDT
💎 HIGH CONVICTION
━━━━━━━━━━━━━━━━━━━━
📊 Master Score: +8.1/10
🎯 Confidence: 81% | Pipelines: 5/5 ✅

📈 TECHNICAL [+8.5/10]
✅ EMA: 21>50>200 aligned
✅ RSI: 58↑ (healthy momentum)
⚡ RSI Bullish Divergence detected
✅ Volume: 2.8x average spike
✅ MACD: histogram turning positive
...
```

---

## File Structure

```
crypto_hyper_bot/
├── main.py                    # Orchestrator + scheduler
├── config.py                  # All settings
├── .env                       # Secrets (git-ignored)
├── requirements.txt
│
├── data/                      # API fetchers
│   ├── binance_fetcher.py     # OHLCV, funding, OI, liq
│   ├── coingecko_fetcher.py   # Market cap, FA, trending
│   ├── fear_greed_fetcher.py  # Alternative.me
│   ├── news_fetcher.py        # CryptoPanic + Binance RSS
│   ├── social_fetcher.py      # Nitter + Reddit + YouTube
│   ├── mempool_fetcher.py     # Bitcoin on-chain
│   ├── macro_calendar.py      # Economic calendar
│   └── events_fetcher.py      # Coin events
│
├── pipelines/                 # Analysis modules
│   ├── technical/             # 5-layer TA
│   ├── correlation/           # BTC/DOM/USD/Alts
│   ├── events/                # CME gaps, halving, macro
│   └── sentiment/             # Context builder
│
├── engine/                    # Scoring engines
│   ├── ta_scorer.py           # TA pipeline → score
│   ├── correlation_scorer.py  # Correlation → score
│   ├── fa_scorer.py           # FA → score
│   ├── sentiment_scorer.py    # Sentiment → score
│   ├── events_scorer.py       # Events → score
│   ├── master_engine.py       # Final weighted master
│   └── override_rules.py      # Emergency overrides
│
├── notifier/                  # Telegram delivery
│   ├── telegram.py            # Bot sender
│   ├── formatters.py          # Message formatting
│   └── alert_types.py         # Special alerts
│
├── storage/
│   ├── signal_db.py           # SQLite: signals, CME gaps
│   └── signal_logger.py       # CSV for backtesting
│
├── utils/
│   ├── cache.py               # TTL in-memory cache
│   ├── rate_limiter.py        # API rate limiting
│   ├── nlp_helper.py          # TextBlob NLP
│   └── timezone_handler.py    # Session/liquidity
│
└── logs/
    ├── crypto_bot.log         # Rotating logs
    └── signal_history.csv     # Backtesting data
```

---

## Tuning the Bot

### Adjust Signal Sensitivity
In `.env`:
```
LONG_THRESHOLD=5.5    # Lower = more signals (noisier)
SHORT_THRESHOLD=-5.5  # Higher = fewer signals (stricter)
MIN_PIPELINE_AGREEMENT=3  # Lower = fire with less consensus
```

### Change Watchlist
```
WATCHLIST=BTCUSDT,ETHUSDT,SOLUSDT
```

### Adjust Pipeline Weights
In `config.py`, change `PIPELINE_WEIGHTS`:
```python
PIPELINE_WEIGHTS = {
    "ta":          0.40,  # Increase TA weight
    "correlation": 0.20,
    "fundamental": 0.15,
    "sentiment":   0.10,  # Decrease social weight
    "events":      0.15,
}
```

---

## Backtesting

Every fired signal is logged to `logs/signal_history.csv`.
Load it in pandas:

```python
import pandas as pd
df = pd.read_csv("logs/signal_history.csv")
df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"])
print(df.groupby("direction")["master_score"].describe())
```

---

## Troubleshooting

**Bot not sending Telegram messages:**
- Check `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env`
- Make sure you've started a chat with your bot
- Run `python -c "from notifier.telegram import *; import asyncio; asyncio.run(send_message('test'))"` 

**No signals firing:**
- Lower `LONG_THRESHOLD` to `4.5` temporarily
- Lower `MIN_PIPELINE_AGREEMENT` to `2`
- Check logs: `tail -f logs/crypto_bot.log`

**CoinGecko rate limit errors:**
- The free tier is 30 req/min — the bot respects this
- If you're seeing 429s, increase `CACHE_FA` in `.env`

**Nitter RSS not working:**
- Nitter instances go down often — the bot tries multiple
- If all fail, Twitter data is skipped (graceful degradation)

---

## ⚠️ Disclaimer

This bot is for **educational purposes only**.
Crypto trading involves significant financial risk.
Never trade more than you can afford to lose.
Past signal performance does not guarantee future results.
DYOR — Do Your Own Research.
