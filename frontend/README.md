# Crypto Hyper Bot Frontend

Minimal TradingView-style dashboard for the Python backend.

## Run locally

```bash
cd frontend
npm install
npm run dev
```

Open the local Vite URL in your browser.

## Current status

This is the first UI/UX layer with static research data so the product direction is visible before backend API wiring.

Shown sections:

- Market overview strip
- TradingView-style chart panel
- Signal cards
- Watchlist sidebar
- Risk plan panel
- Pipeline confluence bars
- Performance stats

## Next wiring phase

Connect these UI sections to backend endpoints:

- `/api/market` → market strip
- `/api/signals/latest` → current signal cards
- `/api/signals/:symbol` → signal detail page
- `/api/performance` → win rate and outcome metrics
- `/api/pipelines/health` → pipeline health status

## Design direction

- Dark charcoal base
- Soft glass panels
- Green/red direction accents
- Minimal noise
- Every screen answers: act, wait, or avoid
