import { useEffect, useMemo, useState } from 'react'
import {
  Activity,
  BarChart3,
  Bell,
  Bot,
  CandlestickChart,
  Gauge,
  LineChart,
  Loader2,
  Play,
  RadioTower,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Target,
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
    { label: 'Source', value: '—', change: '—', tone: 'flat' },
  ],
  signals: [],
  watchlist: [],
  pipelines: [],
  chart: { symbol: 'BTCUSDT', timeframe: '1H', points: [55, 60, 58, 66, 70, 64, 78, 82] },
  riskPlan: { entryZone: '—', stopLoss: '—', targets: '—', rr: '—', note: 'Waiting for live data.' },
  performance: { winRate: '—', tracked: '0', avgMove: '—', bestPair: '—' },
  system: { dataFreshness: 'loading', nextUpdate: 'Live API on refresh' },
}

const pages = [
  { key: 'dashboard', label: 'Dashboard', icon: Gauge },
  { key: 'signals', label: 'Signals', icon: LineChart },
  { key: 'pipelines', label: 'Pipelines', icon: RadioTower },
  { key: 'performance', label: 'Performance', icon: BarChart3 },
]

function formatDate(value) {
  const time = Date.parse(value)
  if (!Number.isFinite(time)) return value || '—'
  return new Date(time).toLocaleString()
}

function StatCard({ stat }) {
  return <div className="stat-card"><div className="stat-top"><span>{stat.label}</span><span className={`pill ${stat.tone || 'flat'}`}>{stat.change}</span></div><strong>{stat.value}</strong></div>
}

function ToneIcon({ tone }) {
  if (tone === 'up') return <TrendingUp size={16} />
  if (tone === 'down') return <TrendingDown size={16} />
  return <Activity size={16} />
}

function DirectionPill({ signal }) {
  return <span className={`direction ${signal?.tone || 'flat'}`}><ToneIcon tone={signal?.tone} /> {signal?.direction || 'WAIT'}</span>
}

