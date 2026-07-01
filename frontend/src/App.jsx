import {
  Activity,
  BarChart3,
  Bell,
  CandlestickChart,
  Gauge,
  LineChart,
  RadioTower,
  ShieldCheck,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Zap,
} from 'lucide-react'

const marketStats = [
  { label: 'BTCUSDT', value: '$104,280', change: '+1.82%', tone: 'up' },
  { label: 'ETHUSDT', value: '$5,840', change: '+0.74%', tone: 'up' },
  { label: 'BTC.D', value: '54.2%', change: '-0.31%', tone: 'down' },
  { label: 'Fear & Greed', value: '68', change: 'Greed', tone: 'warn' },
]

const signals = [
  {
    symbol: 'BTCUSDT',
    direction: 'LONG',
    score: '+7.8',
    confidence: '78%',
    price: '$104,280',
    reason: '4H trend aligned, funding neutral, liquidity supportive',
    tone: 'up',
  },
  {
    symbol: 'SOLUSDT',
    direction: 'WAIT',
    score: '+3.1',
    confidence: '42%',
    price: '$183.40',
    reason: 'Momentum improving but pipeline agreement is weak',
    tone: 'flat',
  },
  {
    symbol: 'AVAXUSDT',
    direction: 'SHORT WATCH',
    score: '-5.2',
    confidence: '63%',
    price: '$41.80',
    reason: 'Structure weakening near resistance zone',
    tone: 'down',
  },
]

const pipelines = [
  { name: 'Technical', score: 8.4, tone: 'up' },
  { name: 'Correlation', score: 6.8, tone: 'up' },
  { name: 'Fundamental', score: 4.5, tone: 'flat' },
  { name: 'Sentiment', score: 7.2, tone: 'up' },
  { name: 'Events', score: 5.7, tone: 'flat' },
]

const watchlist = [
  ['BTC', '+7.8', 'LONG'],
  ['ETH', '+5.9', 'WATCH'],
  ['SOL', '+3.1', 'WAIT'],
  ['BNB', '+2.4', 'WAIT'],
  ['AVAX', '-5.2', 'SHORT'],
]

const candles = [62, 68, 65, 72, 78, 75, 81, 88, 84, 91, 96, 94, 101, 108, 105, 114, 121, 118]

function ToneIcon({ tone }) {
  if (tone === 'up') return <TrendingUp size={16} />
  if (tone === 'down') return <TrendingDown size={16} />
  return <Activity size={16} />
}

function StatCard({ stat }) {
  return (
    <div className="stat-card">
      <div className="stat-top">
        <span>{stat.label}</span>
        <span className={`pill ${stat.tone}`}>{stat.change}</span>
      </div>
      <strong>{stat.value}</strong>
    </div>
  )
}

function SignalCard({ signal, active }) {
  return (
    <article className={`signal-card ${active ? 'active' : ''}`}>
      <div className="signal-head">
        <div>
          <span className="muted small">Signal</span>
          <h3>{signal.symbol}</h3>
        </div>
        <span className={`direction ${signal.tone}`}>{signal.direction}</span>
      </div>
      <div className="signal-grid">
        <div>
          <span>Score</span>
          <strong>{signal.score}</strong>
        </div>
        <div>
          <span>Confidence</span>
          <strong>{signal.confidence}</strong>
        </div>
        <div>
          <span>Price</span>
          <strong>{signal.price}</strong>
        </div>
      </div>
      <p>{signal.reason}</p>
    </article>
  )
}

function PipelineBar({ item }) {
  return (
    <div className="pipeline-row">
      <div className="pipeline-label">
        <span>{item.name}</span>
        <strong>{item.score.toFixed(1)}</strong>
      </div>
      <div className="bar-track">
        <div className={`bar-fill ${item.tone}`} style={{ width: `${item.score * 10}%` }} />
      </div>
    </div>
  )
}

