import { useEffect, useMemo, useState } from 'react'
import { Bot, CheckCircle2, ExternalLink, Loader2, Play, RadioTower, RefreshCw, ShieldCheck, Sparkles, Zap } from 'lucide-react'

const initialScan = {
  generatedAt: 'never',
  status: { mode: 'waiting', message: 'No original bot scan has been run yet.' },
  summary: { symbolsScanned: 0, signalsFired: 0, bestSymbol: '—', bestDirection: 'NO_TRADE', bestScore: '+0.0', errors: [] },
  latestSignal: null,
  signals: [],
  pipelines: [],
}

const phases = [
  'Booting original Python engine',
  'Fetching Binance OHLCV + futures data',
  'Running TA, correlation, FA, sentiment, events',
  'Applying master scoring + override rules',
  'Exporting latest original bot signal',
]

function formatDate(value) {
  const parsed = Date.parse(value)
  if (!Number.isFinite(parsed)) return value || '—'
  return new Date(parsed).toLocaleString()
}

function DirectionPill({ signal }) {
  const tone = signal?.tone || 'flat'
  return <span className={`direction ${tone}`}>{signal?.direction || 'NO_TRADE'}</span>
}

function PipelineBar({ item }) {
  const width = Math.min(100, Math.max(0, Math.abs(Number(item.score || 0)) * 10))
  return <div className="pipeline-row"><div className="pipeline-label"><span>{item.name}</span><strong>{Number(item.rawScore ?? item.score ?? 0).toFixed(2)}</strong></div><div className="bar-track"><div className={`bar-fill ${item.tone || 'flat'}`} style={{ width: `${width}%` }} /></div></div>
}

function OriginalSignalCard({ signal, generatedAt }) {
  if (!signal) {
    return <section className="panel original-empty"><Bot className="accent" /><h2>No original bot signal yet</h2><p>Start an original bot scan to run the Python master engine and export the latest signal result.</p></section>
  }

  return (
    <section className="panel original-signal-card">
      <div className="panel-head compact"><div><span className="eyebrow">Latest original bot signal</span><h2>{signal.symbol}</h2></div><DirectionPill signal={signal} /></div>
      <div className="bot-signal-grid"><div><span>Score</span><strong>{signal.score}</strong></div><div><span>Confidence</span><strong>{signal.confidence}</strong></div><div><span>Price</span><strong>{signal.price}</strong></div><div><span>Generated</span><strong>{formatDate(generatedAt)}</strong></div></div>
      <p>{signal.reason}</p>
    </section>
  )
}

function ScannerStage({ scanning, phaseIndex }) {
  return (
    <section className={`panel scanner-hero ${scanning ? 'scanning' : ''}`}>
      <div className="scanner-copy">
        <span className="eyebrow">Original bot engine</span>
        <h2>Run the real Python signal pipeline</h2>
        <p>This triggers GitHub Actions to run the original master engine once: market data, 5 pipelines, overrides, scoring, and latest signal export.</p>
      </div>
      <div className="scanner-3d" aria-hidden="true">
        <div className="orbit orbit-one" />
        <div className="orbit orbit-two" />
        <div className="core-orb"><Zap size={34} /></div>
        <div className="cube cube-a" />
        <div className="cube cube-b" />
      </div>
      <div className="phase-list">
        {phases.map((phase, index) => <div key={phase} className={index <= phaseIndex ? 'active' : ''}><span>{index < phaseIndex ? <CheckCircle2 size={15} /> : index === phaseIndex && scanning ? <Loader2 className="spin" size={15} /> : index + 1}</span>{phase}</div>)}
      </div>
    </section>
  )
}

