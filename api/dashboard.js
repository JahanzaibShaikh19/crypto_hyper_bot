const SPOT = 'https://api.binance.com'
const FNG = 'https://api.alternative.me/fng/'

const symbols = (process.env.WATCHLIST || 'BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,AVAXUSDT')
  .split(',')
  .map((s) => s.trim().toUpperCase())
  .filter(Boolean)

function n(v, d = 0) {
  const x = Number(v)
  return Number.isFinite(x) ? x : d
}

function money(v) {
  const x = n(v)
  if (x >= 1000) return `$${x.toLocaleString(undefined, { maximumFractionDigits: 2 })}`
  if (x >= 1) return `$${x.toLocaleString(undefined, { maximumFractionDigits: 4 })}`
  return `$${x.toFixed(6)}`
}

function pct(v) {
  return `${n(v).toFixed(2)}%`.replace(/^([^\-])/, '+$1')
}

function tone(v) {
  const x = n(v)
  if (x > 0.15) return 'up'
  if (x < -0.15) return 'down'
  return 'flat'
}

async function j(url) {
  const r = await fetch(url, { headers: { 'user-agent': 'hyperbot-dashboard' } })
  if (!r.ok) throw new Error(`${r.status} ${url}`)
  return r.json()
}

function avg(arr) {
  return arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0
}

function rsi(closes) {
  if (closes.length < 15) return 50
  const slice = closes.slice(-15)
  let gains = 0
  let losses = 0
  for (let i = 1; i < slice.length; i++) {
    const diff = slice[i] - slice[i - 1]
    if (diff >= 0) gains += diff
    else losses += Math.abs(diff)
  }
  if (!losses) return 100
  const rs = gains / losses
  return 100 - 100 / (1 + rs)
}

async function symbolData(symbol) {
  const [ticker, klines] = await Promise.all([
    j(`${SPOT}/api/v3/ticker/24hr?symbol=${symbol}`),
    j(`${SPOT}/api/v3/klines?symbol=${symbol}&interval=1h&limit=80`),
  ])
  const closes = klines.map((k) => n(k[4]))
  const highs = klines.map((k) => n(k[2]))
  const lows = klines.map((k) => n(k[3]))
  const price = n(ticker.lastPrice, closes.at(-1) || 0)
  const ranges = highs.slice(-14).map((h, i) => h - lows.slice(-14)[i])
  return {
    symbol,
    price,
    change: n(ticker.priceChangePercent),
    volume: n(ticker.quoteVolume),
    closes,
    sma20: avg(closes.slice(-20)),
    sma50: avg(closes.slice(-50)),
    rsi: rsi(closes),
    atr: avg(ranges) || price * 0.015,
  }
}

function score(d, btcChange, fearValue) {
  let technical = 0
  technical += d.price > d.sma20 ? 2.2 : -1.8
  technical += d.sma20 > d.sma50 ? 2.0 : -1.5
  technical += d.rsi >= 48 && d.rsi <= 70 ? 1.4 : -1
  technical += Math.max(-2, Math.min(2, d.change / 2.5))
  const correlation = Math.max(-8, Math.min(8, (btcChange + d.change) / 2))
  const fundamental = d.volume > 1000000000 ? 2 : d.volume > 200000000 ? 1 : -0.5
  const sentiment = (fearValue - 50) / 8
  const events = 0.5
  const master = technical * 0.4 + correlation * 0.2 + fundamental * 0.15 + sentiment * 0.1 + events * 0.15
  const vals = [technical, correlation, fundamental, sentiment, events]
  const aligned = Math.max(vals.filter((x) => x > 0).length, vals.filter((x) => x < 0).length)
  let direction = 'WAIT'
  let t = 'flat'
  if (master >= 5.5 && aligned >= 3) { direction = 'LONG'; t = 'up' }
  else if (master <= -5.5 && aligned >= 3) { direction = 'SHORT'; t = 'down' }
  else if (master >= 3.2) { direction = 'LONG WATCH'; t = 'up' }
  else if (master <= -3.2) { direction = 'SHORT WATCH'; t = 'down' }
  return {
    symbol: d.symbol,
    direction,
    score: `${master >= 0 ? '+' : ''}${master.toFixed(1)}`,
    scoreRaw: Number(master.toFixed(3)),
    confidence: `${Math.max(18, Math.min(96, Math.abs(master) / 8 * 100)).toFixed(0)}%`,
    price: money(d.price),
    priceRaw: d.price,
    change: pct(d.change),
    tone: t,
    reason: `SMA20 ${d.sma20 > d.sma50 ? 'above' : 'below'} SMA50, RSI ${d.rsi.toFixed(0)}, 24h ${pct(d.change)}`,
    pipelines: { Technical: technical, Correlation: correlation, Fundamental: fundamental, Sentiment: sentiment, Events: events },
  }
}