function ChartPanel() {
  return (
    <section className="panel chart-panel">
      <div className="panel-head">
        <div>
          <span className="eyebrow">Live market context</span>
          <h2>BTCUSDT Research View</h2>
        </div>
        <div className="chart-actions">
          <span>15m</span>
          <span>1H</span>
          <strong>4H</strong>
          <span>1D</span>
        </div>
      </div>

      <div className="chart-shell">
        <div className="chart-grid" />
        <svg viewBox="0 0 900 280" className="line-svg" preserveAspectRatio="none">
          <defs>
            <linearGradient id="area" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="rgba(0,192,118,.35)" />
              <stop offset="100%" stopColor="rgba(0,192,118,0)" />
            </linearGradient>
          </defs>
          <path d="M0,210 C80,180 120,205 185,166 C245,130 310,165 360,112 C430,50 500,100 560,78 C640,48 705,84 760,42 C825,12 860,46 900,20" fill="none" stroke="var(--green)" strokeWidth="3" />
          <path d="M0,210 C80,180 120,205 185,166 C245,130 310,165 360,112 C430,50 500,100 560,78 C640,48 705,84 760,42 C825,12 860,46 900,20 L900,280 L0,280 Z" fill="url(#area)" />
        </svg>
        <div className="candles">
          {candles.map((height, index) => (
            <span key={index} className={index % 3 === 0 ? 'red' : 'green'} style={{ height: `${height}px` }} />
          ))}
        </div>
      </div>
    </section>
  )
}

function RiskPanel() {
  return (
    <section className="panel risk-panel">
      <div className="panel-head compact">
        <div>
          <span className="eyebrow">Execution discipline</span>
          <h2>Risk Plan</h2>
        </div>
        <ShieldCheck className="accent" />
      </div>
      <div className="risk-box">
        <div><span>Entry Zone</span><strong>$103,900 — $104,650</strong></div>
        <div><span>Stop Loss</span><strong>$102,450</strong></div>
        <div><span>TP1 / TP2</span><strong>$106,850 / $109,200</strong></div>
        <div><span>R:R</span><strong>1:2.42</strong></div>
      </div>
      <p className="panel-note">Educational research view only. Risk is capped before conviction is considered.</p>
    </section>
  )
}

function App() {
  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="logo"><CandlestickChart size={22} /></div>
          <div>
            <strong>Hyper Bot</strong>
            <span>Trading intelligence</span>
          </div>
        </div>

        <nav>
          <a className="active"><Gauge size={18} /> Dashboard</a>
          <a><LineChart size={18} /> Signals</a>
          <a><BarChart3 size={18} /> Performance</a>
          <a><RadioTower size={18} /> Pipelines</a>
        </nav>

        <div className="watchlist">
          <span className="eyebrow">Watchlist</span>
          {watchlist.map(([coin, score, mode]) => (
            <div className="watch-row" key={coin}>
              <strong>{coin}</strong>
              <span>{score}</span>
              <small>{mode}</small>
            </div>
          ))}
        </div>
      </aside>

      <section className="content">
        <header className="topbar">
          <div>
            <span className="eyebrow">Research dashboard</span>
            <h1>Market Intelligence</h1>
          </div>
          <button className="notify"><Bell size={18} /> Live Signals</button>
        </header>

        <section className="stats-grid">
          {marketStats.map((stat) => <StatCard stat={stat} key={stat.label} />)}
        </section>

        <section className="main-grid">
          <div className="left-stack">
            <ChartPanel />
            <section className="signals-grid">
              {signals.map((signal, index) => <SignalCard key={signal.symbol} signal={signal} active={index === 0} />)}
            </section>
          </div>

          <div className="right-stack">
            <RiskPanel />

            <section className="panel">
              <div className="panel-head compact">
                <div>
                  <span className="eyebrow">5-pipeline score</span>
                  <h2>Confluence</h2>
                </div>
                <Zap className="accent" />
              </div>
              <div className="pipeline-list">
                {pipelines.map((item) => <PipelineBar item={item} key={item.name} />)}
              </div>
            </section>

            <section className="panel performance-panel">
              <div className="panel-head compact">
                <div>
                  <span className="eyebrow">Outcome tracking</span>
                  <h2>Performance</h2>
                </div>
                <Sparkles className="accent" />
              </div>
              <div className="performance-grid">
                <div><span>Win Rate</span><strong>64.8%</strong></div>
                <div><span>Tracked</span><strong>142</strong></div>
                <div><span>Avg Move</span><strong className="green-text">+1.38%</strong></div>
                <div><span>Best Pair</span><strong>BTC</strong></div>
              </div>
            </section>
          </div>
        </section>
      </section>
    </main>
  )
}

export default App
