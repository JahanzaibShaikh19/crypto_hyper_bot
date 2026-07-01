import { useEffect, useState } from 'react'
import {
  Activity,
  BarChart3,
  Bell,
  CandlestickChart,
  Gauge,
  LineChart,
  Loader2,
  Play,
  RadioTower,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Zap,
} from 'lucide-react'

const fallback = {
  generatedAt: 'Loading...',
  status: { mode: 'loading', message: 'Loading dashboard data...' },
  marketStats: [
    { label: 'BTCUSDT', value: '—', change: '—', tone: 'flat' },
    { label: 'ETHUSDT', value: '—', change: '—', tone: 'flat' },
    { label: 'BTC.D', value: '—', change: '—', tone: 'flat' },
    { label: 'Fear & Greed', value: '—', change: '—', tone: 'flat' },
  ],
  signals: [],
  watchlist: [],
  pipelines: [],
  chart: { symbol: 'BTCUSDT', timeframe: '1H', points: [55, 60, 58, 66, 70, 64, 78, 82] },
  riskPlan: { entryZone: '—', stopLoss: '—', targets: '—', rr: '—', note: 'Waiting for live data.' },
  performance: { winRate: '—', tracked: '0', avgMove: '—', bestPair: '—' },
  system: { dataFreshness: 'loading', nextUpdate: 'Live API on refresh' },
}

function StatCard({ stat }) {
  return <div className="stat-card"><div className="stat-top"><span>{stat.label}</span><span className={`pill ${stat.tone || 'flat'}`}>{stat.change}</span></div><strong>{stat.value}</strong></div>
}

function ToneIcon({ tone }) {
  if (tone === 'up') return <TrendingUp size={16} />
  if (tone === 'down') return <TrendingDown size={16} />
  return <Activity size={16} />
}

function SignalCard({ signal, active }) {
  return (
    <article className={`signal-card ${active ? 'active' : ''}`}>
      <div className="signal-head"><div><span className="muted small">Signal</span><h3>{signal.symbol}</h3></div><span className={`direction ${signal.tone || 'flat'}`}><ToneIcon tone={signal.tone} /> {signal.direction}</span></div>
      <div className="signal-grid"><div><span>Score</span><strong>{signal.score}</strong></div><div><span>Confidence</span><strong>{signal.confidence}</strong></div><div><span>Price</span><strong>{signal.price}</strong></div></div>
      <p>{signal.reason}</p>
    </article>
  )
}

function PipelineBar({ item }) {
  const width = Math.min(100, Math.max(0, Math.abs(Number(item.score || 0)) * 10))
  return <div className="pipeline-row"><div className="pipeline-label"><span>{item.name}</span><strong>{Number(item.score || 0).toFixed(1)}</strong></div><div className="bar-track"><div className={`bar-fill ${item.tone || 'flat'}`} style={{ width: `${width}%` }} /></div></div>
}

