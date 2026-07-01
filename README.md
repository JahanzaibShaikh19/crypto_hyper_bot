# 🤖 Crypto Hyper Bot

A modular Python crypto market-intelligence bot with five analysis pipelines, free public data sources, SQLite storage, and Telegram delivery.

> Educational/research tool only. It does not place trades or manage funds.

## Architecture

```txt
Market Data + News + Events
        ↓
5 Parallel Pipelines
        ↓
Master Scoring Engine
        ↓
Telegram Signal / Health Report
```

### Pipelines

| Pipeline | Purpose |
|---|---|
| Technical Analysis | Trend, momentum, volume, derivatives, structure |
| Correlation | BTC, dominance, USD/DXY proxy, cycle environment |
| Fundamentals / On-chain | CoinGecko, market data, mempool health |
| News + Social | RSS news, Binance announcements, Reddit, Nitter, YouTube |
| Events + Macro | Macro calendar, CME gaps, coin events, liquidity/session filters |

## Backend Intelligence Upgrade

The backend now includes the first production-hardening layer before frontend work:

- Binance USD-M futures endpoint routing for funding, open interest, and liquidations.
- Liquidation feed wiring into the Binance symbol payload.
- Dedicated ATR-based risk planner module in `engine/risk_engine.py`.
- Signal outcome tracker module in `storage/performance_tracker.py`.
- SQLite helpers for 1h / 4h / 24h signal outcome tracking.
- Minimalist TradingView-style frontend spec in `docs/frontend_tradingview_ui_spec.md`.

## Free Data Sources

| Source | Data |
|---|---|
| Binance Spot Public | OHLCV, ticker stats |
| Binance USD-M Futures Public | Funding, open interest, liquidation feed |
| CoinGecko Free | Global market, coin fundamentals, trending |
| Alternative.me | Fear & Greed Index |
| Free RSS News | CoinDesk, CoinTelegraph, Decrypt, The Block, Bitcoin Magazine |
| Binance RSS | Announcements, listings, maintenance |
| Reddit JSON | Public crypto community posts |
| Nitter RSS | Public X/Twitter-style feeds where available |
| YouTube RSS | Public video title sentiment |
| Mempool.space | BTC on-chain / fee environment |

## Quick Start

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python main.py
```

Required `.env` values:

```env
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
WATCHLIST=BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,AVAXUSDT
```

No paid news API key is required.

## File Structure

```txt
crypto_hyper_bot/
├── main.py
├── config.py
├── requirements.txt
├── data/
│   ├── binance_fetcher.py
│   ├── coingecko_fetcher.py
│   ├── fear_greed_fetcher.py
│   ├── news_fetcher.py
│   ├── social_fetcher.py
│   ├── mempool_fetcher.py
│   ├── macro_calendar.py
│   └── events_fetcher.py
├── engine/
│   ├── master_engine.py
│   ├── risk_engine.py
│   ├── ta_scorer.py
│   ├── correlation_scorer.py
│   ├── fa_scorer.py
│   ├── sentiment_scorer.py
│   ├── events_scorer.py
│   └── override_rules.py
├── notifier/
├── pipelines/
├── storage/
│   ├── signal_db.py
│   ├── signal_logger.py
│   └── performance_tracker.py
└── docs/
    └── frontend_tradingview_ui_spec.md
```

## Next Frontend Direction

Build the frontend as a clean TradingView-style dashboard:

- Dark charcoal background.
- Green/red accents only for direction and risk.
- Watchlist sidebar.
- Signal cards with score, confidence, invalidation, and risk plan.
- Pipeline score breakdown.
- Performance dashboard for tracked outcomes.
- English + Roman Urdu explanation mode.

## Safety

Crypto markets are volatile. This project is for research, education, and analytics. It should not be treated as financial advice, an execution bot, or a guarantee of future performance.
