import { useState, useEffect, useCallback } from 'react'
import { TrendingUp, RefreshCw, Loader2, AlertOctagon, AlertTriangle, Filter, Clock, Network } from 'lucide-react'
import { fetchAlerts, triggerDetection, fetchRunStatus } from '../api/patterns'
import type { AlertSummary, RunStatus } from '../types/patterns'
import type { NavContext } from '../App'
import AlertCard from '../components/AlertCard'

const RISK_ORDER = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3, UNKNOWN: 4 }
type RiskFilter = 'ALL' | 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'

export default function PatternBreaker({ navCtx }: { navCtx: NavContext }) {
  const [alerts,     setAlerts]     = useState<AlertSummary[]>([])
  const [status,     setStatus]     = useState<RunStatus | null>(null)
  const [loading,    setLoading]    = useState(false)
  const [error,      setError]      = useState<string | null>(null)
  const [filter,     setFilter]     = useState<RiskFilter>('ALL')
  const [triggering, setTriggering] = useState(false)

  const loadAlerts = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const [a, s] = await Promise.all([fetchAlerts(), fetchRunStatus()])
      setAlerts(a); setStatus(s)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed')
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { loadAlerts() }, [loadAlerts])
  useEffect(() => {
    if (!status?.running) return
    const id = setInterval(async () => {
      try {
        const s = await fetchRunStatus(); setStatus(s)
        if (!s.running) loadAlerts()
      } catch { /* silent */ }
    }, 3000)
    return () => clearInterval(id)
  }, [status?.running, loadAlerts])

  const handleRun = async (force = false) => {
    setTriggering(true); setError(null)
    try { await triggerDetection(force); setStatus(s => s ? { ...s, running: true } : null) }
    catch (e: unknown) { setError(e instanceof Error ? e.message : 'Failed') }
    finally { setTriggering(false) }
  }

  const sorted = [...alerts].sort((a, b) => {
    const ra = RISK_ORDER[a.risk_level as keyof typeof RISK_ORDER] ?? 4
    const rb = RISK_ORDER[b.risk_level as keyof typeof RISK_ORDER] ?? 4
    return ra !== rb ? ra - rb : b.confidence - a.confidence
  })
  const filtered    = filter === 'ALL' ? sorted : sorted.filter(a => a.risk_level === filter)
  const byRisk      = sorted.reduce<Record<string,number>>((acc,a) => { acc[a.risk_level]=(acc[a.risk_level]??0)+1; return acc }, {})
  const critCount   = byRisk['CRITICAL'] ?? 0
  const highCount   = byRisk['HIGH'] ?? 0

  const filterBtns: RiskFilter[] = ['ALL','CRITICAL','HIGH','MEDIUM','LOW']

  return (
    <div className="flex flex-col h-full overflow-hidden" style={{ background:'var(--bg)' }}>

      {/* Header */}
      <div className="section-header shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center"
                 style={{ background:'rgba(249,115,22,0.1)', border:'1px solid rgba(249,115,22,0.25)' }}>
              <TrendingUp size={17} style={{ color:'#f97316' }} />
            </div>
            <div>
              <h1 className="font-semibold text-base t-primary">Pattern Breaker</h1>
              <p className="text-xs t-3">Proactively surfaces recurring risk patterns</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {status?.running ? (
              <span className="flex items-center gap-1.5 text-xs font-medium text-orange-600 dark:text-orange-400
                               px-3 py-1.5 rounded-lg border border-orange-200 dark:border-orange-500/30
                               bg-orange-50 dark:bg-orange-500/10">
                <Loader2 size={12} className="animate-spin" /> Running…
              </span>
            ) : (
              <>
                <button onClick={() => handleRun(false)} disabled={triggering||loading} className="btn">
                  <RefreshCw size={13} className={triggering?'animate-spin':''} /> Detect new
                </button>
                <button onClick={() => handleRun(true)} disabled={triggering||loading}
                  className="btn" style={{ borderColor:'#f9731640', color:'#f97316' }}>
                  Re-run all
                </button>
              </>
            )}
            <button onClick={loadAlerts} disabled={loading} className="btn" style={{ padding:'6px 10px' }}>
              <RefreshCw size={13} className={loading?'animate-spin':''} />
            </button>
          </div>
        </div>

        {/* Summary + filters */}
        {alerts.length > 0 && (
          <div className="flex items-center gap-4 mt-4 flex-wrap">
            {critCount > 0 && (
              <span className="flex items-center gap-1.5 text-[13px] font-semibold text-red-600 dark:text-red-400">
                <AlertOctagon size={14} /> {critCount} CRITICAL
              </span>
            )}
            {highCount > 0 && (
              <span className="flex items-center gap-1.5 text-[13px] font-semibold text-orange-500">
                <AlertTriangle size={14} /> {highCount} HIGH
              </span>
            )}
            <span className="text-xs t-3">{alerts.length} total alerts</span>
            <div className="ml-auto flex items-center gap-1.5">
              <Filter size={12} className="t-3" />
              {filterBtns.map(f => (
                <button key={f} onClick={() => setFilter(f)}
                  className="pill cursor-pointer transition-all"
                  style={filter===f
                    ? { background:'var(--brand)', color:'white', borderColor:'var(--brand-2)' }
                    : { background:'var(--bg-2)', color:'var(--text-2)', borderColor:'var(--border)' }}>
                  {f==='ALL' ? `All (${alerts.length})` : `${f} (${byRisk[f]??0})`}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Status bar */}
      {(status?.error || error) && (
        <div className="shrink-0 px-6 py-2 text-xs font-medium text-red-600 dark:text-red-400
                        bg-red-50 dark:bg-red-500/10 border-b border-red-200 dark:border-red-500/20">
          {status?.error ?? error}
        </div>
      )}

      {/* Alert list */}
      <div className="flex-1 overflow-y-auto px-6 py-5 space-y-3">
        {loading && (
          <div className="flex items-center justify-center h-48">
            <Loader2 size={24} className="animate-spin t-3" />
          </div>
        )}

        {!loading && filtered.length === 0 && (
          <div className="flex flex-col items-center justify-center h-48 gap-3 t-3">
            <TrendingUp size={28} className="opacity-30" />
            {alerts.length === 0
              ? <><p className="text-sm t-2">No alerts yet.</p><p className="text-xs">Click "Detect new" to run.</p></>
              : <p className="text-sm">No alerts match "{filter}".</p>
            }
          </div>
        )}

        {!loading && filtered.map(alert => (
          <div key={alert.alert_id} className="space-y-1">
            <AlertCard alert={alert} />
            {alert.asset_id && (
              <div className="flex gap-3 pl-2">
                <button onClick={() => navCtx.goToTimeMachine(alert.asset_id!)}
                  className="flex items-center gap-1 text-[11px] t-3 hover:text-indigo-500 transition-colors">
                  <Clock size={10} /> Timeline for {alert.asset_id}
                </button>
                <button onClick={() => navCtx.goToGraph(alert.asset_id!)}
                  className="flex items-center gap-1 text-[11px] t-3 hover:text-green-500 transition-colors">
                  <Network size={10} /> Graph for {alert.asset_id}
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
