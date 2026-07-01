# Crypto Hyper Bot — Minimalist TradingView-Style UI/UX Spec

## Direction

Build the frontend as a clean trading-intelligence dashboard, not a noisy crypto casino UI.

Visual inspiration:

- TradingView dark charts
- Binance/Bybit market panels
- Linear/Vercel-level spacing and typography
- Green/red accents only where direction matters

## Theme

```ts
const theme = {
  bg: "#0b0f14",
  panel: "#111820",
  panelSoft: "#151e27",
  border: "#22303d",
  text: "#dce3ea",
  muted: "#7f8b99",
  green: "#00c076",
  red: "#ff4d4f",
  yellow: "#f5c542",
  blue: "#3b82f6",
}
```

## Product UX

Every page should answer:

> Should I act, wait, or avoid?

No signal should appear without:

- Why it fired
- Risk plan
- Invalidation
- Pipeline confidence
- Educational explanation

## Pages

### Dashboard

- Market strip: BTC, ETH, TOTAL, BTC.D, Fear & Greed
- Best current signal
- Watchlist cards
- Performance stats
- Pipeline health

### Signal Detail

- TradingView chart area
- Master score
- Pipeline breakdown
- Entry / SL / TP plan
- English + Roman Urdu explanation

### Performance

- Signal history table
- 1h / 4h / 24h outcomes
- Win rate
- Best symbols
- Best pipeline combinations

### Settings

- Watchlist
- Thresholds
- Pipeline weights
- Telegram status
- Risk settings

## Components

- `SignalCard`
- `PipelineScoreBar`
- `RiskPlanPanel`
- `MarketContextStrip`
- `PerformanceStats`
- `WatchlistSidebar`
- `HealthBadge`

## UX Principle

Every screen should keep the decision simple:

- Act
- Wait
- Avoid

Never show a LONG/SHORT without showing why, invalidation, and risk.