function SignalCard({ signal, active }) {
  return (
    <article className={`signal-card ${active ? 'active' : ''}`}>
      <div className="signal-head"><div><span className="muted small">Bot Signal</span><h3>{signal.symbol}</h3></div><DirectionPill signal={signal} /></div>
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

function BotSignalPanel({ signal, generatedAt }) {
  if (!signal) return <section className="panel bot-signal"><Bot className="accent" /><h2>Latest Bot Signal</h2><p>No signal generated yet. Run live scan to calculate the latest setup.</p></section>
  return (
    <section className="panel bot-signal">
      <div className="panel-head compact"><div><span className="eyebrow">Latest bot output</span><h2>{signal.symbol}</h2></div><DirectionPill signal={signal} /></div>
      <div className="bot-signal-grid"><div><span>Score</span><strong>{signal.score}</strong></div><div><span>Confidence</span><strong>{signal.confidence}</strong></div><div><span>Price</span><strong>{signal.price}</strong></div><div><span>Generated</span><strong>{formatDate(generatedAt)}</strong></div></div>
      <p>{signal.reason}</p>
    </section>
  )
}

function EmptyPanel({ title, copy }) {
  return <section className="panel empty-panel"><Sparkles className="accent" /><h2>{title}</h2><p>{copy}</p></section>
}

function DashboardPage({ dashboard, signals, pipelines, botSignal }) {
  return (
    <section className="main-grid">
      <div className="left-stack"><ChartPanel chart={dashboard.chart} /><BotSignalPanel signal={botSignal} generatedAt={dashboard.generatedAt} />{signals.length ? <section className="signals-grid">{signals.slice(0, 3).map((signal, index) => <SignalCard key={signal.symbol} signal={signal} active={index === 0} />)}</section> : <EmptyPanel title="No signals yet" copy="Run live scan manually or wait for live API refresh." />}</div>
      <div className="right-stack"><SystemPanel dashboard={dashboard} /><RiskPanel riskPlan={dashboard.riskPlan || fallback.riskPlan} /><PipelinesPanel pipelines={pipelines} /><PerformanceMini dashboard={dashboard} signals={signals} /></div>
    </section>
  )
}

function SignalsPage({ dashboard, signals, botSignal }) {
  return (
    <section className="page-stack"><BotSignalPanel signal={botSignal} generatedAt={dashboard.generatedAt} />{signals.length ? <div className="signal-table panel"><div className="table-head"><span>Pair</span><span>Signal</span><span>Score</span><span>Confidence</span><span>Price</span><span>Reason</span></div>{signals.map((signal) => <div className="table-row" key={signal.symbol}><strong>{signal.symbol}</strong><DirectionPill signal={signal} /><span>{signal.score}</span><span>{signal.confidence}</span><span>{signal.price}</span><p>{signal.reason}</p></div>)}</div> : <EmptyPanel title="Signals unavailable" copy="Live API did not return signal data yet." />}</section>
  )
}

function PipelinesPanel({ pipelines }) {
  return <section className="panel"><div className="panel-head compact"><div><span className="eyebrow">5-pipeline score</span><h2>Confluence</h2></div><Zap className="accent" /></div><div className="pipeline-list">{pipelines.map((item) => <PipelineBar item={item} key={item.name} />)}</div></section>
}

function PipelinesPage({ dashboard, pipelines, botSignal }) {
  const rawPipelines = botSignal?.pipelines || {}
  return (
    <section className="page-stack"><BotSignalPanel signal={botSignal} generatedAt={dashboard.generatedAt} /><div className="pipeline-page-grid"><PipelinesPanel pipelines={pipelines} /><section className="panel"><div className="panel-head compact"><div><span className="eyebrow">Pipeline detail</span><h2>Decision Breakdown</h2></div><RadioTower className="accent" /></div><div className="detail-list">{Object.entries(rawPipelines).map(([name, value]) => <div key={name}><span>{name}</span><strong className={Number(value) >= 0 ? 'green-text' : 'red-text'}>{Number(value).toFixed(2)}</strong></div>)}</div></section></div></section>
  )
}

function PerformanceMini({ dashboard, signals }) {
  const actionable = signals.filter((s) => s.direction !== 'WAIT').length
  const longs = signals.filter((s) => s.direction.includes('LONG')).length
  const shorts = signals.filter((s) => s.direction.includes('SHORT')).length
  return <section className="panel performance-panel"><div className="panel-head compact"><div><span className="eyebrow">Live performance proxy</span><h2>Market Health</h2></div><Sparkles className="accent" /></div><div className="performance-grid"><div><span>Actionable</span><strong>{actionable}</strong></div><div><span>Long Bias</span><strong>{longs}</strong></div><div><span>Short Bias</span><strong>{shorts}</strong></div><div><span>Best Pair</span><strong>{dashboard.performance?.bestPair || signals[0]?.symbol?.replace('USDT', '') || '—'}</strong></div></div></section>
}

function PerformancePage({ dashboard, signals, botSignal }) {
  const actionable = signals.filter((s) => s.direction !== 'WAIT')
  const avgConfidence = signals.length ? Math.round(signals.reduce((sum, s) => sum + Number(String(s.confidence).replace('%', '') || 0), 0) / signals.length) : 0
  const longBias = signals.filter((s) => s.direction.includes('LONG')).length
  const shortBias = signals.filter((s) => s.direction.includes('SHORT')).length
  return (
    <section className="page-stack"><BotSignalPanel signal={botSignal} generatedAt={dashboard.generatedAt} /><section className="metrics-grid"><StatCard stat={{ label: 'Actionable Signals', value: String(actionable.length), change: 'live', tone: actionable.length ? 'up' : 'flat' }} /><StatCard stat={{ label: 'Avg Confidence', value: `${avgConfidence}%`, change: 'signal set', tone: avgConfidence >= 60 ? 'up' : 'flat' }} /><StatCard stat={{ label: 'Long Bias', value: String(longBias), change: 'market', tone: longBias > shortBias ? 'up' : 'flat' }} /><StatCard stat={{ label: 'Short Bias', value: String(shortBias), change: 'market', tone: shortBias > longBias ? 'down' : 'flat' }} /></section><section className="panel"><div className="panel-head compact"><div><span className="eyebrow">Production note</span><h2>Outcome Tracking</h2></div><Target className="accent" /></div><p className="panel-note">Live performance page is functional from current bot signals. Historical win-rate will become real once the Python bot outcome tracker writes completed 1H/4H/24H results to an API-accessible store.</p></section></section>
  )
}

function SystemPanel({ dashboard }) {
  return <section className="panel system-panel"><div className="panel-head compact"><div><span className="eyebrow">Automation</span><h2>System Status</h2></div><RadioTower className="accent" /></div><div className="system-list"><div><span>Mode</span><strong>{dashboard.status?.mode}</strong></div><div><span>Last refresh</span><strong>{formatDate(dashboard.generatedAt)}</strong></div><div><span>Next update</span><strong>{dashboard.system?.nextUpdate}</strong></div></div></section>
}

function App() {
  const [dashboard, setDashboard] = useState(fallback)
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState('')
  const [activePage, setActivePage] = useState('dashboard')

  async function fetchLiveDashboard() {
    const response = await fetch(`/api/market?t=${Date.now()}`, { cache: 'no-store' })
    if (!response.ok) throw new Error('Live market API failed')
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
        setMessage('Live market API unavailable, showing last saved snapshot')
      } catch {
        setMessage('Dashboard data not available yet')
      }
    } finally {
      setLoading(false)
    }
  }

  async function runScan() {
    setMessage('Running live market scan...')
    try {
      const data = await fetchLiveDashboard()
      setDashboard({ ...fallback, ...data })
      setMessage('Live scan complete. Prices, signals, pipelines and performance refreshed.')
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
  const botSignal = signals[0]
  const watchlist = dashboard.watchlist || []
  const pipelines = dashboard.pipelines?.length ? dashboard.pipelines : fallback.pipelines
  const pageTitle = pages.find((page) => page.key === activePage)?.label || 'Dashboard'

  const page = useMemo(() => {
    if (activePage === 'signals') return <SignalsPage dashboard={dashboard} signals={signals} botSignal={botSignal} />
    if (activePage === 'pipelines') return <PipelinesPage dashboard={dashboard} pipelines={pipelines} botSignal={botSignal} />
    if (activePage === 'performance') return <PerformancePage dashboard={dashboard} signals={signals} botSignal={botSignal} />
    return <DashboardPage dashboard={dashboard} signals={signals} pipelines={pipelines} botSignal={botSignal} />
  }, [activePage, dashboard, signals, pipelines, botSignal])

  return (
    <main className="app-shell">
      <aside className="sidebar"><div className="brand"><div className="logo"><CandlestickChart size={22} /></div><div><strong>Hyper Bot</strong><span>Trading intelligence</span></div></div><nav>{pages.map(({ key, label, icon: Icon }) => <button key={key} className={activePage === key ? 'active' : ''} onClick={() => setActivePage(key)}><Icon size={18} /> {label}</button>)}</nav><div className="watchlist"><span className="eyebrow">Watchlist</span>{watchlist.map(([coin, score, mode]) => <div className="watch-row" key={coin}><strong>{coin}</strong><span>{score}</span><small>{mode}</small></div>)}</div></aside>
      <section className="content"><header className="topbar"><div><span className="eyebrow">{pageTitle}</span><h1>Market Intelligence</h1><p className="topbar-subtitle">{message || dashboard.status?.message}</p></div><div className="topbar-actions"><button className="secondary-btn" onClick={loadDashboard}>{loading ? <Loader2 className="spin" size={16} /> : <RefreshCw size={16} />} Refresh</button><button className="run-btn" onClick={runScan}><Play size={16} /> Run Live Scan</button><button className="notify"><Bell size={18} /> {dashboard.system?.dataFreshness || 'Live'}</button></div></header><section className="stats-grid">{dashboard.marketStats.map((stat) => <StatCard stat={stat} key={stat.label} />)}</section>{page}</section>
    </main>
  )
}

export default App