export default function OriginalScanner({ onRefreshMarket }) {
  const [scan, setScan] = useState(initialScan)
  const [workflow, setWorkflow] = useState(null)
  const [scanning, setScanning] = useState(false)
  const [phaseIndex, setPhaseIndex] = useState(0)
  const [message, setMessage] = useState('Ready to run original bot scan.')
  const [scanStartedAt, setScanStartedAt] = useState('')

  const latest = scan.latestSignal
  const signals = scan.signals || []
  const pipelines = scan.pipelines || []
  const runUrl = workflow?.htmlUrl

  async function readJson(url) {
    const response = await fetch(url, { cache: 'no-store' })
    if (!response.ok) throw new Error(`Failed to load ${url}`)
    return response.json()
  }

  async function loadOriginalSnapshot() {
    try {
      const data = await readJson(`/api/original-scan-result?t=${Date.now()}`)
      setScan({ ...initialScan, ...data })
      setMessage(data.status?.message || 'Latest original bot result loaded from GitHub.')
    } catch {
      try {
        const data = await readJson(`/data/original-bot-scan.json?t=${Date.now()}`)
        setScan({ ...initialScan, ...data })
        setMessage('Loaded bundled original bot snapshot fallback.')
      } catch {
        setMessage('Original bot snapshot is not available yet.')
      }
    }
  }

  async function pollStatus(after, limit = 24) {
    for (let attempt = 0; attempt < limit; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 5000))
      try {
        const query = after ? `&after=${encodeURIComponent(after)}` : ''
        const response = await fetch(`/api/original-scan-status?t=${Date.now()}${query}`, { cache: 'no-store' })
        const data = await response.json()
        setWorkflow(data)
        if (data.status === 'completed') {
          setScanning(false)
          setPhaseIndex(phases.length - 1)
          setMessage(data.conclusion === 'success' ? 'Original bot scan completed. Loading latest signal snapshot...' : `Original bot scan finished with ${data.conclusion}.`)
          await new Promise((resolve) => setTimeout(resolve, 3500))
          await loadOriginalSnapshot()
          return
        }
        if (data.status === 'in_progress' || data.status === 'queued') {
          setMessage(`Workflow ${data.status}. Original engine is running...`)
        }
      } catch {
        setMessage('Workflow started. Status polling temporarily unavailable.')
      }
    }
    setScanning(false)
    setMessage('Scan is taking longer than expected. Open GitHub workflow for details.')
  }

  async function startOriginalScan() {
    const startedAt = new Date().toISOString()
    setScanStartedAt(startedAt)
    setScanning(true)
    setPhaseIndex(0)
    setMessage('Starting original bot scan workflow...')
    setWorkflow(null)
    try {
      const response = await fetch('/api/original-scan', { method: 'POST' })
      const data = await response.json()
      if (!response.ok) throw new Error(data.message || 'Failed to start original scan')
      setMessage(data.message || 'Original bot scan started.')
      pollStatus(startedAt)
    } catch (error) {
      setScanning(false)
      setMessage(error.message || 'Unable to start original bot scan.')
    }
  }

  useEffect(() => {
    loadOriginalSnapshot()
  }, [])

  useEffect(() => {
    if (!scanning) return undefined
    const timer = setInterval(() => setPhaseIndex((value) => Math.min(phases.length - 1, value + 1)), 2600)
    return () => clearInterval(timer)
  }, [scanning])

  const health = useMemo(() => [
    { label: 'Symbols Scanned', value: String(scan.summary?.symbolsScanned ?? 0), icon: RadioTower },
    { label: 'Signals Fired', value: String(scan.summary?.signalsFired ?? 0), icon: Sparkles },
    { label: 'Best Symbol', value: scan.summary?.bestSymbol || '—', icon: ShieldCheck },
    { label: 'Best Score', value: scan.summary?.bestScore || '+0.0', icon: Zap },
  ], [scan])

  return (
    <section className="page-stack original-scan-page">
      <ScannerStage scanning={scanning} phaseIndex={phaseIndex} />

      <section className="scanner-actions panel">
        <div><span className="eyebrow">Control center</span><h2>Original Signal Runner</h2><p>{message}</p>{scanStartedAt && <small className="scan-started">Started: {formatDate(scanStartedAt)}</small>}</div>
        <div className="action-row"><button className="run-btn" onClick={startOriginalScan} disabled={scanning}>{scanning ? <Loader2 className="spin" size={16} /> : <Play size={16} />} Run Original Bot Scan</button><button className="secondary-btn" onClick={loadOriginalSnapshot}><RefreshCw size={16} /> Reload Result</button>{onRefreshMarket && <button className="secondary-btn" onClick={onRefreshMarket}><RefreshCw size={16} /> Refresh Market UI</button>}{runUrl && <a className="secondary-link" href={runUrl} target="_blank" rel="noreferrer"><ExternalLink size={16} /> Open Workflow</a>}</div>
      </section>

      <section className="metrics-grid">{health.map(({ label, value, icon: Icon }) => <div className="stat-card" key={label}><div className="stat-top"><span>{label}</span><Icon className="accent" size={16} /></div><strong>{value}</strong></div>)}</section>

      <OriginalSignalCard signal={latest} generatedAt={scan.generatedAt} />

      <section className="pipeline-page-grid"><section className="panel"><div className="panel-head compact"><div><span className="eyebrow">Original pipeline scores</span><h2>Master Engine Breakdown</h2></div><RadioTower className="accent" /></div><div className="pipeline-list">{pipelines.map((item) => <PipelineBar item={item} key={item.name} />)}</div></section><section className="panel"><div className="panel-head compact"><div><span className="eyebrow">All scanned symbols</span><h2>Original Bot Results</h2></div><Bot className="accent" /></div><div className="mini-signal-list">{signals.length ? signals.map((signal) => <div key={signal.symbol}><strong>{signal.symbol}</strong><DirectionPill signal={signal} /><span>{signal.score}</span><small>{signal.reason}</small></div>) : <p className="panel-note">No original bot results yet.</p>}</div></section></section>
    </section>
  )
}