function ChartPanel({ chart }) {
  const points = chart?.points?.length ? chart.points : fallback.chart.points
  const max = Math.max(...points)
  const min = Math.min(...points)
  const span = max - min || 1
  const path = points.map((point, index) => {
    const x = (index / Math.max(points.length - 1, 1)) * 900
    const y = 260 - ((point - min) / span) * 220
    return `${index === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
  return (
    <section className="panel chart-panel">
      <div className="panel-head"><div><span className="eyebrow">Live market context</span><h2>{chart?.symbol || 'BTCUSDT'} Research View</h2></div><div className="chart-actions"><span>15m</span><strong>{chart?.timeframe || '1H'}</strong><span>4H</span><span>1D</span></div></div>
      <div className="chart-shell"><div className="chart-grid" /><svg viewBox="0 0 900 280" className="line-svg" preserveAspectRatio="none"><defs><linearGradient id="area" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="rgba(0,192,118,.35)" /><stop offset="100%" stopColor="rgba(0,192,118,0)" /></linearGradient></defs><path d={path} fill="none" stroke="var(--green)" strokeWidth="3" /><path d={`${path} L900,280 L0,280 Z`} fill="url(#area)" /></svg><div className="candles">{points.slice(-22).map((value, index) => <span key={`${value}-${index}`} className={index % 4 === 0 ? 'red' : 'green'} style={{ height: `${Math.max(30, value)}px` }} />)}</div></div>
    </section>
  )
}

function RiskPanel({ riskPlan }) {
  return <section className="panel risk-panel"><div className="panel-head compact"><div><span className="eyebrow">Execution discipline</span><h2>Risk Plan</h2></div><ShieldCheck className="accent" /></div><div className="risk-box"><div><span>Entry Zone</span><strong>{riskPlan.entryZone}</strong></div><div><span>Stop Loss</span><strong>{riskPlan.stopLoss}</strong></div><div><span>TP1 / TP2</span><strong>{riskPlan.targets}</strong></div><div><span>R:R</span><strong>{riskPlan.rr}</strong></div></div><p className="panel-note">{riskPlan.note}</p></section>
}

function App() {
  const [dashboard, setDashboard] = useState(fallback)
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState('')

  async function fetchLiveDashboard() {
    const response = await fetch(`/api/dashboard?t=${Date.now()}`, { cache: 'no-store' })
    if (!response.ok) throw new Error('Live API failed')
    return response.json()
  }

  async function fetchSnapshotDashboard() {
    const response = await fetch(`/data/dashboard.json?t=${Date.now()}`, { cache: 'no-store' })
    if (!response.ok) throw new Error('Snapshot unavailable')
    return response.json()
  }

  async function loadDashboard() {
    setLoading(true)
    try {
      const data = await fetchLiveDashboard()
      setDashboard({ ...fallback, ...data })
      setMessage(data.status?.message || 'Live dashboard updated')
    } catch {
      try {
        const data = await fetchSnapshotDashboard()
        setDashboard({ ...fallback, ...data })
        setMessage('Live API unavailable, showing last saved snapshot')
      } catch {
        setMessage('Dashboard data not available yet')
      }
    } finally {
      setLoading(false)
    }
  }

  async function runScan() {
    setMessage('Running live scan...')
    try {
      const data = await fetchLiveDashboard()
      setDashboard({ ...fallback, ...data })
      setMessage('Live scan complete. Prices and signals refreshed.')
    } catch {
      setMessage('Live scan failed. Check Vercel function logs.')
    }
  }

  useEffect(() => {
    loadDashboard()
    const timer = setInterval(loadDashboard, 60000)
    return () => clearInterval(timer)
  }, [])

  const signals = dashboard.signals || []
  const watchlist = dashboard.watchlist || []
  const pipelines = dashboard.pipelines?.length ? dashboard.pipelines : fallback.pipelines
  const generatedAt = dashboard.generatedAt ? new Date(dashboard.generatedAt).toLocaleString() : '—'

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand"><div className="logo"><CandlestickChart size={22} /></div><div><strong>Hyper Bot</strong><span>Trading intelligence</span></div></div>
        <nav><a className="active"><Gauge size={18} /> Dashboard</a><a><LineChart size={18} /> Signals</a><a><BarChart3 size={18} /> Performance</a><a><RadioTower size={18} /> Pipelines</a></nav>
        <div className="watchlist"><span className="eyebrow">Watchlist</span>{watchlist.map(([coin, score, mode]) => <div className="watch-row" key={coin}><strong>{coin}</strong><span>{score}</span><small>{mode}</small></div>)}</div>
      </aside>

      <section className="content">
        <header className="topbar"><div><span className="eyebrow">Research dashboard</span><h1>Market Intelligence</h1><p className="topbar-subtitle">{message || dashboard.status?.message}</p></div><div className="topbar-actions"><button className="secondary-btn" onClick={loadDashboard}>{loading ? <Loader2 className="spin" size={16} /> : <RefreshCw size={16} />} Refresh</button><button className="run-btn" onClick={runScan}><Play size={16} /> Run Live Scan</button><button className="notify"><Bell size={18} /> {dashboard.system?.dataFreshness || 'Live'}</button></div></header>
        <section className="stats-grid">{dashboard.marketStats.map((stat) => <StatCard stat={stat} key={stat.label} />)}</section>
        <section className="main-grid"><div className="left-stack"><ChartPanel chart={dashboard.chart} />{signals.length ? <section className="signals-grid">{signals.map((signal, index) => <SignalCard key={signal.symbol} signal={signal} active={index === 0} />)}</section> : <section className="panel empty-panel"><Sparkles className="accent" /><h2>No signals yet</h2><p>Run scan manually or wait for live API.</p></section>}</div><div className="right-stack"><section className="panel system-panel"><div className="panel-head compact"><div><span className="eyebrow">Automation</span><h2>System Status</h2></div><RadioTower className="accent" /></div><div className="system-list"><div><span>Mode</span><strong>{dashboard.status?.mode}</strong></div><div><span>Last refresh</span><strong>{generatedAt}</strong></div><div><span>Next update</span><strong>{dashboard.system?.nextUpdate}</strong></div></div></section><RiskPanel riskPlan={dashboard.riskPlan || fallback.riskPlan} /><section className="panel"><div className="panel-head compact"><div><span className="eyebrow">5-pipeline score</span><h2>Confluence</h2></div><Zap className="accent" /></div><div className="pipeline-list">{pipelines.map((item) => <PipelineBar item={item} key={item.name} />)}</div></section><section className="panel performance-panel"><div className="panel-head compact"><div><span className="eyebrow">Outcome tracking</span><h2>Performance</h2></div><Sparkles className="accent" /></div><div className="performance-grid"><div><span>Win Rate</span><strong>{dashboard.performance?.winRate}</strong></div><div><span>Tracked</span><strong>{dashboard.performance?.tracked}</strong></div><div><span>Avg Move</span><strong className="green-text">{dashboard.performance?.avgMove}</strong></div><div><span>Best Pair</span><strong>{dashboard.performance?.bestPair}</strong></div></div></section></div></section>
      </section>
    </main>
  )
}

export default App