function chart(closes) {
  const s = closes.slice(-28)
  const lo = Math.min(...s)
  const hi = Math.max(...s)
  const span = hi - lo || 1
  return s.map((v) => Math.round(38 + ((v - lo) / span) * 92))
}

function risk(best, raw) {
  if (!raw || !raw.price) return { entryZone: '—', stopLoss: '—', targets: '—', rr: '—', note: 'No live data.' }
  const p = raw.price
  const a = raw.atr || p * 0.015
  if (best.direction.includes('LONG')) {
    return { entryZone: `${money(p - a * .25)} — ${money(p + a * .12)}`, stopLoss: money(p - a * 1.15), targets: `${money(p + a * 1.65)} / ${money(p + a * 2.65)}`, rr: '1:2.30', note: 'Educational risk plan only.' }
  }
  if (best.direction.includes('SHORT')) {
    return { entryZone: `${money(p - a * .12)} — ${money(p + a * .25)}`, stopLoss: money(p + a * 1.15), targets: `${money(p - a * 1.65)} / ${money(p - a * 2.65)}`, rr: '1:2.30', note: 'Educational risk plan only.' }
  }
  return { entryZone: 'No trade zone', stopLoss: 'Wait for confluence', targets: '—', rr: '—', note: 'Market does not meet signal threshold.' }
}

export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store, max-age=0')
  try {
    const fg = await j(`${FNG}?limit=1`).catch(() => ({ data: [{ value: '50', value_classification: 'Neutral' }] }))
    const fear = Number(fg.data?.[0]?.value || 50)
    const raw = await Promise.all(symbols.map(symbolData))
    const btcChange = raw.find((x) => x.symbol === 'BTCUSDT')?.change || 0
    const signals = raw.map((d) => score(d, btcChange, fear)).sort((a, b) => Math.abs(b.scoreRaw) - Math.abs(a.scoreRaw))
    const best = signals[0]
    const bestRaw = raw.find((x) => x.symbol === best.symbol)
    const pipe = Object.entries(best.pipelines).map(([name, value]) => ({ name, score: Math.abs(Number(value.toFixed(1))), tone: tone(value) }))
    res.status(200).json({
      generatedAt: new Date().toISOString(),
      source: 'vercel-live-binance-api',
      status: { mode: 'live', message: 'Live prices/signals calculated from Binance public API.' },
      marketStats: raw.filter((x) => ['BTCUSDT', 'ETHUSDT'].includes(x.symbol)).map((x) => ({ label: x.symbol, value: money(x.price), change: pct(x.change), tone: tone(x.change) })).concat([{ label: 'BTC.D', value: 'Proxy', change: 'live soon', tone: 'flat' }, { label: 'Fear & Greed', value: String(fear), change: fg.data?.[0]?.value_classification || 'Neutral', tone: fear >= 60 ? 'warn' : fear <= 35 ? 'down' : 'flat' }]),
      signals,
      watchlist: signals.map((x) => [x.symbol.replace('USDT', ''), x.score, x.direction]),
      pipelines: pipe,
      chart: { symbol: best.symbol, timeframe: '1H', points: chart(bestRaw.closes) },
      riskPlan: risk(best, bestRaw),
      performance: { winRate: 'Live soon', tracked: '0', avgMove: 'Live soon', bestPair: best.symbol.replace('USDT', '') },
      system: { lastWorkflow: new Date().toISOString(), nextUpdate: 'Live API on refresh + hourly snapshot backup', dataFreshness: 'live', symbolsScanned: signals.length },
    })
  } catch (error) {
    res.status(500).json({ ok: false, message: error.message })
  }
}
