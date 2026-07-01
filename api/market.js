const CG = 'https://api.coingecko.com/api/v3/coins/markets'
const coins = [
  ['BTCUSDT', 'BTC', 'bitcoin'],
  ['ETHUSDT', 'ETH', 'ethereum'],
  ['SOLUSDT', 'SOL', 'solana'],
  ['BNBUSDT', 'BNB', 'binancecoin'],
  ['AVAXUSDT', 'AVAX', 'avalanche-2'],
]

const ids = coins.map((x) => x[2]).join(',')

function money(value) {
  const x = Number(value || 0)
  if (x >= 1000) return `$${x.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  if (x >= 1) return `$${x.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })}`
  return `$${x.toFixed(6)}`
}

function pct(value) {
  const x = Number(value || 0)
  return `${x >= 0 ? '+' : ''}${x.toFixed(2)}%`
}

function tone(value) {
  const x = Number(value || 0)
  if (x > 0.15) return 'up'
  if (x < -0.15) return 'down'
  return 'flat'
}

function norm(points) {
  const sample = (points || []).slice(-32)
  if (!sample.length) return [60, 66, 62, 70, 76, 72, 80]
  const min = Math.min(...sample)
  const max = Math.max(...sample)
  const span = max - min || 1
  return sample.map((v) => Math.round(38 + ((v - min) / span) * 92))
}

function score(row) {
  const change = Number(row.price_change_percentage_24h || 0)
  const capRank = Number(row.market_cap_rank || 99)
  const volume = Number(row.total_volume || 0)
  const liquidity = volume > 1_000_000_000 ? 2 : volume > 200_000_000 ? 1 : 0
  const rankScore = capRank <= 5 ? 1.5 : capRank <= 20 ? 1 : 0.5
  const momentum = Math.max(-4, Math.min(4, change / 1.5))
  const master = momentum * 0.55 + liquidity * 0.25 + rankScore * 0.2
  let direction = 'WAIT'
  let t = 'flat'
  if (master >= 3.2) { direction = 'LONG WATCH'; t = 'up' }
  if (master >= 5.5) { direction = 'LONG'; t = 'up' }
  if (master <= -3.2) { direction = 'SHORT WATCH'; t = 'down' }
  if (master <= -5.5) { direction = 'SHORT'; t = 'down' }
  return {
    symbol: coins.find((x) => x[2] === row.id)?.[0] || row.symbol.toUpperCase(),
    direction,
    score: `${master >= 0 ? '+' : ''}${master.toFixed(1)}`,
    scoreRaw: Number(master.toFixed(3)),
    confidence: `${Math.max(18, Math.min(96, Math.abs(master) / 6 * 100)).toFixed(0)}%`,
    price: money(row.current_price),
    priceRaw: row.current_price,
    change: pct(change),
    tone: t,
    reason: `CoinGecko live price, 24h move ${pct(change)}, rank #${capRank}, volume ${money(volume)}`,
    pipelines: {
      Technical: momentum,
      Correlation: change / 2,
      Fundamental: liquidity + rankScore,
      Sentiment: change > 0 ? 1 : -1,
      Events: 0.5,
    },
  }
}

function risk(best) {
  const price = Number(best.priceRaw || 0)
  const atr = price * 0.018
  if (best.direction.includes('LONG')) {
    return { entryZone: `${money(price - atr * .25)} — ${money(price + atr * .12)}`, stopLoss: money(price - atr * 1.15), targets: `${money(price + atr * 1.65)} / ${money(price + atr * 2.65)}`, rr: '1:2.30', note: 'Educational risk plan only.' }
  }
  if (best.direction.includes('SHORT')) {
    return { entryZone: `${money(price - atr * .12)} — ${money(price + atr * .25)}`, stopLoss: money(price + atr * 1.15), targets: `${money(price - atr * 1.65)} / ${money(price - atr * 2.65)}`, rr: '1:2.30', note: 'Educational risk plan only.' }
  }
  return { entryZone: 'No trade zone', stopLoss: 'Wait for confluence', targets: '—', rr: '—', note: 'Market does not meet signal threshold.' }
}

export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store, max-age=0')
  const url = `${CG}?vs_currency=usd&ids=${ids}&order=market_cap_desc&per_page=10&page=1&sparkline=true&price_change_percentage=24h`
  try {
    const response = await fetch(url, { headers: { 'user-agent': 'hyperbot-market-dashboard' } })
    if (!response.ok) throw new Error(`CoinGecko ${response.status}`)
    const rows = await response.json()
    const signals = rows.map(score).sort((a, b) => Math.abs(b.scoreRaw) - Math.abs(a.scoreRaw))
    const best = signals[0]
    const bestRow = rows.find((r) => (coins.find((x) => x[2] === r.id)?.[0]) === best.symbol) || rows[0]
    const pipelines = Object.entries(best.pipelines).map(([name, value]) => ({ name, score: Math.abs(Number(value.toFixed(1))), tone: tone(value) }))
    const marketStats = rows.slice(0, 2).map((r) => ({ label: coins.find((x) => x[2] === r.id)?.[0] || r.symbol.toUpperCase(), value: money(r.current_price), change: pct(r.price_change_percentage_24h), tone: tone(r.price_change_percentage_24h) }))
    marketStats.push({ label: 'BTC.D', value: 'Proxy', change: 'market rank', tone: 'flat' })
    marketStats.push({ label: 'Source', value: 'Live', change: 'CoinGecko', tone: 'up' })
    res.status(200).json({
      generatedAt: new Date().toISOString(),
      source: 'coingecko-live-market-api',
      status: { mode: 'live', message: 'Live prices/signals calculated from CoinGecko market API.' },
      marketStats,
      signals,
      watchlist: signals.map((x) => [x.symbol.replace('USDT', ''), x.score, x.direction]),
      pipelines,
      chart: { symbol: best.symbol, timeframe: '7D sparkline', points: norm(bestRow.sparkline_in_7d?.price) },
      riskPlan: risk(best),
      performance: { winRate: 'Live soon', tracked: '0', avgMove: 'Live soon', bestPair: best.symbol.replace('USDT', '') },
      system: { nextUpdate: 'Live on every refresh', dataFreshness: 'live', symbolsScanned: signals.length },
    })
  } catch (error) {
    res.status(500).json({ ok: false, message: error.message })
  }
}
